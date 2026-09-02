"""Build the Fountains USA dynamic display remarketing campaign. Dry run unless --live.

Products come from the Merchant Center feed and are constrained to Trevor's four
brands by a campaign-level listing_scope, so a visitor who browsed an excluded
brand cannot be followed with it. Optimized targeting is OFF: left on, Google
serves past the remarketing lists to people who never visited, which is the
opposite of remarketing and is what was quietly draining the BetterPatio account.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

MERCHANT_ID = 258983089
BUDGET_MICROS = 5_000_000
STORE_URL = "https://www.fountainsusa.com"
STATES = ["geoTargetConstants/21137", "geoTargetConstants/21136",
          "geoTargetConstants/21176", "geoTargetConstants/21142"]
BRANDS = ["the outdoor plus", "giannini garden", "fiore stone", "metropolitan galleries inc."]
AUDIENCES = [9187533874,   # Product viewers (Retail)
             9204844723,   # All Users of Fountains USA Shopify Store
             9187533877]   # Shopping cart abandoners (Retail)
HEADLINES = ["Still Comparing Fountains?", "Your Fountain Is Waiting",
             "Free Freight Quote", "Authorized Dealer", "Trade Pricing Available"]
LONG_HEADLINE = "Cast Stone, Marble And Fire Water Fountains Shipped To Your Project"
DESCRIPTIONS = ["Pick up where you left off.",
                "Authorized dealer for The Outdoor Plus, Giannini, Fiore and Metropolitan.",
                "Freight quoted with every fountain. Trade pricing for builders.",
                "Questions on sizing or install? Talk to a specialist before you order."]
MARKETING = [269417357430, 269886518701, 278174306978]
SQUARE    = [269417348868, 269901348654, 269398016164]
BUSINESS  = "Fountains USA"

for h in HEADLINES:      assert len(h) <= 30, h
assert len(LONG_HEADLINE) <= 90
for d in DESCRIPTIONS:   assert len(d) <= 90, d
assert len(BUSINESS) <= 25

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
b.name = "FUSA - Dynamic Display Remarketing"
b.amount_micros = BUDGET_MICROS
b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
b.explicitly_shared = False

camp_rn = f"customers/{CID}/campaigns/{nxt()}"
c = op().campaign_operation.create
c.resource_name = camp_rn
c.name = "FUSA - Dynamic Display Remarketing"
c.status = e.CampaignStatusEnum.PAUSED
c.advertising_channel_type = e.AdvertisingChannelTypeEnum.DISPLAY
c.campaign_budget = budget_rn
c.maximize_conversions = client.get_type("MaximizeConversions")
c.shopping_setting.merchant_id = MERCHANT_ID
c.contains_eu_political_advertising = (
    e.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
c.geo_target_type_setting.positive_geo_target_type = e.PositiveGeoTargetTypeEnum.PRESENCE
c.geo_target_type_setting.negative_geo_target_type = e.NegativeGeoTargetTypeEnum.PRESENCE

for g in STATES:
    cc = op().campaign_criterion_operation.create
    cc.campaign = camp_rn
    cc.location.geo_target_constant = g
    cc.negative = False

# Constrain the feed to Trevor's four brands at campaign level.
scope = op().campaign_criterion_operation.create
scope.campaign = camp_rn
d = client.get_type("ListingDimensionInfo")
d.product_brand.value = BRANDS[0]
scope.listing_scope.dimensions.append(d)

ag_rn = f"customers/{CID}/adGroups/{nxt()}"
ag = op().ad_group_operation.create
ag.resource_name = ag_rn
ag.campaign = camp_rn
ag.name = "FUSA - Warm Product Viewers"
ag.type_ = e.AdGroupTypeEnum.DISPLAY_STANDARD
ag.status = e.AdGroupStatusEnum.ENABLED
ag.optimized_targeting_enabled = False          # no audience expansion

for uid in AUDIENCES:
    crit = op().ad_group_criterion_operation.create
    crit.ad_group = ag_rn
    crit.status = e.AdGroupCriterionStatusEnum.ENABLED
    crit.user_list.user_list = f"customers/{CID}/userLists/{uid}"

ad = op().ad_group_ad_operation.create
ad.ad_group = ag_rn
ad.status = e.AdGroupAdStatusEnum.ENABLED
ad.ad.final_urls.append(STORE_URL)
rda = ad.ad.responsive_display_ad
for h in HEADLINES:
    a = client.get_type("AdTextAsset"); a.text = h; rda.headlines.append(a)
rda.long_headline.text = LONG_HEADLINE
for d in DESCRIPTIONS:
    a = client.get_type("AdTextAsset"); a.text = d; rda.descriptions.append(a)
for i in MARKETING:
    m = client.get_type("AdImageAsset"); m.asset = f"customers/{CID}/assets/{i}"
    rda.marketing_images.append(m)
for i in SQUARE:
    m = client.get_type("AdImageAsset"); m.asset = f"customers/{CID}/assets/{i}"
    rda.square_marketing_images.append(m)
rda.business_name = BUSINESS

ga = client.get_service("GoogleAdsService")
req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID
req.mutate_operations.extend(ops)
req.validate_only = not args.live
print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
print(f"  campaign  FUSA - Dynamic Display Remarketing  ${BUDGET_MICROS/1e6:,.0f}/day  PAUSED")
print(f"  geo       CA, AZ, TX, FL  PRESENCE")
print(f"  feed      {MERCHANT_ID}, scoped to {len(BRANDS)} brands")
print(f"  audiences {len(AUDIENCES)}   optimized_targeting=False")
print(f"  ad        {len(HEADLINES)} headlines, {len(DESCRIPTIONS)} descriptions, "
      f"{len(MARKETING)+len(SQUARE)} images")
try:
    ga.mutate(request=req)
    print("\n" + ("DONE" if args.live else "VALIDATED - nothing written"))
except Exception as ex:
    print("\nFAILED:"); print(str(ex)[:1800]); sys.exit(1)
