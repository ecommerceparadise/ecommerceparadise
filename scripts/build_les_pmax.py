"""Build the Laser Engraver Store feed-only Performance Max campaign.

Same shape as the Fountains USA rebuild: asset groups carry a listing filter
and NO creative assets, so PMax serves Shopping product ads only and every
click lands on the product page from the feed.

Segmented by LASER TYPE rather than brand, because the feed's brands are thin
and lopsided (gweike cloud 69, monportlaser 69, sculpfun 30, then four brands
with 2-6 products each) while laser type maps cleanly onto how people search:
"fiber laser engraver", "co2 laser cutter", "diode laser engraver", "uv laser
marking machine".

The two products typed '3d printer' fall into every asset group's "everything
else" bucket and are therefore excluded account-wide -- Trevor's call on
2026-09-03, since FlashForge and Ortur (the brands that drove 3D printer
demand) are not in Merchant Center at all and a feed campaign cannot serve
that traffic.

Created PAUSED. Search themes and audience signals are added separately by
add_les_pmax_signals.py.

Dry run unless --live.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

MERCHANT_ID = 5823754958
BUDGET_MICROS = 15_000_000
STORE_URL = "https://laserengraverstore.com"
CAMPAIGN_NAME = "LES - PMax - Lasers (feed only)"

# Lower 48. Read off the account's existing Shopping campaigns, not typed out.
STATES = [21133, 21135, 21136, 21137, 21138, 21139, 21141, 21142, 21143, 21145,
          21146, 21147, 21148, 21149, 21150, 21151, 21152, 21153, 21154, 21155,
          21156, 21157, 21158, 21159, 21160, 21161, 21162, 21163, 21164, 21165,
          21166, 21167, 21168, 21169, 21170, 21171, 21172, 21173, 21174, 21175,
          21176, 21177, 21178, 21179, 21180, 21182, 21183, 21184]

# (asset group label, [product_type_level1 values], product count in the feed)
GROUPS = [
    ("Fiber & MOPA Lasers", ["fiber laser engravers",
                             "mopa fiber laser engravers"], 86),
    ("Diode Lasers",        ["diode laser engravers"], 32),
    ("CO2 Lasers",          ["co2 laser engravers",
                             "industrial co2 laser engravers"], 29),
    ("UV Lasers",           ["uv laser engravers"], 18),
    ("Accessories & Kits",  ["laser accessories", "laser engravers",
                             "replacement filters (hepa & carbon)",
                             "small business production kits",
                             "dual laser engravers", "cnc machines"], 18),
]

NEGATIVE_LISTS = [
    (11765673294, "EP Generic"),
    (12165888848, "LES Universal Negatives"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    client = get_client()
    acct = resolve_account("Laser Engraver Store", client=client)
    CID = acct["id"]
    e = client.enums
    ga = client.get_service("GoogleAdsService")

    dupe = list(ga.search(customer_id=CID, query=f"""
        SELECT campaign.id FROM campaign
        WHERE campaign.name = '{CAMPAIGN_NAME}' AND campaign.status != 'REMOVED'"""))
    if dupe:
        print(f"{CAMPAIGN_NAME!r} already exists ({dupe[0].campaign.id}). Aborting.")
        return 1

    ops = []
    def op():
        o = client.get_type("MutateOperation")
        ops.append(o)
        return o
    tmp = [0]
    def nxt():
        tmp[0] -= 1
        return tmp[0]

    budget_rn = f"customers/{CID}/campaignBudgets/{nxt()}"
    b = op().campaign_budget_operation.create
    b.resource_name = budget_rn
    b.name = CAMPAIGN_NAME
    b.amount_micros = BUDGET_MICROS
    b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False

    camp_rn = f"customers/{CID}/campaigns/{nxt()}"
    c = op().campaign_operation.create
    c.resource_name = camp_rn
    c.name = CAMPAIGN_NAME
    c.status = e.CampaignStatusEnum.PAUSED
    c.advertising_channel_type = e.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
    c.campaign_budget = budget_rn
    c.maximize_conversions = client.get_type("MaximizeConversions")
    c.shopping_setting.merchant_id = MERCHANT_ID
    c.contains_eu_political_advertising = (
        e.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    c.geo_target_type_setting.positive_geo_target_type = e.PositiveGeoTargetTypeEnum.PRESENCE
    c.geo_target_type_setting.negative_geo_target_type = e.NegativeGeoTargetTypeEnum.PRESENCE
    for t in (e.AssetAutomationTypeEnum.FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION,
              e.AssetAutomationTypeEnum.TEXT_ASSET_AUTOMATION,
              e.AssetAutomationTypeEnum.GENERATE_IMAGE_EXTRACTION):
        a = client.get_type("Campaign").AssetAutomationSetting()
        a.asset_automation_type = t
        a.asset_automation_status = e.AssetAutomationStatusEnum.OPTED_OUT
        c.asset_automation_settings.append(a)

    for g in STATES:
        cc = op().campaign_criterion_operation.create
        cc.campaign = camp_rn
        cc.location.geo_target_constant = f"geoTargetConstants/{g}"
        cc.negative = False

    for lid, _ in NEGATIVE_LISTS:
        cs = op().campaign_shared_set_operation.create
        cs.campaign = camp_rn
        cs.shared_set = f"customers/{CID}/sharedSets/{lid}"

    for label, types, _count in GROUPS:
        ag_t = nxt()
        ag_rn = f"customers/{CID}/assetGroups/{ag_t}"
        ag = op().asset_group_operation.create
        ag.resource_name = ag_rn
        ag.campaign = camp_rn
        ag.name = f"LES - {label}"
        ag.final_urls.append(STORE_URL)   # required by the API, inert feed-only
        ag.status = e.AssetGroupStatusEnum.ENABLED

        root_rn = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        r = op().asset_group_listing_group_filter_operation.create
        r.resource_name = root_rn
        r.asset_group = ag_rn
        r.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
        r.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING

        for value in types:
            inc = op().asset_group_listing_group_filter_operation.create
            inc.resource_name = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
            inc.asset_group = ag_rn
            inc.type_ = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
            inc.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            inc.parent_listing_group_filter = root_rn
            inc.case_value.product_type.level = e.ListingGroupFilterProductTypeLevelEnum.LEVEL1
            inc.case_value.product_type.value = value

        oth = op().asset_group_listing_group_filter_operation.create
        oth.resource_name = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        oth.asset_group = ag_rn
        oth.type_ = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
        oth.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        oth.parent_listing_group_filter = root_rn
        oth.case_value.product_type.level = e.ListingGroupFilterProductTypeLevelEnum.LEVEL1

    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = CID
    req.mutate_operations.extend(ops)
    req.validate_only = not args.live

    print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
    print(f"  campaign   {CAMPAIGN_NAME}  ${BUDGET_MICROS/1e6:,.0f}/day  PAUSED")
    print(f"  merchant   {MERCHANT_ID}")
    print(f"  geo        lower 48 ({len(STATES)} states) on PRESENCE")
    print(f"  negatives  {[n for _, n in NEGATIVE_LISTS]}")
    print(f"  asset groups (feed-only, no creative):")
    covered = 0
    for label, types, count in GROUPS:
        covered += count
        print(f"    LES - {label:22} {count:>4} products  {types}")
    print(f"    -> {covered} of 185 products; the 2 typed '3d printer' fall into"
          f" 'everything else' and are excluded")

    resp = ga.mutate(request=req)
    if args.live:
        for r in resp.mutate_operation_responses:
            for f in ("campaign_result", "asset_group_result"):
                if r._pb.HasField(f):
                    print(f"    created {getattr(r, f).resource_name}")
    else:
        print("\nValidated OK. Re-run with --live to create.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
