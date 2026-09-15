"""Add one feed-only asset group per brand to the existing BetterPatio PMax.

Every active brand gets its own asset group inside
`BP · PMax — Outdoor Kitchens` [24209664922], alongside the three that already
carry creative (Mont Alpi, Cal Flame, BetterPatio House Brands). The new groups
carry no text, image, logo or video assets -- the feed-only pattern from the
other three accounts, where zero-asset groups are ELIGIBLE and serve Shopping
inventory straight from the feed.

Asset groups cannot be moved between campaigns, so this builds them fresh
rather than relocating the ones in the separate campaign created earlier.

Brands at or above OWN_GROUP_MIN eligible products get their own group; the
remainder land in a catch-all that includes "everything else", so brands added
to the feed later are advertised with no rebuild.

The three existing asset groups restrict their brands to kitchen product types
(bbq island, outdoor kitchens, grills, refrigerators and so on). The catch-all
is attempted WITHOUT excluding those brands first, so the leftover products --
Cal Flame fireplaces and fire pits, for instance -- are picked up too. If the
API rejects that as overlapping, it retries with those brands excluded and
reports the gap.

Listing trees are created one asset group at a time: subdivision and children
in a single mutate with temporary resource names, and the "everything else"
sibling marked present via SetInParent so its dimension is declared.

Idempotent -- existing asset groups and trees are left alone.
Run with no flags for a dry run. Pass --execute to build.
"""
import argparse
import sys
from collections import Counter, defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
PMAX = 24209664922
OWN_GROUP_MIN = 20
CATCHALL = "BP · All Other Brands"
FINAL_URL = "https://betterpatio.com"

KITCHENS_BRANDS = {
    "mont alpi", "cal flame", "betterpatio", "betterpatio designer series",
    "betterpatio mountain series", "betterpatio solace series",
    "betterpatio unfinished outdoor kitchens", "betterpatio.com",
    "ufinish by betterpatio outdoor kitchens",
}
DISPLAY = {
    "rcs": "RCS", "miragevision tv": "MirageVision TV",
    "american outdoor grill": "American Outdoor Grill",
    "le griddle": "Le Griddle",
}


def label(brand):
    return f"BP · {DISPLAY.get(brand, brand.title())}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    ok = Counter()
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.issues
        FROM shopping_product """):
        p = r.shopping_product
        if not ({i.error_code for i in p.issues} - {"not_eligible_in_any_campaign"}):
            ok[p.brand.strip().lower()] += 1

    own = [b for b, n in ok.most_common()
           if b and b not in KITCHENS_BRANDS and n >= OWN_GROUP_MIN]
    tail = [b for b, n in ok.most_common()
            if b not in KITCHENS_BRANDS and (not b or n < OWN_GROUP_MIN)]

    have = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.resource_name
        FROM asset_group WHERE campaign.id = {PMAX}
          AND asset_group.status != 'REMOVED' """):
        have[r.asset_group.name] = (r.asset_group.id, r.asset_group.resource_name)

    todo = [b for b in own if label(b) not in have]
    need_catchall = CATCHALL not in have

    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print(f"campaign {PMAX}; {len(have)} asset groups today")
    print(f"  new brand asset groups : {len(todo)} "
          f"({sum(ok[b] for b in todo)} products)")
    print(f"  catch-all needed       : {need_catchall} "
          f"({len(tail)} brands, {sum(ok[b] for b in tail)} products)")
    for b in todo:
        print(f"    {label(b):44} {ok[b]:6}")
    if not todo and not need_catchall:
        print("\nNothing to do.")
        return 0
    if not args.execute:
        print("\nDry run. Re-run with --execute to build.")
        return 0

    svc_ag = client.get_service("AssetGroupService")
    svc_lg = client.get_service("AssetGroupListingGroupFilterService")
    INC = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
    EXC = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
    SUB = e.ListingGroupFilterTypeEnum.SUBDIVISION

    def make_group(name):
        o = client.get_type("AssetGroupOperation")
        a = o.create
        a.name = name
        a.campaign = client.get_service("CampaignService").campaign_path(cust, PMAX)
        a.final_urls.append(FINAL_URL)
        a.status = e.AssetGroupStatusEnum.ENABLED
        return svc_ag.mutate_asset_groups(
            customer_id=cust, operations=[o]).results[0].resource_name

    def build_tree(ag_rn, children):
        ag_id = int(ag_rn.split("/")[-1])
        ops = []
        o = client.get_type("AssetGroupListingGroupFilterOperation")
        f = o.create
        f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                           f"{ag_id}~-1")
        f.asset_group = ag_rn
        f.type_ = SUB
        f.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        ops.append(o)
        for i, (kind, brand) in enumerate(children, start=2):
            o = client.get_type("AssetGroupListingGroupFilterOperation")
            f = o.create
            f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                               f"{ag_id}~-{i}")
            f.asset_group = ag_rn
            f.parent_listing_group_filter = (
                f"customers/{cust}/assetGroupListingGroupFilters/{ag_id}~-1")
            f.type_ = kind
            f.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            if brand is not None:
                f.case_value.product_brand.value = brand
            else:
                f._pb.case_value.product_brand.SetInParent()
            ops.append(o)
        svc_lg.mutate_asset_group_listing_group_filters(
            customer_id=cust, operations=ops)
        return len(ops)

    made = 0
    for b in todo:
        rn = make_group(label(b))
        n = build_tree(rn, [(INC, b), (EXC, None)])
        made += 1
        print(f"  {label(b)}: {n} listing nodes")

    if need_catchall:
        rn = make_group(CATCHALL)
        wide = [(EXC, x) for x in sorted(own)] + [(INC, None)]
        try:
            n = build_tree(rn, wide)
            print(f"  {CATCHALL}: {n} nodes -- also picks up the kitchen "
                  f"brands' non-kitchen products")
        except Exception as ex:
            print(f"  {CATCHALL}: wide catch-all rejected "
                  f"({str(ex)[:90]}); retrying with kitchen brands excluded")
            narrow = ([(EXC, x) for x in sorted(set(own) | KITCHENS_BRANDS)]
                      + [(INC, None)])
            n = build_tree(rn, narrow)
            print(f"  {CATCHALL}: {n} nodes (kitchen brands excluded)")
        made += 1

    print(f"\n{made} asset groups added to campaign {PMAX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
