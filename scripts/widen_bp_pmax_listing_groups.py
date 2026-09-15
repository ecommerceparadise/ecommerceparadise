"""Let the BetterPatio PMax serve the outdoor-kitchen products it already owns.

Each asset group filters brand -> product_type, and only three types are
included: 'bbq island', 'bbq island accessories' and 'outdoor kitchens'.
Everything else in those same brands is excluded, so 127 eligible products
sit in the campaign's own brands but cannot serve.

This adds the excluded types that genuinely belong in an outdoor kitchen --
grills, refrigerators, doors and drawers, griddles, pizza ovens, kegerators,
bar islands, modular cabinets, grill carts and power burners -- and leaves
out the ones that do not: fireplaces, fire pits, spas and hot tubs,
entertainment centers and patio furniture.

This is a small fix. It does NOT address the real gap: 10,486 eligible
products belong to 45 brands that have no asset group at all, and they are
mostly not outdoor kitchen products. See the handoff -- that needs a
Shopping campaign, not more asset groups here.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys
from collections import Counter, defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
PMAX = 24209664922

IN_THEME = {
    "pizza oven and cart", "bbq grill", "doors & drawers", "refrigerator",
    "modular island cabinets", "grill carts", "bbq accessory - power burner",
    "griddles", "bar islands", "kegerator",
}
OFF_THEME_NOTE = {
    "fireplace", "fire pit", "spas and hot tubs", "entertainment center",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    # brand subdivision node + the types already included beneath it
    brand_node, have = {}, defaultdict(set)
    nodes = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name,
               asset_group_listing_group_filter.resource_name,
               asset_group_listing_group_filter.parent_listing_group_filter,
               asset_group_listing_group_filter.type,
               asset_group_listing_group_filter.case_value.product_brand.value,
               asset_group_listing_group_filter.case_value.product_type.value
        FROM asset_group_listing_group_filter WHERE campaign.id = {PMAX} """):
        f = r.asset_group_listing_group_filter
        nodes[f.resource_name] = (f, r.asset_group.name)
        if f.type_.name == "SUBDIVISION" and f.case_value.product_brand.value:
            brand_node[f.case_value.product_brand.value.strip().lower()] = (
                f.resource_name, r.asset_group.name)
    for rn, (f, agname) in nodes.items():
        if f.type_.name == "UNIT_INCLUDED" and f.case_value.product_type.value:
            par = nodes.get(f.parent_listing_group_filter)
            if par and par[0].case_value.product_brand.value:
                have[par[0].case_value.product_brand.value.strip().lower()].add(
                    f.case_value.product_type.value.strip().lower())

    if not brand_node:
        print("ABORT: no brand subdivisions found; structure changed.")
        return 1

    # what the feed holds for those brands
    feed = defaultdict(Counter)
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.product_type_level1,
               shopping_product.issues FROM shopping_product """):
        p = r.shopping_product
        if {i.error_code for i in p.issues} - {"not_eligible_in_any_campaign"}:
            continue
        b = p.brand.strip().lower()
        if b in brand_node:
            feed[b][p.product_type_level1.strip().lower()] += 1

    ops, plan, skipped = [], [], []
    svc_ag = client.get_service("AssetGroupService")
    for brand, (parent_rn, agname) in sorted(brand_node.items()):
        ag_id = int(parent_rn.split("/")[-1].split("~")[0])
        for ptype, n in feed.get(brand, Counter()).most_common():
            if not ptype or ptype in have[brand]:
                continue
            if ptype not in IN_THEME:
                skipped.append((brand, ptype, n))
                continue
            op = client.get_type("AssetGroupListingGroupFilterOperation")
            c = op.create
            c.asset_group = svc_ag.asset_group_path(cust, ag_id)
            c.parent_listing_group_filter = parent_rn
            c.type_ = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
            c.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            c.case_value.product_type.value = ptype
            c.case_value.product_type.level = (
                e.ListingGroupFilterProductTypeLevelEnum.LEVEL1)
            ops.append(op)
            plan.append((agname, brand, ptype, n))

    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    by_ag = defaultdict(list)
    for agname, brand, ptype, n in plan:
        by_ag[agname].append((brand, ptype, n))
    gained = 0
    for agname in sorted(by_ag):
        print(f"{agname}")
        for brand, ptype, n in by_ag[agname]:
            print(f"    + {brand:42} {ptype!r:32} {n:4} products")
            gained += n
        print()
    print(f"{len(ops)} listing nodes, {gained} products newly reachable")
    if skipped:
        print(f"\nleft out as off-theme ({sum(n for _, _, n in skipped)} products):")
        agg = Counter()
        for _, ptype, n in skipped:
            agg[ptype] += n
        for ptype, n in agg.most_common():
            flag = "  <- deliberate" if ptype in OFF_THEME_NOTE else ""
            print(f"    {ptype!r:36} {n:4}{flag}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to push.")
        return 0
    if ops:
        client.get_service("AssetGroupListingGroupFilterService") \
              .mutate_asset_group_listing_group_filters(
                  customer_id=cust, operations=ops)
        print(f"\n  added {len(ops)} listing nodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
