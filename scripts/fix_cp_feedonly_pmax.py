"""Restore the Culinary Profis PMax to feed-only and give every feed brand an
asset group.

Two fixes in one atomic mutate, both against the live feed rather than a
hardcoded brand list, so this stays correct as stock moves.

FEED-ONLY. The campaign was built feed-only -- asset groups carrying a brand
listing filter and NO text, image, logo or video assets, with the three asset
automation types opted out. That is the house pattern in FUSA, LES and
BetterPatio: with no creative, PMax has nothing to build a display or video ad
from, so it serves Shopping inventory from the feed. Ad strength reads POOR and
the asset group stays ELIGIBLE. Anything that has since put creative back --
assets added in the UI, or asset automation flipping itself on -- takes the
campaign off that pattern and lets it spend on display. This removes every
asset group asset in the campaign and re-asserts the three opt-outs.

ONE ASSET GROUP PER BRAND. prune_cp_pmax_to_active.py cut the campaign to the
8 brands that had stock on 8 September. That was a snapshot, and its own
docstring says a restocked brand needs its asset group back. Any brand that has
since gained feed products has been unadvertised ever since. This creates an
asset group, brand listing filter and 'everything else' exclusion for every
brand in the feed that does not already have one.

Existing asset groups whose brand currently holds nothing are reported but NOT
removed: an asset group with no serveable products does not serve and costs
nothing, and keeping it means the next restock is covered without a rebuild.
Pruning is prune_cp_pmax_to_active.py's job, not this script's.

Matching is on each asset group's brand listing filter value, never on its
name, so the existing house labels (CP - BakeMax, CP - Pro-Cut, CP - MRCOOL)
are left alone and no duplicate group is ever created for a brand that already
has one.

No budget, bid strategy, status, geo or search theme is touched. Products
carrying no brand at all cannot be reached by a brand filter and are reported
separately -- pass --catchall to add a group that picks them up.

Dry run unless --live. The dry run runs the real mutate with validate_only, so
what it prints is what the API will accept.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_ads.auth import get_client  # noqa: E402
from google_ads.accounts import resolve_account  # noqa: E402

ACCOUNT = "Culinary Profis"
CAMPAIGN_NAME = "CP - PMax - Culinary (feed only)"
STORE_URL = "https://www.culinaryprofis.com"
CATCHALL_NAME = "CP - All Other Brands"


def automation_types(e):
    """Every real asset automation type in this library version.

    Deliberately derived from the enum rather than hardcoded. build_cp_pmax.py
    and restore_old_pmax.py both name GENERATE_IMAGE_EXTRACTION, which no
    longer exists in v21 -- those scripts raise AttributeError on the current
    library. For a feed-only campaign the answer is always 'opt out of all of
    them', so reading the enum keeps this correct across library bumps.
    """
    return [m for m in e.AssetAutomationTypeEnum
            if m.name not in ("UNSPECIFIED", "UNKNOWN")]


# House casing for brands that already have a group, so a brand that is removed
# and later rebuilt keeps the name the account is used to. Anything not listed
# is title-cased.
LABELS = {
    "bakemax": "BakeMax", "pro-cut": "Pro-Cut", "mrcool": "MRCOOL",
    "ikon": "IKON", "kingsbottle": "KingsBottle", "le griddle": "Le Griddle",
}


def label_for(brand):
    return LABELS.get(brand, brand.title())


def feed_brands(ga, cust):
    """Return {brand: (total, serveable)} for every brand in the feed.

    Serveable means in stock with no blocking issue. 'not_eligible_in_any_
    campaign' is not blocking -- it is the feed telling us the product has no
    asset group covering it, which is the very gap this script closes.
    """
    total, serveable, blank = Counter(), Counter(), [0, 0]
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand,
               shopping_product.availability,
               shopping_product.issues
        FROM shopping_product """):
        p = r.shopping_product
        brand = p.brand.strip().lower()
        blocked = bool({i.error_code for i in p.issues}
                       - {"not_eligible_in_any_campaign"})
        in_stock = p.availability.name == "IN_STOCK"
        if not brand:
            blank[0] += 1
            blank[1] += 0 if (blocked or not in_stock) else 1
            continue
        total[brand] += 1
        if in_stock and not blocked:
            serveable[brand] += 1
    return total, serveable, blank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="apply; otherwise validate_only dry run")
    ap.add_argument("--min-products", type=int, default=1,
                    help="only build groups for brands with at least this many "
                         "feed products (default 1: every brand)")
    ap.add_argument("--serveable-only", action="store_true",
                    help="only build groups for brands with stock TODAY; by "
                         "default an out-of-stock brand still gets one so a "
                         "restock is covered without a rebuild")
    ap.add_argument("--catchall", action="store_true",
                    help="also add one group for products carrying no brand")
    ap.add_argument("--keep-creative", action="store_true",
                    help="skip the feed-only half; only add missing brands")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT, client=client)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    camps = [r.campaign for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type
        FROM campaign
        WHERE campaign.name = '{CAMPAIGN_NAME}'
          AND campaign.status != 'REMOVED' """)]
    if len(camps) != 1:
        print(f"ABORT: expected exactly one campaign named {CAMPAIGN_NAME!r}, "
              f"found {len(camps)}.")
        return 1
    camp = camps[0]
    camp_id = camp.id
    camp_rn = f"customers/{cust}/campaigns/{camp_id}"
    if camp.advertising_channel_type.name != "PERFORMANCE_MAX":
        print(f"ABORT: {CAMPAIGN_NAME!r} is "
              f"{camp.advertising_channel_type.name}, not PERFORMANCE_MAX.")
        return 1

    # ---- current state ----------------------------------------------------
    groups = {r.asset_group.id: r.asset_group.name for r in ga.search(
        customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name FROM asset_group
        WHERE campaign.id = {camp_id} AND asset_group.status != 'REMOVED' """)}

    # brand each existing group filters on -> group id
    covered = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id,
               asset_group_listing_group_filter.type,
               asset_group_listing_group_filter.case_value.product_brand.value
        FROM asset_group_listing_group_filter
        WHERE campaign.id = {camp_id} """):
        f = r.asset_group_listing_group_filter
        if f.type_.name == "UNIT_INCLUDED":
            brand = f.case_value.product_brand.value.strip().lower()
            if brand:
                covered[brand] = r.asset_group.id

    creative = [(r.asset_group.name, r.asset_group_asset.field_type.name,
                 r.asset_group_asset.resource_name)
                for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group_asset.field_type,
               asset_group_asset.resource_name
        FROM asset_group_asset
        WHERE campaign.id = {camp_id}
          AND asset_group_asset.status != 'REMOVED' """)]

    automation = {s.asset_automation_type.name: s.asset_automation_status.name
                  for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.asset_automation_settings FROM campaign
        WHERE campaign.id = {camp_id} """)
                  for s in r.campaign.asset_automation_settings}
    want_off = automation_types(e)
    on = [t for t in want_off if automation.get(t.name) != "OPTED_OUT"]

    total, serveable, blank = feed_brands(ga, cust)

    pool = serveable if args.serveable_only else total
    missing = sorted(((b, total[b], serveable[b]) for b in total
                      if b not in covered and pool[b] >= args.min_products),
                     key=lambda x: -x[1])
    empty = sorted((groups[gid], b, total.get(b, 0))
                   for b, gid in covered.items() if total.get(b, 0) == 0)

    # ---- report -----------------------------------------------------------
    print(f"{'LIVE' if args.live else 'DRY RUN'}   {ACCOUNT} ({cust})")
    print(f"campaign  {CAMPAIGN_NAME}  [{camp_id}]  {camp.status.name}\n")
    print(f"feed      {sum(total.values())} branded products across "
          f"{len(total)} brands, {sum(serveable.values())} serveable today")
    print(f"          {blank[0]} products carry NO brand "
          f"({blank[1]} serveable)")
    print(f"groups    {len(groups)} asset groups, {len(covered)} brand filters\n")

    print("=" * 72)
    print("FEED-ONLY")
    print("=" * 72)
    if args.keep_creative:
        print("  skipped (--keep-creative)")
    elif not creative and not on:
        print("  already clean: no asset group assets, all automation opted out")
    else:
        if creative:
            by_group = Counter(g for g, _, _ in creative)
            print(f"  REMOVE {len(creative)} asset group assets — this is what "
                  f"takes the campaign off feed-only:")
            for g, n in by_group.most_common():
                kinds = Counter(k for gg, k, _ in creative if gg == g)
                print(f"    {g:28} {n:>3}  "
                      f"{', '.join(f'{k.lower()} x{c}' for k, c in kinds.most_common())}")
        else:
            print("  no asset group assets to remove")
        if on:
            print(f"  OPT OUT {len(on)} asset automation type(s) not already off:")
            for t in on:
                print(f"    {t.name}  ({automation.get(t.name, 'not set')})")
        else:
            print("  asset automation already opted out")

    print()
    print("=" * 72)
    print("BRAND COVERAGE")
    print("=" * 72)
    if missing:
        print(f"  CREATE {len(missing)} asset groups for uncovered feed brands:")
        print(f"    {'brand':28} {'products':>9} {'serveable':>10}   asset group")
        for b, t, s in missing:
            print(f"    {b:28} {t:>9} {s:>10}   CP - {label_for(b)}")
    else:
        print("  every feed brand already has an asset group")
    if empty:
        print(f"\n  {len(empty)} existing group(s) hold nothing in the feed today. "
              f"Kept —\n  an empty group does not serve and costs nothing, and it "
              f"covers a restock:")
        for name, b, _ in empty:
            print(f"    {name:28} brand={b!r}")
    if blank[0]:
        note = ("adding it" if args.catchall else
                "pass --catchall to add a group that picks them up")
        print(f"\n  {blank[0]} products carry no brand and cannot be reached by a "
              f"brand filter\n  ({note}). Fixing the brand attribute in the feed "
              f"is the better fix.")

    if not creative and not on and not missing and not args.catchall:
        print("\nNothing to do.")
        return 0

    # ---- build ------------------------------------------------------------
    ops = []

    def op():
        o = client.get_type("MutateOperation")
        ops.append(o)
        return o

    tmp = [0]

    def nxt():
        tmp[0] -= 1
        return tmp[0]

    if not args.keep_creative:
        for _, _, rn in creative:
            op().asset_group_asset_operation.remove = rn
        if on:
            # asset_automation_settings replaces the whole list, so every type
            # is written, not just the ones currently on.
            c = op().campaign_operation
            c.update.resource_name = camp_rn
            for t in want_off:
                s = client.get_type("Campaign").AssetAutomationSetting()
                s.asset_automation_type = t
                s.asset_automation_status = e.AssetAutomationStatusEnum.OPTED_OUT
                c.update.asset_automation_settings.append(s)
            c.update_mask.paths.append("asset_automation_settings")

    def add_group(name, brand, exclude=()):
        """Asset group with a brand filter and an 'everything else' sibling.

        Root, include and exclude go in one mutate with temporary resource
        names; a bare subdivision root fails atomically and leaves the group
        empty.

        brand=str  -> include that brand, exclude everything else.
        brand=None -> the no-brand catch-all: 'everything else' becomes the
        INCLUDED node, and every brand in `exclude` is added as an excluded
        sibling so that 'everything else' resolves to products with no brand
        rather than to the whole feed. Without those siblings the catch-all
        would match every product and compete with every brand group.
        """
        ag_t = nxt()
        ag_rn = f"customers/{cust}/assetGroups/{ag_t}"
        ag = op().asset_group_operation.create
        ag.resource_name = ag_rn
        ag.campaign = camp_rn
        ag.name = name
        ag.final_urls.append(STORE_URL)
        ag.status = e.AssetGroupStatusEnum.ENABLED

        root_rn = f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        r = op().asset_group_listing_group_filter_operation.create
        r.resource_name = root_rn
        r.asset_group = ag_rn
        r.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
        r.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING

        for value in ([brand] if brand is not None else list(exclude)):
            n = op().asset_group_listing_group_filter_operation.create
            n.resource_name = (
                f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}")
            n.asset_group = ag_rn
            n.type_ = (e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
                       if brand is not None
                       else e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED)
            n.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            n.parent_listing_group_filter = root_rn
            n.case_value.product_brand.value = value

        oth = op().asset_group_listing_group_filter_operation.create
        oth.resource_name = (
            f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}")
        oth.asset_group = ag_rn
        # The no-brand catch-all INCLUDES the blank-brand bucket; a brand group
        # excludes it.
        oth.type_ = (e.ListingGroupFilterTypeEnum.UNIT_INCLUDED if brand is None
                     else e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED)
        oth.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        oth.parent_listing_group_filter = root_rn
        oth.case_value._pb.product_brand.SetInParent()

    for b, _, _ in missing:
        add_group(f"CP - {label_for(b)}", b)
    if args.catchall:
        if CATCHALL_NAME in groups.values():
            print(f"\nABORT: {CATCHALL_NAME!r} already exists.")
            return 1
        # Exclude every brand in the feed, so 'everything else' means the
        # blank-brand products and nothing that a brand group already holds.
        add_group(CATCHALL_NAME, None, exclude=sorted(total))

    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = cust
    req.mutate_operations.extend(ops)
    req.validate_only = not args.live

    print(f"\n{len(ops)} operations")
    try:
        ga.mutate(request=req)
    except Exception as exc:
        print(f"\nFAILED (nothing changed — the mutate is atomic):\n  {exc}")
        return 1

    if not args.live:
        print("Validated OK. Re-run with --live to apply.")
        return 0

    print(f"Applied. Campaign {camp_id} is feed-only across "
          f"{len(groups) + len(missing) + (1 if args.catchall else 0)} "
          f"asset groups.")
    print("Budget, bid strategy, status, geo and search themes unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
