"""Build the feed-only PMax campaign for HVAC Saver (hvacsaver.com).

House pattern, same as FUSA / LES / CP: ONE Performance Max campaign, one asset
group per brand that clears the product threshold, each carrying a brand
listing filter and NO text, image, logo or video assets. Ad strength reads POOR
and the group still serves -- from the feed. A catch-all group excludes every
brand handled elsewhere and includes everything else, so brands added to the
feed later are picked up without a rebuild.

Account notes found during the audit on 2026-09-29:

* All 31 pre-existing campaigns are PAUSED, so every product in Merchant Center
  reports `not_eligible_in_any_campaign` ("No campaigns advertising this
  product"). That is a consequence of nothing being enabled, not a feed fault,
  so it is ignored when judging which products are servable.
* Three earlier PMax attempts exist (`Feed Only | Goodman`, `Goodman Feed Only`,
  `Goodman`), all paused, all Goodman-only, none covering Daikin. They are left
  alone -- never delete, and they are already paused.
* Geo convention in this account is US minus Alaska, Hawaii and Puerto Rico
  (21 of 24 live campaigns), which suits freight on this equipment. Replicated
  here, with PRESENCE targeting.
* Conversion goals are deliberately NOT set at campaign level so the campaign
  inherits the account goal (Purchase / Website, the only biddable one).

Created PAUSED. All five asset automations are opted out at creation time.
Run with no flags for a dry run. Pass --execute to build.
"""
import argparse
import sys
from collections import Counter

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "Hvacsaver"
CAMPAIGN_NAME = "HS - PMax - HVAC (feed only)"
BUDGET_NAME = "HS - PMax - HVAC (feed only)"
CATCHALL = "HS - All Other Brands"
FINAL_URL = "https://hvacsaver.com/"
OWN_GROUP_MIN = 20
AUDIENCE_NAME = "HS - HVAC System Buyers"

# US, minus the three regions every other campaign in this account excludes.
GEO_POSITIVE = ["geoTargetConstants/2840"]                      # United States
GEO_NEGATIVE = ["geoTargetConstants/21132",                     # Alaska
                "geoTargetConstants/21144",                     # Hawaii
                "geoTargetConstants/2630"]                      # Puerto Rico

# PMax exposes all five. CLAUDE.md standing rule: these stay OFF, always.
AUTOMATIONS_OFF = [
    "FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION",
    "TEXT_ASSET_AUTOMATION",
    "GENERATE_IMAGE_EXTRACTION",
    "GENERATE_IMAGE_ENHANCEMENT",
    "GENERATE_ENHANCED_YOUTUBE_VIDEOS",
]

# Homeowners replacing a system, people mid-renovation or just moved in, and
# the contractors and small installers who buy this equipment for jobs.
IN_MARKET = [
    (80241, "Home Improvement"),
    (80237, "Home & Garden"),
    (80898, "Air Conditioners"),
    (80238, "Home Appliances"),
    (80490, "General Contracting & Remodeling Services"),
    (80483, "Home & Garden Services"),
    (80883, "Business & Industrial Products"),
]
AFFINITY = [(92946, "Home & Garden")]
LIFE_EVENTS = [
    (95015, "Home Renovation"),
    (95017, "Renovating Home Soon"),
    (95034, "Recently Purchased a Home"),
    (95032, "Purchasing a Home"),
]
DETAILED_DEMOGRAPHICS = [
    (30007, "Homeowners"),
    (30027, "Construction Industry"),
]

# Written from the product types actually in the feed: AC & furnace systems,
# evaporator coils, gas furnaces, condensers, air handlers, and Daikin's
# 1-4 zone ductless mini splits.
THEMES = {
    "goodman": [
        "goodman air conditioner", "goodman ac unit", "goodman furnace",
        "goodman heat pump", "goodman hvac system",
        "ac and furnace system", "complete hvac system",
        "14.5 seer2 air conditioner", "r32 ac split system",
        "gas furnace 92 afue", "evaporator coil replacement",
        "ac condenser unit", "heat pump and air handler system",
        "central air conditioner replacement", "split system air conditioner",
        "upflow gas furnace", "hvac replacement system",
        "3 ton ac unit", "goodman condenser", "ac and coil combo",
    ],
    "daikin": [
        "daikin mini split", "daikin ductless mini split",
        "daikin heat pump", "daikin air conditioner",
        "ductless mini split system", "multi zone mini split",
        "2 zone mini split", "3 zone mini split", "4 zone mini split",
        "single zone ductless mini split", "18 seer2 mini split",
        "9000 btu mini split", "ductless heat pump system",
        "wall mounted mini split", "daikin entra series",
        "mini split air conditioner and heater", "inverter mini split",
        "ductless ac installation", "daikin hvac", "mini split with heat",
    ],
}
SEARCH_THEME_MAX, THEMES_PER_GROUP_MAX = 80, 25


