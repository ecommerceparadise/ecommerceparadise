"""Build the HVAC Saver dynamic remarketing Display campaign -- PAUSED and on hold.

Trevor, 30 September 2026, choosing between options after I reported the
blockers: "Build dynamic, paused, hold until feed fixed."

READ THIS BEFORE ENABLING. The campaign is deliberately un-enableable as things
stand, for one reason:

    A Display dynamic remarketing campaign CANNOT be filtered by brand.

Verified empirically rather than assumed: across BetterPatio's ten Display
campaigns that have a Merchant Center feed attached, not one carries a
LISTING_GROUP criterion. Display campaigns target by USER_LIST, KEYWORD, TOPIC,
AGE_RANGE, USER_INTEREST, CUSTOM_INTENT and YOUTUBE_CHANNEL -- there is no
product partition. Product selection in a dynamic ad comes from the feed plus
what the visitor browsed.

HVAC Saver's feed carries ONE feed label, 'US', holding goodman 453 AND
daikin 103 together. The client asked for Goodman only, never Daikin. So the
moment this campaign is enabled, a visitor who browsed a Daikin condenser gets
shown that Daikin condenser. That breaks the client's instruction.

Two things must be true before this may be enabled:

  1. Merchant Center carries a GOODMAN-ONLY feed label (a supplemental feed or
     feed rule), and this campaign's shopping_setting.feed_label points at it.
  2. The product-level remarketing lists are populating. Right now, after 1,205
     clicks in September, 'Product viewers', 'Shopping cart abandoners' and
     'Past buyers' all read ZERO while 'General visitors' reads 2,600 -- the
     page-level tag fires but the retail tag is not passing product IDs. Dynamic
     remarketing has nothing to be dynamic about until that is fixed on
     hvacsaver.com.

The campaign name carries the hold so nobody enables it from the UI by accident.

Creative is taken from the retired Goodman PMax asset group, which is
Goodman-specific by construction -- picking images out of the account's
227-asset library at random could easily have surfaced a Daikin unit. The
time-sensitive and discount-specific copy from that group is deliberately left
out: 'Flash Sale Ending In 48 Hours', 'Save Over $3,000 Off Goodman',
'Goodman Sale $1,000 Off', 'Call For A Discount Code' and the 12%-off lines
would be stale or unverifiable claims on an evergreen remarketing ad.

Created PAUSED at $10/day, matching the account's PMax budget. DISPLAY does not
expose the asset automation settings, so the standing opt-out rule does not
apply here.

Run with no flags for a dry run. Pass --execute to build.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "Hvacsaver"
CAMPAIGN_NAME = ("HS - Display Dynamic Remarketing "
                 "(HOLD - do not enable, Daikin in feed)")
BUDGET_NAME = "HS - Display Dynamic Remarketing"
DAILY_BUDGET = 10.0
MERCHANT_ID = 5828411191
FINAL_URL = "https://hvacsaver.com/"

# US, minus the three regions every other campaign in this account excludes.
GEO_POSITIVE = ["geoTargetConstants/2840"]
GEO_NEGATIVE = ["geoTargetConstants/21132",   # Alaska
                "geoTargetConstants/21144",   # Hawaii
                "geoTargetConstants/2630"]    # Puerto Rico

# One ad group per intent tier. The two high-intent lists are empty today; the
# groups exist so the structure is right the moment the retail tag is fixed.
TIERS = [
    ("HS RMK - Cart Abandoners", [9462981685]),
    ("HS RMK - Product Viewers", [9462981682]),
    ("HS RMK - General Visitors", [9462981679, 9446667478]),
]

BUSINESS_NAME = "HVAC Saver"
HEADLINES = [                      # RDA cap: 30 chars each, 5 max
    "No Sales Tax + Free Shipping",
    "Packaged & Ready To Ship",
    "Experts Ready To Talk",
    "Questions? Call Or Live Chat",
    "Wholesale Cost To The Public",
]
LONG_HEADLINE = ("No BS No Hassle. Official Goodman Systems and Experts "
                 "Readily Available Over The Phone.")     # cap 90
DESCRIPTIONS = [                   # cap 90 each, 5 max
    "One-Stop-Shop For Goodman HVAC Systems. Wholesale Pricing Given To The Public.",
    "Over 20+ Years Of HVAC Experience. We've Got You Covered.",
    "Wholesale Pricing Given To The General Public. Lowest Pricing Guarantee.",
]
MARKETING_IMAGES = [414544655669, 414722948424, 414723360528]   # 1.91:1
SQUARE_IMAGES = [414544436516, 414722854524, 414722876106]      # 1:1
SQUARE_LOGO = 401096145060                                      # 1024x1024

HEADLINE_MAX, DESC_MAX, LONG_MAX, BIZ_MAX = 30, 90, 90, 25


def validate():
    bad = []
    if len(HEADLINES) > 5 or len(set(HEADLINES)) != len(HEADLINES):
        bad.append(f"{len(HEADLINES)} headlines, {len(set(HEADLINES))} unique")
    for h in HEADLINES:
        if len(h) > HEADLINE_MAX:
            bad.append(f"headline {len(h)} chars: {h!r}")
    if len(DESCRIPTIONS) > 5 or len(set(DESCRIPTIONS)) != len(DESCRIPTIONS):
        bad.append("description count/uniqueness")
    for d in DESCRIPTIONS:
        if len(d) > DESC_MAX:
            bad.append(f"description {len(d)} chars: {d!r}")
    if len(LONG_HEADLINE) > LONG_MAX:
        bad.append(f"long headline {len(LONG_HEADLINE)} chars")
    if len(BUSINESS_NAME) > BIZ_MAX:
        bad.append(f"business name {len(BUSINESS_NAME)} chars")
    if bad:
        print("VALIDATION FAILED:")
        for b in bad:
            print("  " + b)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    validate()
    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    dupes = [r.campaign.id for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.name FROM campaign
        WHERE campaign.name = '{CAMPAIGN_NAME}' AND campaign.status != 'REMOVED'""")]
    if dupes:
        print(f"ABORT: {CAMPAIGN_NAME!r} already exists: {dupes}")
        return 1

    # Every asset referenced must exist and be the right shape.
    want = set(MARKETING_IMAGES) | set(SQUARE_IMAGES) | {SQUARE_LOGO}
    got = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT asset.id, asset.type, asset.image_asset.full_size.width_pixels,
               asset.image_asset.full_size.height_pixels FROM asset
        WHERE asset.type = 'IMAGE'"""):
        if r.asset.id in want:
            got[r.asset.id] = (r.asset.image_asset.full_size.width_pixels,
                               r.asset.image_asset.full_size.height_pixels)
    missing = want - set(got)
    if missing:
        print(f"ABORT: image assets not found: {sorted(missing)}")
        return 1
    shape_bad = []
    for i in MARKETING_IMAGES:
        w, h = got[i]
        if abs(w / h - 1.91) > 0.02:
            shape_bad.append(f"{i} is {w}x{h} (ratio {w/h:.3f}), need 1.91:1")
    for i in list(SQUARE_IMAGES) + [SQUARE_LOGO]:
        w, h = got[i]
        if abs(w / h - 1.0) > 0.02:
            shape_bad.append(f"{i} is {w}x{h} (ratio {w/h:.3f}), need 1:1")
    if shape_bad:
        print("ABORT: image aspect ratios wrong:")
        for s in shape_bad:
            print("  " + s)
        return 1

    lists = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT user_list.id, user_list.name, user_list.size_for_display,
               user_list.eligible_for_display FROM user_list"""):
        lists[r.user_list.id] = (r.user_list.name,
                                 r.user_list.size_for_display,
                                 r.user_list.eligible_for_display)
    need = {l for _, ls in TIERS for l in ls}
    if need - set(lists):
        print(f"ABORT: user lists not found: {sorted(need - set(lists))}")
        return 1

    print("=" * 76)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 76)
    print(f"\naccount {ACCOUNT} [{cust}]")
    print(f"campaign {CAMPAIGN_NAME!r}")
    print(f"  DISPLAY   PAUSED   ${DAILY_BUDGET:.2f}/day   "
          f"MAXIMIZE_CONVERSIONS, no target CPA")
    print(f"  dynamic feed: merchant_id {MERCHANT_ID}")
    print( "  geo: US minus Alaska / Hawaii / Puerto Rico, PRESENCE")
    print( "  goals: inherited from the account (Purchase / Website)")

    print("\nAD GROUPS")
    for nm, ls in TIERS:
        print(f"  {nm}")
        for l in ls:
            name, size, elig = lists[l]
            warn = "   <-- EMPTY, cannot serve until the retail tag is fixed" \
                if size < 100 else ""
            print(f"      [{l}] display={size:>6,} elig={elig}  {name!r}{warn}")

    print(f"\nRESPONSIVE DISPLAY AD (one per ad group)")
    print(f"  business_name {BUSINESS_NAME!r}")
    print(f"  long_headline {LONG_HEADLINE!r}")
    for h in HEADLINES:
        print(f"    headline    ({len(h):>2}) {h!r}")
    for d in DESCRIPTIONS:
        print(f"    description ({len(d):>2}) {d!r}")
    print(f"  marketing images {[f'{i} {got[i][0]}x{got[i][1]}' for i in MARKETING_IMAGES]}")
    print(f"  square images    {[f'{i} {got[i][0]}x{got[i][1]}' for i in SQUARE_IMAGES]}")
    print(f"  square logo      {SQUARE_LOGO} {got[SQUARE_LOGO][0]}x{got[SQUARE_LOGO][1]}")
    print(f"  final url        {FINAL_URL}")

    print("\n" + "!" * 76)
    print("HOLD: do NOT enable this campaign until BOTH are true --")
    print("  1. Merchant Center has a Goodman-only feed label and this")
    print("     campaign points at it. Display has no brand filter, so as")
    print("     things stand a Daikin browser would be shown Daikin.")
    print("  2. Product viewers / cart abandoners are populating (all 0 today).")
    print("!" * 76)

    if not args.execute:
        print("\nDry run. Re-run with --execute to build.")
        return 0

    bop = client.get_type("CampaignBudgetOperation")
    b = bop.create
    b.name = f"{BUDGET_NAME} {int(DAILY_BUDGET)}"
    b.amount_micros = int(DAILY_BUDGET * 1e6)
    b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False
    budget_rn = client.get_service("CampaignBudgetService").mutate_campaign_budgets(
        customer_id=cust, operations=[bop]).results[0].resource_name
    print(f"\n  budget {budget_rn}")

    cop = client.get_type("CampaignOperation")
    c = cop.create
    c.name = CAMPAIGN_NAME
    c.advertising_channel_type = e.AdvertisingChannelTypeEnum.DISPLAY
    c.status = e.CampaignStatusEnum.PAUSED
    c.campaign_budget = budget_rn
    c.bidding_strategy_type = e.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSIONS
    c.maximize_conversions.target_cpa_micros = 0
    c.shopping_setting.merchant_id = MERCHANT_ID
    c.geo_target_type_setting.positive_geo_target_type = (
        e.PositiveGeoTargetTypeEnum.PRESENCE)
    c.geo_target_type_setting.negative_geo_target_type = (
        e.NegativeGeoTargetTypeEnum.PRESENCE)
    c.contains_eu_political_advertising = (
        e.EuPoliticalAdvertisingStatusEnum
        .DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    camp_rn = client.get_service("CampaignService").mutate_campaigns(
        customer_id=cust, operations=[cop]).results[0].resource_name
    camp_id = int(camp_rn.split("/")[-1])
    print(f"  campaign {camp_rn}  (PAUSED)")

    geo_ops = []
    for g in GEO_POSITIVE + GEO_NEGATIVE:
        o = client.get_type("CampaignCriterionOperation")
        o.create.campaign = camp_rn
        o.create.location.geo_target_constant = g
        o.create.negative = g in GEO_NEGATIVE
        geo_ops.append(o)
    client.get_service("CampaignCriterionService").mutate_campaign_criteria(
        customer_id=cust, operations=geo_ops)
    print(f"  {len(GEO_POSITIVE)} positive + {len(GEO_NEGATIVE)} negative locations")

    ag_svc = client.get_service("AdGroupService")
    ag_ops = []
    for nm, _ in TIERS:
        o = client.get_type("AdGroupOperation")
        a = o.create
        a.name = nm
        a.campaign = camp_rn
        a.type_ = e.AdGroupTypeEnum.DISPLAY_STANDARD
        a.status = e.AdGroupStatusEnum.ENABLED
        ag_ops.append(o)
    ag_rns = [r.resource_name for r in ag_svc.mutate_ad_groups(
        customer_id=cust, operations=ag_ops).results]
    made = dict(zip([nm for nm, _ in TIERS], ag_rns))
    print(f"  {len(ag_rns)} ad groups")

    crit_ops = []
    for nm, ls in TIERS:
        for l in ls:
            o = client.get_type("AdGroupCriterionOperation")
            cr = o.create
            cr.ad_group = made[nm]
            cr.user_list.user_list = f"customers/{cust}/userLists/{l}"
            cr.status = e.AdGroupCriterionStatusEnum.ENABLED
            crit_ops.append(o)
    client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(
        customer_id=cust, operations=crit_ops)
    print(f"  {len(crit_ops)} user list criteria")

    def asset_rn(i):
        return f"customers/{cust}/assets/{i}"

    ad_ops = []
    for nm, _ in TIERS:
        o = client.get_type("AdGroupAdOperation")
        a = o.create
        a.ad_group = made[nm]
        a.status = e.AdGroupAdStatusEnum.ENABLED
        a.ad.final_urls.append(FINAL_URL)
        rd = a.ad.responsive_display_ad
        rd.business_name = BUSINESS_NAME
        rd.long_headline.text = LONG_HEADLINE
        for h in HEADLINES:
            t = client.get_type("AdTextAsset")
            t.text = h
            rd.headlines.append(t)
        for d in DESCRIPTIONS:
            t = client.get_type("AdTextAsset")
            t.text = d
            rd.descriptions.append(t)
        for i in MARKETING_IMAGES:
            im = client.get_type("AdImageAsset")
            im.asset = asset_rn(i)
            rd.marketing_images.append(im)
        for i in SQUARE_IMAGES:
            im = client.get_type("AdImageAsset")
            im.asset = asset_rn(i)
            rd.square_marketing_images.append(im)
        im = client.get_type("AdImageAsset")
        im.asset = asset_rn(SQUARE_LOGO)
        rd.square_logo_images.append(im)
        ad_ops.append(o)
    client.get_service("AdGroupAdService").mutate_ad_group_ads(
        customer_id=cust, operations=ad_ops)
    print(f"  {len(ad_ops)} responsive display ads (with logo)")

    print("\n--- read-back ---")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.name, campaign.status, campaign.primary_status,
               campaign.advertising_channel_type,
               campaign.shopping_setting.merchant_id,
               campaign_budget.amount_micros
        FROM campaign WHERE campaign.id = {camp_id}"""):
        print(f"  [{r.campaign.id}] {r.campaign.status.name} "
              f"{r.campaign.advertising_channel_type.name} "
              f"${r.campaign_budget.amount_micros/1e6:.2f}/d "
              f"mc={r.campaign.shopping_setting.merchant_id} "
              f"primary={r.campaign.primary_status.name}")
        print(f"      {r.campaign.name!r}")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.id, ad_group.name, ad_group.status, campaign.id
        FROM ad_group WHERE campaign.id = {camp_id} ORDER BY ad_group.name"""):
        gid = r.ad_group.id
        ls = [lists[int(x.ad_group_criterion.user_list.user_list.split("/")[-1])]
              for x in ga.search(customer_id=cust, query=f"""
            SELECT ad_group_criterion.user_list.user_list, ad_group.id
            FROM ad_group_criterion WHERE ad_group.id = {gid}
              AND ad_group_criterion.type = 'USER_LIST'""")]
        ads = [(x.ad_group_ad.ad.id,
                len(x.ad_group_ad.ad.responsive_display_ad.square_logo_images))
               for x in ga.search(customer_id=cust, query=f"""
            SELECT ad_group_ad.ad.id,
                   ad_group_ad.ad.responsive_display_ad.square_logo_images,
                   ad_group.id
            FROM ad_group_ad WHERE ad_group.id = {gid}""")]
        print(f"\n  {r.ad_group.name!r} {r.ad_group.status.name}")
        for name, size, _ in ls:
            print(f"      list {size:>6,}  {name!r}")
        for aid, logos in ads:
            print(f"      ad {aid} logos={logos}")
    print(f"\nBuilt PAUSED. Campaign id {camp_id}. ON HOLD -- see the banner above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
