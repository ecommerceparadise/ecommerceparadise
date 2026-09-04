"""Build the Laser Engraver Store retargeting pair, mirroring Fountains USA.

  1. LES - Display Remarketing   -- desktop only, Manual CPC $1.00, $5/day
  2. LES - Shopping - Retargeting Only -- Manual CPC $2.00, $5/day, priority
     HIGH, serving restricted to remarketing lists, all brands per Trevor

Both created PAUSED, and they should stay that way for now. The account's
remarketing lists are nearly empty -- the largest is 150 users on Search and 88
on Display, and General visitors, Product viewers and Shopping cart abandoners
are all at ZERO. Display needs 100 users to serve and Shopping needs 1,000 on
Search. Neither campaign can deliver until traffic rebuilds those lists, which
is why they are built now and enabled later rather than enabled now.

The display ad uses the three assets already prepared in this account and named
for the purpose (LES RT Land / Square / Logo). Every claim in the ad copy is
one the account already runs.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

MERCHANT_ID = 5823754958
STORE_URL = "https://laserengraverstore.com"
DISPLAY_NAME = "LES - Display Remarketing"
SHOPPING_NAME = "LES - Shopping - Retargeting Only"
DISPLAY_BUDGET, SHOPPING_BUDGET = 5_000_000, 5_000_000
DISPLAY_CPC, SHOPPING_CPC = 1_000_000, 2_000_000

STATES = [21133, 21135, 21136, 21137, 21138, 21139, 21141, 21142, 21143, 21145,
          21146, 21147, 21148, 21149, 21150, 21151, 21152, 21153, 21154, 21155,
          21156, 21157, 21158, 21159, 21160, 21161, 21162, 21163, 21164, 21165,
          21166, 21167, 21168, 21169, 21170, 21171, 21172, 21173, 21174, 21175,
          21176, 21177, 21178, 21179, 21180, 21182, 21183, 21184]

AUDIENCES = [
    (9437405836, "AdWords optimized list", 150),
    (9437317696, "All visitors (AdWords)", 150),
    (9454938191, "General visitors (Retail)", 0),
    (9454938194, "Product viewers (Retail)", 0),
    (9454938197, "Shopping cart abandoners (Retail)", 0),
]

NEGATIVE_LISTS = [(11765673294, "EP Generic"), (12165888848, "LES Universal Negatives")]

IMG_LANDSCAPE, IMG_SQUARE, IMG_LOGO = 398348002945, 398348002948, 398348002951

HEADLINES = ["Laser Engravers & Cutters", "Authorized Dealer Pricing",
             "Fiber, CO2, Diode & UV", "Free Shipping Lower 48",
             "Talk To A Specialist"]
LONG_HEADLINE = "Fiber, MOPA, CO2, diode and UV laser engravers from an authorized dealer."
DESCRIPTIONS = [
    "Authorized dealer for Gweike, Monport, Sculpfun and more. Free shipping to the lower 48.",
    "Compare fiber, CO2, diode and UV laser engravers. Talk to a specialist before you buy.",
    "Machines for metal marking, wood, acrylic and glass. Get a free quote today.",
]
BUSINESS_NAME = "Laser Engraver Store"
EXCLUDE_DEVICES = ["MOBILE", "TABLET", "CONNECTED_TV"]


def check_lengths():
    bad = [f"headline {len(h)}>30: {h!r}" for h in HEADLINES if len(h) > 30]
    bad += [f"description {len(d)}>90: {d!r}" for d in DESCRIPTIONS if len(d) > 90]
    if len(LONG_HEADLINE) > 90:
        bad.append(f"long headline {len(LONG_HEADLINE)}>90")
    if len(BUSINESS_NAME) > 25:
        bad.append(f"business name {len(BUSINESS_NAME)}>25")
    if bad:
        print("VALIDATION FAILED:")
        for b in bad:
            print("  " + b)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    check_lengths()

    client = get_client()
    cust = resolve_account("Laser Engraver Store")["id"]
    e = client.enums
    ga = client.get_service("GoogleAdsService")

    for name in (DISPLAY_NAME, SHOPPING_NAME):
        if list(ga.search(customer_id=cust, query=f"""
            SELECT campaign.id FROM campaign WHERE campaign.name = '{name}'
              AND campaign.status != 'REMOVED'""")):
            print(f"{name!r} already exists. Aborting.")
            return 1

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\n{DISPLAY_NAME}  [PAUSED]  ${DISPLAY_BUDGET/1e6:.2f}/day")
    print(f"  Manual CPC ${DISPLAY_CPC/1e6:.2f}, desktop only "
          f"({', '.join(EXCLUDE_DEVICES)} excluded)")
    print(f"  responsive display ad: {len(HEADLINES)} headlines, "
          f"{len(DESCRIPTIONS)} descriptions, 3 images")
    print(f"\n{SHOPPING_NAME}  [PAUSED]  ${SHOPPING_BUDGET/1e6:.2f}/day")
    print(f"  Manual CPC ${SHOPPING_CPC/1e6:.2f}, priority HIGH, all brands")
    print(f"  AUDIENCE restriction bid_only=False (serves only to the lists)")
    print(f"\nAudiences on both:")
    for i, n, s in AUDIENCES:
        warn = "  <-- EMPTY, cannot serve yet" if s == 0 else ""
        print(f"    {i}  {n[:38]:40} {s:>5} on Search{warn}")
    print(f"\nNegatives on both: {[n for _, n in NEGATIVE_LISTS]}")
    print(f"Geo on both: lower 48 ({len(STATES)} states) on PRESENCE")

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

    def common(camp_rn):
        for g in STATES:
            cc = op().campaign_criterion_operation.create
            cc.campaign = camp_rn
            cc.location.geo_target_constant = f"geoTargetConstants/{g}"
        for lid, _ in NEGATIVE_LISTS:
            cs = op().campaign_shared_set_operation.create
            cs.campaign = camp_rn
            cs.shared_set = f"customers/{cust}/sharedSets/{lid}"

    # ---------- 1. display remarketing ----------
    db_rn = f"customers/{cust}/campaignBudgets/{nxt()}"
    b = op().campaign_budget_operation.create
    b.resource_name = db_rn
    b.name = DISPLAY_NAME
    b.amount_micros = DISPLAY_BUDGET
    b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False

    dc_rn = f"customers/{cust}/campaigns/{nxt()}"
    c = op().campaign_operation.create
    c.resource_name = dc_rn
    c.name = DISPLAY_NAME
    c.status = e.CampaignStatusEnum.PAUSED
    c.advertising_channel_type = e.AdvertisingChannelTypeEnum.DISPLAY
    c.campaign_budget = db_rn
    c.manual_cpc.enhanced_cpc_enabled = False
    c.contains_eu_political_advertising = (
        e.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    c.geo_target_type_setting.positive_geo_target_type = e.PositiveGeoTargetTypeEnum.PRESENCE
    common(dc_rn)
    for d in EXCLUDE_DEVICES:
        cc = op().campaign_criterion_operation.create
        cc.campaign = dc_rn
        cc.device.type_ = getattr(e.DeviceEnum, d)
        cc.bid_modifier = 0.0

    dag_rn = f"customers/{cust}/adGroups/{nxt()}"
    ag = op().ad_group_operation.create
    ag.resource_name = dag_rn
    ag.name = "LES - Returning Visitors"
    ag.campaign = dc_rn
    ag.status = e.AdGroupStatusEnum.ENABLED
    ag.type_ = e.AdGroupTypeEnum.DISPLAY_STANDARD
    ag.cpc_bid_micros = DISPLAY_CPC
    for uid, _, _ in AUDIENCES:
        k = op().ad_group_criterion_operation.create
        k.ad_group = dag_rn
        k.status = e.AdGroupCriterionStatusEnum.ENABLED
        k.user_list.user_list = f"customers/{cust}/userLists/{uid}"

    ada = op().ad_group_ad_operation.create
    ada.ad_group = dag_rn
    ada.status = e.AdGroupAdStatusEnum.ENABLED
    ada.ad.final_urls.append(STORE_URL)
    rda = ada.ad.responsive_display_ad
    for h in HEADLINES:
        a = client.get_type("AdTextAsset")
        a.text = h
        rda.headlines.append(a)
    rda.long_headline.text = LONG_HEADLINE
    for d in DESCRIPTIONS:
        a = client.get_type("AdTextAsset")
        a.text = d
        rda.descriptions.append(a)
    rda.business_name = BUSINESS_NAME
    for aid, field in ((IMG_LANDSCAPE, rda.marketing_images),
                       (IMG_SQUARE, rda.square_marketing_images),
                       (IMG_LOGO, rda.square_logo_images)):
        img = client.get_type("AdImageAsset")
        img.asset = f"customers/{cust}/assets/{aid}"
        field.append(img)

    # ---------- 2. retargeting shopping ----------
    sb_rn = f"customers/{cust}/campaignBudgets/{nxt()}"
    b = op().campaign_budget_operation.create
    b.resource_name = sb_rn
    b.name = SHOPPING_NAME
    b.amount_micros = SHOPPING_BUDGET
    b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False

    sc_rn = f"customers/{cust}/campaigns/{nxt()}"
    c = op().campaign_operation.create
    c.resource_name = sc_rn
    c.name = SHOPPING_NAME
    c.status = e.CampaignStatusEnum.PAUSED
    c.advertising_channel_type = e.AdvertisingChannelTypeEnum.SHOPPING
    c.campaign_budget = sb_rn
    c.manual_cpc.enhanced_cpc_enabled = False
    c.shopping_setting.merchant_id = MERCHANT_ID
    c.shopping_setting.campaign_priority = 2
    c.contains_eu_political_advertising = (
        e.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    c.geo_target_type_setting.positive_geo_target_type = e.PositiveGeoTargetTypeEnum.PRESENCE
    common(sc_rn)

    sag_rn = f"customers/{cust}/adGroups/{nxt()}"
    ag = op().ad_group_operation.create
    ag.resource_name = sag_rn
    ag.name = "LES - Returning Visitors"
    ag.campaign = sc_rn
    ag.status = e.AdGroupStatusEnum.ENABLED
    ag.type_ = e.AdGroupTypeEnum.SHOPPING_PRODUCT_ADS
    ag.cpc_bid_micros = SHOPPING_CPC
    tr = client.get_type("TargetRestriction")
    tr.targeting_dimension = e.TargetingDimensionEnum.AUDIENCE
    tr.bid_only = False
    ag.targeting_setting.target_restrictions.append(tr)

    sada = op().ad_group_ad_operation.create
    sada.ad_group = sag_rn
    sada.status = e.AdGroupAdStatusEnum.ENABLED
    sada.ad.shopping_product_ad._pb.SetInParent()

    lg = op().ad_group_criterion_operation.create
    lg.ad_group = sag_rn
    lg.status = e.AdGroupCriterionStatusEnum.ENABLED
    lg.listing_group.type_ = e.ListingGroupTypeEnum.UNIT
    lg.cpc_bid_micros = SHOPPING_CPC
    for uid, _, _ in AUDIENCES:
        k = op().ad_group_criterion_operation.create
        k.ad_group = sag_rn
        k.status = e.AdGroupCriterionStatusEnum.ENABLED
        k.user_list.user_list = f"customers/{cust}/userLists/{uid}"

    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = cust
    req.mutate_operations.extend(ops)
    resp = ga.mutate(request=req)
    print(f"\n  {len(ops)} operations applied")
    for r in resp.mutate_operation_responses:
        for f in ("campaign_result", "ad_group_result", "ad_group_ad_result"):
            if r._pb.HasField(f):
                print(f"    {getattr(r, f).resource_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
