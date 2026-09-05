"""Build the Culinary Profis feed-only Performance Max campaign, one asset
group per brand, on the Fountains USA / Laser Engraver Store pattern.

Created PAUSED and left that way -- Trevor asked for the build only.

Brand selection. The feed holds 1,950 products across 86 brand values, but only
229 products can actually serve: 1,679 are out of stock and a few dozen have
landing page or attribute errors. Only 8 brands have serveable stock today.
Asset groups are built for the 14 brands that hold the catalogue -- the 8 with
stock now, plus the 6 largest currently out-of-stock brands -- so a restock is
covered automatically instead of needing a rebuild. An asset group whose
products are all out of stock simply does not serve; it costs nothing.

582 products carry no brand at all and fall into every group's "everything
else" bucket. Exactly one of them is currently serveable, so this costs almost
nothing today, but it is worth fixing in the feed.

Search themes are written per brand from what that brand actually sells,
checked against its product titles and types. These brands are not
interchangeable: mrcool is DIY mini-split HVAC, le griddle is outdoor gas
griddles, ankarsrum is consumer stand mixers, omcan is $32k commercial bakery
plant.

Dry run unless --live.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

MERCHANT_ID = 5595259630
BUDGET_MICROS = 15_000_000
STORE_URL = "https://www.culinaryprofis.com"
CAMPAIGN_NAME = "CP - PMax - Culinary (feed only)"

STATES = [21133, 21135, 21136, 21137, 21138, 21139, 21141, 21142, 21143, 21145,
          21146, 21147, 21148, 21149, 21150, 21151, 21152, 21153, 21154, 21155,
          21156, 21157, 21158, 21159, 21160, 21161, 21162, 21163, 21164, 21165,
          21166, 21167, 21168, 21169, 21170, 21171, 21172, 21173, 21174, 21175,
          21176, 21177, 21178, 21179, 21180, 21182, 21183, 21184]

NEGATIVE_LISTS = [(11765673294, "EP Generic"), (11890494955, "negative keyword")]

IN_MARKET = [(80884, "Food Service Equipment"), (80238, "Home Appliances"),
             (80259, "Refrigerators"), (80265, "Small Appliances"),
             (80915, "Cookware & Bakeware"), (80249, "Kitchen & Dining Room")]
AFFINITY = [(90800, "Cooking Enthusiasts")]
LIFE_EVENTS = [(95021, "Business Creation"), (95023, "Recently Started a Business")]
DETAILED = [(30024, "Hospitality Industry"), (30028, "Small Employer (1-249 Employees)")]
AUDIENCE_NAME = "CP - Kitchen & Food Service Buyers"

# (label, feed brand, total products, serveable today, search themes)
BRANDS = [
    ("Ankarsrum", "ankarsrum", 85, 61, [
        "ankarsrum mixer", "ankarsrum original mixer", "stand mixer for bread dough",
        "ankarsrum attachments", "pasta attachment for mixer",
        "best stand mixer for baking", "ankarsrum assistent", "7 quart stand mixer",
        "stand mixer for sourdough", "dough mixer for home baking",
        "ankarsrum mixer bowl", "grain mill attachment"]),
    ("Sunmix", "sunmix", 56, 40, [
        "sunmix spiral mixer", "spiral dough mixer", "sunmix evo",
        "bakery spiral mixer", "pizza dough mixer", "commercial spiral mixer",
        "dough divider rounder", "small batch spiral mixer",
        "spiral mixer for pizzeria", "countertop spiral dough mixer",
        "8 quart spiral mixer", "sunmix mixer"]),
    ("Sirman", "sirman", 97, 36, [
        "sirman meat slicer", "commercial meat slicer", "sirman spiral mixer",
        "14 inch meat slicer", "commercial food processor", "sirman hercules mixer",
        "commercial meat grinder", "panini grill commercial", "nsf meat slicer",
        "deli meat slicer commercial", "sirman dough mixer",
        "floor model dough mixer"]),
    ("BakeMax", "bakemax", 138, 29, [
        "bakemax", "bakemax dough moulder", "commercial bakery equipment",
        "dough moulder", "bakery dough sheeter", "commercial dough divider",
        "bakemax mixer", "bakery proofer", "commercial bread equipment",
        "dough rounder machine", "bakery mixer commercial", "bakemax oven"]),
    ("Omcan", "omcan", 25, 25, [
        "omcan", "omcan spiral mixer", "omcan meat slicer",
        "commercial dough sheeter", "omcan dough mixer", "belt driven meat slicer",
        "commercial dough divider", "omcan food equipment",
        "spiral dough mixer commercial", "dough rounder commercial",
        "omcan mixer", "restaurant food equipment"]),
    ("Pro-Cut", "pro-cut", 42, 21, [
        "pro-cut meat grinder", "commercial meat grinder", "meat band saw",
        "butcher band saw", "gear driven deli slicer", "number 12 meat grinder",
        "commercial deli slicer", "stainless steel meat grinder",
        "butcher shop equipment", "pro cut band saw", "heavy duty meat grinder",
        "meat processing equipment"]),
    ("Axis", "axis", 14, 14, [
        "axis planetary mixer", "20 qt planetary mixer",
        "commercial planetary mixer", "axis meat slicer", "floor model mixer",
        "3 speed planetary mixer", "commercial mixer with timer", "axis equipment",
        "countertop meat slicer", "40 qt planetary mixer",
        "bakery planetary mixer", "digital timer mixer"]),
    ("MRCOOL", "mrcool", 124, 0, [
        "mrcool diy mini split", "mini split air conditioner",
        "ductless mini split system", "mrcool", "diy mini split",
        "multi zone mini split", "18000 btu mini split", "mini split heat pump",
        "mrcool condenser", "ductless ac system", "mini split line set",
        "24k btu mini split"]),
    ("Avanti", "avanti", 108, 0, [
        "avanti refrigerator", "compact refrigerator", "avanti freezer",
        "garage ready refrigerator", "apartment size refrigerator",
        "avanti compact range", "vertical freezer", "20 inch gas range",
        "mini fridge with freezer", "avanti appliances",
        "convertible freezer refrigerator", "compact kitchen appliances"]),
    ("KingsBottle", "kingsbottle", 71, 0, [
        "kingsbottle wine fridge", "wine and beverage refrigerator",
        "dual zone wine cooler", "upright wine refrigerator",
        "glass door beverage cooler", "wine beverage combo fridge",
        "large wine refrigerator", "triple zone wine cooler", "kingsbottle",
        "built in wine cooler", "low e glass wine fridge",
        "47 inch wine refrigerator"]),
    ("IKON", "ikon", 70, 0, [
        "ikon commercial refrigerator", "reach in refrigerator",
        "sandwich prep table", "undercounter refrigerator commercial",
        "gas convection oven commercial", "glass door merchandiser",
        "commercial freezer reach in", "bottom mount refrigerator",
        "ikon refrigeration", "pizza prep table",
        "commercial kitchen refrigeration", "glass froster"]),
    ("Le Griddle", "le griddle", 59, 0, [
        "le griddle", "built in gas griddle", "outdoor gas griddle",
        "teppanyaki griddle outdoor", "le griddle texan",
        "freestanding griddle with cart", "41 inch griddle",
        "stainless steel outdoor griddle", "natural gas griddle built in",
        "propane outdoor griddle", "le griddle wee",
        "commercial outdoor griddle"]),
    ("Whynter", "whynter", 55, 0, [
        "whynter portable air conditioner", "portable air conditioner",
        "whynter wine refrigerator", "built in wine cooler",
        "33 bottle wine refrigerator", "undercounter beverage cooler",
        "whynter", "dual hose portable ac", "stainless steel wine fridge",
        "portable ac with heat", "beverage refrigerator built in",
        "whynter beverage cooler"]),
    ("Empura", "empura", 52, 0, [
        "empura commercial refrigerator", "commercial ice machine",
        "undercounter ice machine", "glass door merchandiser refrigerator",
        "air cooled ice machine", "commercial reach in refrigerator",
        "sliding glass door refrigerator", "full cube ice machine", "empura",
        "commercial refrigeration equipment", "swing door refrigerator",
        "restaurant refrigerator commercial"]),
]


def validate():
    bad = []
    for label, _, _, _, themes in BRANDS:
        if len(themes) > 25:
            bad.append(f"{label}: {len(themes)} themes exceeds 25")
        if len(set(themes)) != len(themes):
            bad.append(f"{label}: duplicate themes")
        for t in themes:
            if len(t) > 80:
                bad.append(f"{label}: theme too long: {t!r}")
    if bad:
        print("VALIDATION FAILED:")
        for b in bad:
            print("  " + b)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    validate()

    client = get_client()
    cust = resolve_account("Culinary Profis", client=client)["id"]
    e = client.enums
    ga = client.get_service("GoogleAdsService")

    if list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.id FROM campaign WHERE campaign.name = '{CAMPAIGN_NAME}'
          AND campaign.status != 'REMOVED'""")):
        print(f"{CAMPAIGN_NAME!r} already exists. Aborting.")
        return 1

    # Confirm every brand string still matches products in the feed.
    missing = []
    for label, fb, _, _, _ in BRANDS:
        n = len(list(ga.search(customer_id=cust, query=f"""
            SELECT shopping_product.title FROM shopping_product
            WHERE shopping_product.brand = '{fb}'""")))
        if n == 0:
            missing.append(f"{label} ({fb!r})")
    if missing:
        print(f"REFUSING: these brand strings match no products: {missing}")
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

    budget_rn = f"customers/{cust}/campaignBudgets/{nxt()}"
    b = op().campaign_budget_operation.create
    b.resource_name = budget_rn
    b.name = CAMPAIGN_NAME
    b.amount_micros = BUDGET_MICROS
    b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False

    camp_rn = f"customers/{cust}/campaigns/{nxt()}"
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
    for lid, _ in NEGATIVE_LISTS:
        cs = op().campaign_shared_set_operation.create
        cs.campaign = camp_rn
        cs.shared_set = f"customers/{cust}/sharedSets/{lid}"

    for label, feed_brand, _tot, _ok, _themes in BRANDS:
        ag_t = nxt()
        ag_rn = f"customers/{cust}/assetGroups/{ag_t}"
        ag = op().asset_group_operation.create
        ag.resource_name = ag_rn
        ag.campaign = camp_rn
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
    req.validate_only = not args.live

    print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
    print(f"  campaign  {CAMPAIGN_NAME}  ${BUDGET_MICROS/1e6:,.0f}/day  PAUSED")
    print(f"  merchant  {MERCHANT_ID}   geo lower 48 on PRESENCE")
    print(f"  negatives {[n for _, n in NEGATIVE_LISTS]}")
    print(f"\n  {'asset group':22} {'brand':16} {'products':>9} {'serveable':>10} themes")
    tot = ok = 0
    for label, fb, t, o, th in BRANDS:
        tot += t; ok += o
        print(f"  CP - {label:18} {fb!r:16} {t:>9} {o:>10} {len(th):>6}")
    print(f"  {'':22} {'':16} {tot:>9} {ok:>10}")
    print(f"\n  Feed holds 1,950 products; only 229 are serveable today "
          f"(1,679 out of stock).")

    ga.mutate(request=req)
    if not args.live:
        print("\nValidated OK. Re-run with --live to create.")
        return 0

    new = {r.asset_group.name: r.asset_group.id for r in ga.search(
        customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name FROM asset_group
        WHERE campaign.name = '{CAMPAIGN_NAME}'""")}
    print(f"\n  created campaign and {len(new)} asset groups")

    aud_op = client.get_type("AudienceOperation")
    aud = aud_op.create
    aud.name = AUDIENCE_NAME
    aud.description = ("Commercial kitchen, bakery and food service buyers plus "
                       "home cooking enthusiasts shopping for premium appliances.")
    dim = client.get_type("AudienceDimension")
    seg = dim.audience_segments
    for _id, _ in IN_MARKET + AFFINITY:
        s = client.get_type("AudienceSegment")
        s.user_interest.user_interest_category = f"customers/{cust}/userInterests/{_id}"
        seg.segments.append(s)
    for _id, _ in LIFE_EVENTS:
        s = client.get_type("AudienceSegment")
        s.life_event.life_event = f"customers/{cust}/lifeEvents/{_id}"
        seg.segments.append(s)
    for _id, _ in DETAILED:
        s = client.get_type("AudienceSegment")
        s.detailed_demographic.detailed_demographic = (
            f"customers/{cust}/detailedDemographics/{_id}")
        seg.segments.append(s)
    aud.dimensions.append(dim)
    audience_rn = client.get_service("AudienceService").mutate_audiences(
        customer_id=cust, operations=[aud_op]).results[0].resource_name
    print(f"  created audience {audience_rn}")

    ag_svc = client.get_service("AssetGroupService")
    sig_ops = []
    for label, _fb, _t, _o, themes in BRANDS:
        ag_rn = ag_svc.asset_group_path(cust, new[f"CP - {label}"])
        o = client.get_type("AssetGroupSignalOperation")
        o.create.asset_group = ag_rn
        o.create.audience.audience = audience_rn
        sig_ops.append(o)
        for t in themes:
            o = client.get_type("AssetGroupSignalOperation")
            o.create.asset_group = ag_rn
            o.create.search_theme.text = t
            sig_ops.append(o)
    client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
        customer_id=cust, operations=sig_ops)
    print(f"  created {len(sig_ops)} signals "
          f"({len(BRANDS)} audience + {sum(len(b[4]) for b in BRANDS)} themes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
