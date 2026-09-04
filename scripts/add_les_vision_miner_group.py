"""Add the seventh brand asset group -- vision miner -- to the LES PMax campaign.

Correction: when Trevor chose "drop 3D printers for now" he meant drop the
SEARCH TEXT ADS in favour of feed-only PMax, until a high-ticket quote request
funnel exists to send that traffic to. He did not mean drop the products. The
two vision miner 3D printers belong in the feed campaign.

vision miner is 2 products at $19,370 each -- 'Vision Miner 22 IDEX v4 3D
Printer'. At that price the pair is worth more than most of the laser
catalogue, so search themes are pitched at industrial and production buyers
rather than desktop 3D printing hobbyists.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24208827507
STORE_URL = "https://laserengraverstore.com"
AUDIENCE_ID = 358310333
LABEL, FEED_BRAND = "Vision Miner", "vision miner"

# Grounded in the feed: IDEX (independent dual extruder), 220v, $19,370.
# Nothing here claims a material or spec the feed does not show.
THEMES = [
    "industrial 3d printer", "vision miner 3d printer", "idex 3d printer",
    "dual extruder 3d printer", "large format 3d printer",
    "high temperature 3d printer", "professional 3d printer",
    "industrial fdm printer", "3d printer for manufacturing",
    "engineering 3d printer", "production 3d printer",
    "large build volume 3d printer", "commercial 3d printer",
    "high temp 3d printer", "independent dual extruder printer",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Laser Engraver Store", client=client)["id"]
    e = client.enums
    ga = client.get_service("GoogleAdsService")

    name = f"LES - {LABEL}"
    if list(ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id FROM asset_group WHERE campaign.id = {CAMPAIGN}
          AND asset_group.name = '{name}' AND asset_group.status != 'REMOVED'""")):
        print(f"{name!r} already exists. Nothing to do.")
        return 0

    count = len(list(ga.search(customer_id=cust, query=f"""
        SELECT shopping_product.title FROM shopping_product
        WHERE shopping_product.brand = '{FEED_BRAND}'""")))
    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print(f"CREATE asset group {name!r}")
    print(f"  brand filter  {FEED_BRAND!r}  ({count} products in the feed)")
    print(f"  search themes {len(THEMES)}")
    for t in THEMES:
        print(f"    {t}")
    if count == 0:
        print("\nREFUSING: no products match that brand in the feed.")
        return 1

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    ops = []
    def op():
        o = client.get_type("MutateOperation")
        ops.append(o)
        return o
    tmp = [0]
    def nxt():
        tmp[0] -= 1
        return tmp[0]

    ag_t = nxt()
    ag_rn = f"customers/{cust}/assetGroups/{ag_t}"
    ag = op().asset_group_operation.create
    ag.resource_name = ag_rn
    ag.campaign = f"customers/{cust}/campaigns/{CAMPAIGN}"
    ag.name = name
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
    inc.case_value.product_brand.value = FEED_BRAND

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

    agid = [r.asset_group.id for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id FROM asset_group WHERE campaign.id = {CAMPAIGN}
          AND asset_group.name = '{name}'""")][0]
    ag_rn = client.get_service("AssetGroupService").asset_group_path(cust, agid)
    sig_ops = []
    o = client.get_type("AssetGroupSignalOperation")
    o.create.asset_group = ag_rn
    o.create.audience.audience = f"customers/{cust}/audiences/{AUDIENCE_ID}"
    sig_ops.append(o)
    for t in THEMES:
        o = client.get_type("AssetGroupSignalOperation")
        o.create.asset_group = ag_rn
        o.create.search_theme.text = t
        sig_ops.append(o)
    client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
        customer_id=cust, operations=sig_ops)
    print(f"\n  created asset group {agid} with {len(sig_ops)} signals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
