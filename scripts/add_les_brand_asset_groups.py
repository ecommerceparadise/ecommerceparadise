"""Give every uncovered brand in the Laser Engraver Store feed an asset group.

`LES - PMax - Lasers (feed only)` [24208827507] reaches 138 of 222 eligible
products. Seven live asset groups filter on brand; the rest of the catalogue
matches nothing.

READ ONLY LIVE ASSET GROUPS. The campaign also holds five REMOVED asset groups
that filtered on product_type (diode, CO2, fiber/MOPA, UV, accessories). Their
listing group filters still come back from asset_group_listing_group_filter,
so a query that does not join on asset_group.status counts them as coverage
and reports 90%+ when the truth is 62%. The uncovered brands below are exactly
the ones those removed groups used to catch.

Uncovered brands are derived from the feed at run time, not hardcoded, so this
stays correct as the catalogue changes. A brand is skipped if it already has
an asset group, and the run aborts if any of its product types is targeted by
a live type-based filter -- that would put products in two asset groups at
once.

Feed-only pattern: no text, image, logo or video assets. Final URL is read
from an existing asset group rather than hardcoded.

Run with no flags for a dry run. Pass --execute to build.
"""
import argparse
import sys
from collections import Counter

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "Laser Engraver Store"
PMAX = 24208827507
MIN_PRODUCTS = 1
DISPLAY = {"flashforge": "FlashForge", "laserpecker": "LaserPecker",
           "full spectrum laser": "Full Spectrum Laser", "ortur": "Ortur"}


def label_for(brand):
    return f"LES - {DISPLAY.get(brand, brand.title())}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    # LIVE asset groups only -- removed ones still return listing filters
    live, names, final_url = set(), set(), None
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group.final_urls, asset_group.status
        FROM asset_group WHERE campaign.id = {PMAX}
          AND asset_group.status = 'ENABLED' """):
        live.add(r.asset_group.name)
        names.add(r.asset_group.name)
        if final_url is None and r.asset_group.final_urls:
            final_url = list(r.asset_group.final_urls)[0]

    have_brand, have_type = set(), set()
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group_listing_group_filter.type,
               asset_group_listing_group_filter.case_value.product_brand.value,
               asset_group_listing_group_filter.case_value.product_type.value
        FROM asset_group_listing_group_filter WHERE campaign.id = {PMAX} """):
        if r.asset_group.name not in live:
            continue
        f = r.asset_group_listing_group_filter
        if f.type_.name != "UNIT_INCLUDED":
            continue
        if f.case_value.product_brand.value:
            have_brand.add(f.case_value.product_brand.value.strip().lower())
        elif f.case_value.product_type.value:
            have_type.add(f.case_value.product_type.value.strip().lower())

    if not final_url:
        print("ABORT: no final URL found on any existing asset group.")
        return 1

    # feed reality
    feed, types = Counter(), {}
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.product_type_level1,
               shopping_product.issues FROM shopping_product """):
        p = r.shopping_product
        if {i.error_code for i in p.issues} - {"not_eligible_in_any_campaign"}:
            continue
        b = p.brand.strip().lower()
        feed[b] += 1
        types.setdefault(b, Counter())[p.product_type_level1.strip().lower()] += 1

    uncovered = sorted(
        (b for b, n in feed.items()
         if b and n >= MIN_PRODUCTS and b not in have_brand
         and not any(t in have_type for t in types[b])),
        key=lambda b: -feed[b])
    blank = feed.get("", 0)

    plan = []
    for brand in uncovered:
        label = label_for(brand)
        if brand in have_brand or label in names:
            print(f"  skip {brand!r}: already has an asset group")
            continue
        if not feed.get(brand):
            print(f"ABORT: brand {brand!r} has no eligible products in the feed.")
            return 1
        clash = [t for t in types[brand] if t in have_type]
        if clash:
            print(f"ABORT: {brand!r} has product types already targeted by a "
                  f"type-based asset group ({clash}); adding it would put those "
                  f"products in two asset groups at once.")
            return 1
        plan.append((brand, label, feed[brand], dict(types[brand])))

    covered = sum(n for b, n in feed.items()
                  if b in have_brand or any(t in have_type for t in types[b]))
    total = sum(feed.values())
    print(f"\n{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print(f"campaign {PMAX}; {len(live)} LIVE asset groups; final URL {final_url}")
    print(f"feed: {total} eligible, {covered} reachable today "
          f"({covered/total*100:.1f}%)")
    if blank:
        print(f"  note: {blank} eligible products have NO brand set -- a brand "
              f"asset group cannot reach them")
    for brand, label, n, t in plan:
        print(f"  + {label:30} brand={brand!r:24} {n:4} products  types={t}")
    if not plan:
        print("\nNothing to do.")
        return 0
    after = covered + sum(n for _, _, n, _ in plan)
    print(f"\ncoverage after: {after} of {total} ({after/total*100:.1f}%)")

    if not args.execute:
        print("\nDry run. Re-run with --execute to build.")
        return 0

    svc_ag = client.get_service("AssetGroupService")
    svc_lg = client.get_service("AssetGroupListingGroupFilterService")
    for brand, label, n, _ in plan:
        o = client.get_type("AssetGroupOperation")
        a = o.create
        a.name = label
        a.campaign = client.get_service("CampaignService").campaign_path(cust, PMAX)
        a.final_urls.append(final_url)
        a.status = e.AssetGroupStatusEnum.ENABLED
        ag_rn = svc_ag.mutate_asset_groups(
            customer_id=cust, operations=[o]).results[0].resource_name
        ag_id = int(ag_rn.split("/")[-1])

        # root + children in ONE mutate, temporary resource names
        ops = []
        root = f"customers/{cust}/assetGroupListingGroupFilters/{ag_id}~-1"
        o = client.get_type("AssetGroupListingGroupFilterOperation")
        f = o.create
        f.resource_name = root
        f.asset_group = ag_rn
        f.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
        f.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        ops.append(o)
        for i, (kind, val) in enumerate(
                [(e.ListingGroupFilterTypeEnum.UNIT_INCLUDED, brand),
                 (e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED, None)], start=2):
            o = client.get_type("AssetGroupListingGroupFilterOperation")
            f = o.create
            f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                               f"{ag_id}~-{i}")
            f.asset_group = ag_rn
            f.parent_listing_group_filter = root
            f.type_ = kind
            f.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            if val is not None:
                f.case_value.product_brand.value = val
            else:
                f._pb.case_value.product_brand.SetInParent()
            ops.append(o)
        svc_lg.mutate_asset_group_listing_group_filters(
            customer_id=cust, operations=ops)
        print(f"  built {label}: {len(ops)} listing nodes, {n} products")
    return 0


if __name__ == "__main__":
    sys.exit(main())
