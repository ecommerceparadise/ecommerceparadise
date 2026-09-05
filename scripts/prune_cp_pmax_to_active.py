"""Prune the Culinary Profis PMax campaign to brands with ACTIVE feed products.

Trevor: a lot of those brands are not carried any more -- build only for what is
actually in the feed.

The feed answers this directly. A product is active here if it is in stock and
carries no blocking error. On that test:

    ACTIVE   229 products across 8 brands
    DEAD   1,721 products across 77 brands, all out of stock

The seven asset groups built for brands with zero active products are removed:
mrcool (124), avanti (108), kingsbottle (71), ikon (70), le griddle (59),
whynter (55), empura (52). Every one is entirely out of stock.

An eighth active brand, 'primo' (2 products), had no asset group and gains one.

Note this is a snapshot of stock, not a statement about the catalogue. If a
brand is restocked it needs its asset group back -- run this script's reporting
half again to see the current split.

Removes and creates in one atomic mutate. Campaign stays PAUSED throughout.

Dry run unless --live.
"""
import argparse
import sys
from collections import Counter

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN_NAME = "CP - PMax - Culinary (feed only)"
STORE_URL = "https://www.culinaryprofis.com"

ADD = [("Primo", "primo", [
    "primo ceramic grill", "primo kamado grill", "ceramic kamado grill",
    "primo oval grill", "charcoal kamado smoker", "primo grill",
    "built in kamado grill", "ceramic charcoal grill", "kamado style grill",
    "primo xl", "outdoor ceramic smoker", "premium charcoal grill"])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Culinary Profis", client=client)["id"]
    e = client.enums
    ga = client.get_service("GoogleAdsService")

    # 1. Which brands are active right now, straight from the feed.
    ok, dead = Counter(), Counter()
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.issues
        FROM shopping_product"""):
        p = r.shopping_product
        blocking = {i.error_code for i in p.issues} - {"not_eligible_in_any_campaign"}
        (dead if blocking else ok)[p.brand] += 1
    active_brands = {b for b, v in ok.items() if v > 0 and b}

    # 2. What the campaign currently has.
    camp = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.status FROM campaign
        WHERE campaign.name = '{CAMPAIGN_NAME}' AND campaign.status != 'REMOVED'"""))
    if not camp:
        print(f"{CAMPAIGN_NAME!r} not found. Aborting.")
        return 1
    cid = camp[0].campaign.id
    groups = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name,
               asset_group_listing_group_filter.type,
               asset_group_listing_group_filter.case_value.product_brand.value
        FROM asset_group_listing_group_filter WHERE campaign.id = {cid}"""):
        f = r.asset_group_listing_group_filter
        if f.type_.name == "UNIT_INCLUDED":
            groups[r.asset_group.id] = (r.asset_group.name, f.case_value.product_brand.value)

    keep = {g: v for g, v in groups.items() if v[1] in active_brands}
    drop = {g: v for g, v in groups.items() if v[1] not in active_brands}
    add = [(l, b, t) for l, b, t in ADD
           if b in active_brands and b not in {v[1] for v in groups.values()}]

    print(f"{'LIVE' if args.live else 'DRY RUN'}   campaign {cid} "
          f"[{camp[0].campaign.status.name}]")
    print(f"\nFEED: {sum(ok.values())} active products across {len(active_brands)} "
          f"brands; {sum(dead.values())} dead across {len([b for b in dead if not ok[b]])} brands\n")
    print(f"KEEP {len(keep)} asset groups:")
    for g, (n, b) in sorted(keep.items(), key=lambda x: -ok[x[1][1]]):
        print(f"    {n[:24]:26} {b!r:16} {ok[b]:>4} active, {dead[b]:>4} out of stock")
    print(f"\nREMOVE {len(drop)} asset groups (zero active products):")
    for g, (n, b) in sorted(drop.items(), key=lambda x: -dead[x[1][1]]):
        print(f"    {n[:24]:26} {b!r:16} {ok[b]:>4} active, {dead[b]:>4} out of stock")
    print(f"\nADD {len(add)} asset groups:")
    for l, b, t in add:
        print(f"    CP - {l:22} {b!r:16} {ok[b]:>4} active, {len(t)} themes")
    covered = sum(ok[v[1]] for v in keep.values()) + sum(ok[b] for _, b, _ in add)
    print(f"\n  -> {covered} of {sum(ok.values())} active products covered")

    if not args.live:
        print("\nDry run only. Re-run with --live to apply.")
        return 0
    if not drop and not add:
        print("\nNothing to change.")
        return 0

    aud = list(ga.search(customer_id=cust, query=f"""
        SELECT asset_group_signal.audience.audience FROM asset_group_signal
        WHERE campaign.id = {cid}"""))
    audience_rn = next((r.asset_group_signal.audience.audience for r in aud
                        if r.asset_group_signal.audience.audience), None)

    ops = []
    def op():
        o = client.get_type("MutateOperation")
        ops.append(o)
        return o
    tmp = [0]
    def nxt():
        tmp[0] -= 1
        return tmp[0]

    for g in drop:
        op().asset_group_operation.remove = f"customers/{cust}/assetGroups/{g}"

    for label, feed_brand, _themes in add:
        ag_t = nxt()
        ag_rn = f"customers/{cust}/assetGroups/{ag_t}"
        ag = op().asset_group_operation.create
        ag.resource_name = ag_rn
        ag.campaign = f"customers/{cust}/campaigns/{cid}"
        ag.name = f"CP - {label}"
        ag.final_urls.append(STORE_URL)
        ag.status = e.AssetGroupStatusEnum.ENABLED
        root_rn = f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        r = op().asset_group_listing_group_filter_operation.create
        r.resource_name = root_rn
        r.asset_group = ag_rn
        r.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
        r.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        inc = op().asset_group_listing_group_filter_operation.create
        inc.resource_name = f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        inc.asset_group = ag_rn
        inc.type_ = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
        inc.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        inc.parent_listing_group_filter = root_rn
        inc.case_value.product_brand.value = feed_brand
        oth = op().asset_group_listing_group_filter_operation.create
        oth.resource_name = f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        oth.asset_group = ag_rn
        oth.type_ = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
        oth.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        oth.parent_listing_group_filter = root_rn
        oth.case_value._pb.product_brand.SetInParent()

    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = cust
    req.mutate_operations.extend(ops)
    ga.mutate(request=req)
    print(f"\n  {len(ops)} operations applied")

    if add:
        new = {r.asset_group.name: r.asset_group.id for r in ga.search(
            customer_id=cust, query=f"""
            SELECT asset_group.id, asset_group.name FROM asset_group
            WHERE campaign.id = {cid} AND asset_group.status != 'REMOVED'""")}
        ag_svc = client.get_service("AssetGroupService")
        sig = []
        for label, _b, themes in add:
            ag_rn = ag_svc.asset_group_path(cust, new[f"CP - {label}"])
            if audience_rn:
                o = client.get_type("AssetGroupSignalOperation")
                o.create.asset_group = ag_rn
                o.create.audience.audience = audience_rn
                sig.append(o)
            for t in themes:
                o = client.get_type("AssetGroupSignalOperation")
                o.create.asset_group = ag_rn
                o.create.search_theme.text = t
                sig.append(o)
        client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
            customer_id=cust, operations=sig)
        print(f"  {len(sig)} signals added to the new asset group(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