def group_name(brand):
    return f"HS - {brand.title()}"


def validate():
    bad = []
    for b, themes in THEMES.items():
        if len(themes) > THEMES_PER_GROUP_MAX:
            bad.append(f"{b}: {len(themes)} themes exceeds {THEMES_PER_GROUP_MAX}")
        if len(set(themes)) != len(themes):
            bad.append(f"{b}: duplicate themes")
        for t in themes:
            if len(t) > SEARCH_THEME_MAX or not t.strip() or t != t.strip():
                bad.append(f"{b}: bad theme {t!r}")
    if bad:
        print("VALIDATION FAILED:")
        for x in bad:
            print("  " + x)
        sys.exit(1)


def servable_brands(ga, cust):
    """Brand -> product count, ignoring the account-wide 'no campaigns' error.

    Every campaign in this account is paused, so all 562 products carry
    `not_eligible_in_any_campaign`. That error says nothing about the product,
    so it is discounted; any OTHER error (a broken landing page, say) does
    disqualify the product.
    """
    ok, skipped = Counter(), Counter()
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.issues,
               shopping_product.availability
        FROM shopping_product"""):
        p = r.shopping_product
        real = {i.error_code for i in p.issues} - {"not_eligible_in_any_campaign",
                                                   "low_manual_bids"}
        b = (p.brand or "").strip().lower()
        if real:
            skipped[tuple(sorted(real))] += 1
            continue
        ok[b] += 1
    return ok, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--budget", type=float, default=10.0,
                    help="daily budget in dollars (campaign is created PAUSED)")
    args = ap.parse_args()

    validate()
    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    dupes = [r.campaign.id for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id FROM campaign
        WHERE campaign.name = '{CAMPAIGN_NAME}' AND campaign.status != 'REMOVED'""")]
    if dupes:
        print(f"ABORT: {CAMPAIGN_NAME!r} already exists: {dupes}. "
              "Nothing built -- this script only creates.")
        return 1

    mcs = {r.campaign.shopping_setting.merchant_id
           for r in ga.search(customer_id=cust, query="""
        SELECT campaign.shopping_setting.merchant_id FROM campaign
        WHERE campaign.shopping_setting.merchant_id > 0""")}
    if len(mcs) != 1:
        print(f"ABORT: expected exactly one Merchant Center id, found {mcs}")
        return 1
    mc = mcs.pop()

    ok, skipped = servable_brands(ga, cust)
    own = [(b, n) for b, n in ok.most_common() if b and n >= OWN_GROUP_MIN]
    other = [(b, n) for b, n in ok.most_common()
             if (not b or n < OWN_GROUP_MIN)]
    missing_themes = [b for b, _ in own if b not in THEMES]
    if missing_themes:
        print(f"ABORT: no search themes written for {missing_themes}. "
              "Add them to THEMES rather than shipping a group with no signal.")
        return 1

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\naccount  {ACCOUNT} [{cust}]   merchant center {mc}")
    print(f"campaign {CAMPAIGN_NAME!r}")
    print(f"  status   PAUSED   budget ${args.budget:.2f}/day")
    print( "  bidding  MAXIMIZE_CONVERSION_VALUE, no target ROAS")
    print( "  goals    inherited from the account (Purchase / Website)")
    print(f"  geo      US, minus Alaska / Hawaii / Puerto Rico, PRESENCE only")
    print( "  automations OPTED_OUT: " + ", ".join(AUTOMATIONS_OFF))

    print(f"\nFEED  {sum(ok.values())} servable products")
    if skipped:
        print("  excluded for real product errors:")
        for codes, n in skipped.most_common():
            print(f"    {n:>4}  {', '.join(codes)}")
    print(f"\nASSET GROUPS (threshold {OWN_GROUP_MIN} products)")
    for b, n in own:
        print(f"  {group_name(b):28} brand={b!r:22} {n:>4} products, "
              f"{len(THEMES[b])} themes")
    print(f"  {CATCHALL:28} everything except {[b for b, _ in own]}"
          f"  -> {sum(n for _, n in other)} products")
    for b, n in other:
        print(f"      {b or '(no brand)':24} {n:>4}")
    covered = sum(n for _, n in own) + sum(n for _, n in other)
    print(f"\n  coverage {covered}/{sum(ok.values())} servable products")

    nseg = len(IN_MARKET) + len(AFFINITY) + len(LIFE_EVENTS) + len(DETAILED_DEMOGRAPHICS)
    print(f"\nAUDIENCE  {AUDIENCE_NAME!r}  ({nseg} segments, OR'd, "
          "signalled on every group)")
    for label, items in (("in-market", IN_MARKET), ("affinity", AFFINITY),
                         ("life event", LIFE_EVENTS),
                         ("demographic", DETAILED_DEMOGRAPHICS)):
        for _id, nm in items:
            print(f"    {label:12} {_id:>6}  {nm}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to build.")
        return 0

    # ---- budget -----------------------------------------------------------
    bop = client.get_type("CampaignBudgetOperation")
    b = bop.create
    b.name = f"{BUDGET_NAME} {int(args.budget)}"
    b.amount_micros = int(args.budget * 1e6)
    b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False
    budget_rn = client.get_service("CampaignBudgetService").mutate_campaign_budgets(
        customer_id=cust, operations=[bop]).results[0].resource_name
    print(f"\n  budget {budget_rn}")

    # ---- campaign ---------------------------------------------------------
    cop = client.get_type("CampaignOperation")
    c = cop.create
    c.name = CAMPAIGN_NAME
    c.advertising_channel_type = e.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
    c.status = e.CampaignStatusEnum.PAUSED
    c.campaign_budget = budget_rn
    c.bidding_strategy_type = e.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSION_VALUE
    c.maximize_conversion_value.target_roas = 0.0
    c.shopping_setting.merchant_id = mc
    c.brand_guidelines_enabled = True
    c.geo_target_type_setting.positive_geo_target_type = (
        e.PositiveGeoTargetTypeEnum.PRESENCE)
    c.geo_target_type_setting.negative_geo_target_type = (
        e.NegativeGeoTargetTypeEnum.PRESENCE)
    c.contains_eu_political_advertising = (
        e.EuPoliticalAdvertisingStatusEnum
        .DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    # AssetAutomationSetting is nested under Campaign, so client.get_type()
    # cannot resolve it; proto-plus takes a plain dict for the repeated field.
    # The field is replaced wholesale, so write the full target set.
    for name in AUTOMATIONS_OFF:
        c.asset_automation_settings.append({
            "asset_automation_type": e.AssetAutomationTypeEnum[name],
            "asset_automation_status": e.AssetAutomationStatusEnum.OPTED_OUT,
        })
    camp_rn = client.get_service("CampaignService").mutate_campaigns(
        customer_id=cust, operations=[cop]).results[0].resource_name
    camp_id = int(camp_rn.split("/")[-1])
    print(f"  campaign {camp_rn}  (PAUSED)")

    # ---- geo --------------------------------------------------------------
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

    # ---- asset groups (zero assets -- feed only) ---------------------------
    order = [group_name(b) for b, _ in own] + [CATCHALL]
    ag_ops = []
    for nm in order:
        o = client.get_type("AssetGroupOperation")
        a = o.create
        a.name = nm
        a.campaign = camp_rn
        a.final_urls.append(FINAL_URL)
        a.status = e.AssetGroupStatusEnum.ENABLED
        ag_ops.append(o)
    ag_rns = [r.resource_name for r in
              client.get_service("AssetGroupService").mutate_asset_groups(
                  customer_id=cust, operations=ag_ops).results]
    ag_by_name = dict(zip(order, ag_rns))
    print(f"  {len(ag_rns)} asset groups, no assets (feed only)")

    # ---- listing trees, one mutate per group -------------------------------
    svc = client.get_service("AssetGroupListingGroupFilterService")
    INC = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
    EXC = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
    SUB = e.ListingGroupFilterTypeEnum.SUBDIVISION

    def build_tree(ag_rn, children):
        """SUBDIVISION root plus children, created in ONE atomic mutate.

        Temporary resource names carry the parent link. The everything-else
        sibling must still declare its dimension: touching an empty proto3
        message does not set the oneof, so mark it present with no value.
        """
        ag_id = ag_rn.split("/")[-1]
        ops = []
        root = client.get_type("AssetGroupListingGroupFilterOperation")
        f = root.create
        f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                           f"{ag_id}~-1")
        f.asset_group = ag_rn
        f.type_ = SUB
        f.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        ops.append(root)
        for i, (kind, brand) in enumerate(children, start=2):
            o = client.get_type("AssetGroupListingGroupFilterOperation")
            f = o.create
            f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                               f"{ag_id}~{-i}")
            f.asset_group = ag_rn
            f.parent_listing_group_filter = (
                f"customers/{cust}/assetGroupListingGroupFilters/{ag_id}~-1")
            f.type_ = kind
            f.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            if brand is not None:
                f.case_value.product_brand.value = brand
            else:
                f._pb.case_value.product_brand.SetInParent()
            ops.append(o)
        svc.mutate_asset_group_listing_group_filters(
            customer_id=cust, operations=ops)
        return len(ops)

    nodes = 0
    for brand, _ in own:
        nodes += build_tree(ag_by_name[group_name(brand)],
                            [(INC, brand), (EXC, None)])
        print(f"    {group_name(brand)}: brand={brand!r} + everything-else excluded")
    kids = [(EXC, brand) for brand, _ in own] + [(INC, None)]
    nodes += build_tree(ag_by_name[CATCHALL], kids)
    print(f"    {CATCHALL}: {len(own)} brands excluded + everything-else included")
    print(f"  {nodes} listing nodes")

    # ---- audience ---------------------------------------------------------
    aop = client.get_type("AudienceOperation")
    aud = aop.create
    aud.name = AUDIENCE_NAME
    aud.description = ("Homeowners replacing or upgrading an HVAC system, "
                       "people mid-renovation or newly moved in, and the "
                       "contractors and small installers who buy this "
                       "equipment for jobs.")
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
    for _id, _ in DETAILED_DEMOGRAPHICS:
        s = client.get_type("AudienceSegment")
        s.detailed_demographic.detailed_demographic = (
            f"customers/{cust}/detailedDemographics/{_id}")
        seg.segments.append(s)
    aud.dimensions.append(dim)
    audience_rn = client.get_service("AudienceService").mutate_audiences(
        customer_id=cust, operations=[aop]).results[0].resource_name
    print(f"  audience {audience_rn}")

    # ---- signals ----------------------------------------------------------
    sig_ops = []
    for nm, ag_rn in ag_by_name.items():
        o = client.get_type("AssetGroupSignalOperation")
        o.create.asset_group = ag_rn
        o.create.audience.audience = audience_rn
        sig_ops.append(o)
    for brand, _ in own:
        ag_rn = ag_by_name[group_name(brand)]
        for t in THEMES[brand]:
            o = client.get_type("AssetGroupSignalOperation")
            o.create.asset_group = ag_rn
            o.create.search_theme.text = t
            sig_ops.append(o)
    # The catch-all gets the audience only: it has no single product theme,
    # and generic HVAC themes there would compete with the brand groups.
    client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
        customer_id=cust, operations=sig_ops)
    print(f"  {len(sig_ops)} signals "
          f"({len(ag_by_name)} audience + "
          f"{sum(len(THEMES[b]) for b, _ in own)} search themes)")

    # ---- read-back --------------------------------------------------------
    print("\n--- read-back ---")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.bidding_strategy_type, campaign.primary_status,
               campaign.asset_automation_settings, campaign_budget.amount_micros
        FROM campaign WHERE campaign.id = {camp_id}"""):
        print(f"  [{r.campaign.id}] {r.campaign.name!r} {r.campaign.status.name} "
              f"{r.campaign.bidding_strategy_type.name} "
              f"${r.campaign_budget.amount_micros/1e6:.2f}/day "
              f"primary={r.campaign.primary_status.name}")
        off = [s.asset_automation_type.name for s in r.campaign.asset_automation_settings
               if s.asset_automation_status.name == "OPTED_OUT"]
        print(f"      automations OPTED_OUT: {len(off)}/5 {sorted(off)}")
    counts = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group.primary_status, campaign.id
        FROM asset_group WHERE campaign.id = {camp_id}"""):
        counts[r.asset_group.id] = [r.asset_group.name,
                                    r.asset_group.primary_status.name, 0, 0, 0]
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, campaign.id
        FROM asset_group_listing_group_filter WHERE campaign.id = {camp_id}"""):
        counts[r.asset_group.id][2] += 1
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, campaign.id
        FROM asset_group_signal WHERE campaign.id = {camp_id}"""):
        if r.asset_group_signal.search_theme.text:
            counts[r.asset_group.id][3] += 1
        if r.asset_group_signal.audience.audience:
            counts[r.asset_group.id][4] += 1
    for _id, (nm, ps, nodes_, th, au) in sorted(counts.items(), key=lambda kv: kv[1][0]):
        print(f"  {nm:28} nodes={nodes_} themes={th:>3} audience={au} [{ps}]")
    print(f"\nBuilt PAUSED. Campaign id {camp_id}. "
          "Nothing will serve until it is enabled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
