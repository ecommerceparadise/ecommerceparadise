"""Build the Fountains USA feed-only Performance Max campaign. Dry run unless --live.

Feed-only means the asset groups carry a listing filter and NO creative assets.
With no headlines, descriptions or images there is nothing for PMax to serve on
Search, Display, YouTube or Discover, so it serves Shopping product ads only and
every click lands on the product page from the feed. That is what makes it safe
to run while fountainsusa.com has no lead-optimised landing page.

The asset group final URL is required by the API but is inert in this mode: it
is only used to build non-Shopping creative, and there is none.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

MERCHANT_ID = 258983089
BUDGET_MICROS = 15_000_000          # $15/day of Trevor's $20 account budget
STORE_URL = "https://www.fountainsusa.com"
STATES = ["geoTargetConstants/21137",   # California
          "geoTargetConstants/21136",   # Arizona
          "geoTargetConstants/21176",   # Texas
          "geoTargetConstants/21142"]   # Florida
BRANDS = [("The Outdoor Plus", "the outdoor plus"),
          ("Giannini Garden", "giannini garden"),
          ("Fiore Stone", "fiore stone"),
          ("Metropolitan Galleries", "metropolitan galleries inc.")]

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); acct = resolve_account("Fountains USA", client=client)
CID = acct["id"]; e = client.enums
ops = []
def op():
    o = client.get_type("MutateOperation"); ops.append(o); return o
tmp = [0]
def nxt():
    tmp[0] -= 1; return tmp[0]

budget_rn = f"customers/{CID}/campaignBudgets/{nxt()}"
b = op().campaign_budget_operation.create
b.resource_name = budget_rn
b.name = "FUSA - PMax - Fountains (feed only)"
b.amount_micros = BUDGET_MICROS
b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
b.explicitly_shared = False

camp_rn = f"customers/{CID}/campaigns/{nxt()}"
c = op().campaign_operation.create
c.resource_name = camp_rn
c.name = "FUSA - PMax - Fountains (feed only)"
c.status = e.CampaignStatusEnum.PAUSED
c.advertising_channel_type = e.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
c.campaign_budget = budget_rn
c.maximize_conversions = client.get_type("MaximizeConversions")
c.shopping_setting.merchant_id = MERCHANT_ID
c.contains_eu_political_advertising = (
    e.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
c.geo_target_type_setting.positive_geo_target_type = e.PositiveGeoTargetTypeEnum.PRESENCE
c.geo_target_type_setting.negative_geo_target_type = e.NegativeGeoTargetTypeEnum.PRESENCE
for t, status in [
        (e.AssetAutomationTypeEnum.FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION, "OPTED_OUT"),
        (e.AssetAutomationTypeEnum.TEXT_ASSET_AUTOMATION, "OPTED_OUT"),
        (e.AssetAutomationTypeEnum.GENERATE_IMAGE_EXTRACTION, "OPTED_OUT")]:
    a = client.get_type("Campaign").AssetAutomationSetting()
    a.asset_automation_type = t
    a.asset_automation_status = getattr(e.AssetAutomationStatusEnum, status)
    c.asset_automation_settings.append(a)

for g in STATES:
    cc = op().campaign_criterion_operation.create
    cc.campaign = camp_rn
    cc.location.geo_target_constant = g
    cc.negative = False

for label, feed_brand in BRANDS:
    ag_t = nxt()
    ag_rn = f"customers/{CID}/assetGroups/{ag_t}"
    ag = op().asset_group_operation.create
    ag.resource_name = ag_rn
    ag.campaign = camp_rn
    ag.name = f"FUSA - {label}"
    ag.final_urls.append(STORE_URL)      # required by the API, unused in feed-only mode
    ag.status = e.AssetGroupStatusEnum.ENABLED

    root_rn = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
    r = op().asset_group_listing_group_filter_operation.create
    r.resource_name = root_rn
    r.asset_group = ag_rn
    r.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
    r.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING

    inc = op().asset_group_listing_group_filter_operation.create
    inc.resource_name = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
    inc.asset_group = ag_rn
    inc.type_ = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
    inc.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
    inc.parent_listing_group_filter = root_rn
    inc.case_value.product_brand.value = feed_brand

    oth = op().asset_group_listing_group_filter_operation.create
    oth.resource_name = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
    oth.asset_group = ag_rn
    oth.type_ = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
    oth.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
    oth.parent_listing_group_filter = root_rn
    oth.case_value._pb.product_brand.SetInParent()   # "everything else", not brand==""

ga = client.get_service("GoogleAdsService")
req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID
req.mutate_operations.extend(ops)
req.validate_only = not args.live
print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
print(f"  campaign  FUSA - PMax - Fountains (feed only)  ${BUDGET_MICROS/1e6:,.0f}/day  PAUSED")
print(f"  geo       California, Arizona, Texas, Florida  PRESENCE")
print(f"  asset groups (no creative, listing filter only):")
for label, fb in BRANDS:
    print(f"      {label:<24} brand = {fb!r}")
try:
    ga.mutate(request=req)
    print("\n" + ("DONE" if args.live else "VALIDATED - nothing written"))
except Exception as ex:
    print("\nFAILED:"); print(str(ex)[:1800]); sys.exit(1)
