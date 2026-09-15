"""Build a feed-only Performance Max campaign covering BetterPatio's catalogue.

Feed-only PMax is the pattern already running in the other three accounts:
one asset group per brand, each carrying a brand listing filter and NO text,
image, logo or video assets. Ad strength reads POOR and the asset group is
still ELIGIBLE -- FUSA's feed-only campaign serves 16,768 impressions and
$215 over 30 days that way. With no creative, PMax has nothing to build a
display or video ad from, so it serves Shopping inventory from the feed.

Coverage: every brand with eligible products EXCEPT the nine already served by
`BP · PMax — Outdoor Kitchens`. Those keep their creative, search themes and
video in the kitchens campaign; duplicating them here would put two campaigns
into the same auction for the same products.

Brands at or above OWN_GROUP_MIN eligible products get their own asset group.
The rest fall into a catch-all group that includes 'everything else' while
explicitly excluding every brand handled elsewhere -- so brands added to the
feed in future are advertised automatically with no rebuild.

Settings mirror the kitchens campaign: Maximize Conversions with no target
CPA, PRESENCE geo on the same 48 locations, brand guidelines on, same
Merchant Center. Campaign conversion goals are deliberately NOT set, so the
campaign inherits the account goal (Purchase / Website). Setting them at
campaign level is what silently blinded three campaigns in this account.

The campaign is created PAUSED. Enabling it and confirming the budget is a
spend decision and is left to Trevor.

Run with no flags for a dry run. Pass --execute to build.
"""
import argparse
import sys
from collections import Counter

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
KITCHENS_PMAX = 24209664922
CAMPAIGN_NAME = "BP · PMax — All Brands (feed only)"
BUDGET_NAME = "BP · PMax — All Brands (feed only)"
BUDGET_DAILY = 50.00          # placeholder; confirm before enabling
OWN_GROUP_MIN = 20
CATCHALL = "BP · All Other Brands"
FINAL_URL = "https://betterpatio.com"

# Served by the kitchens PMax -- kept out to avoid self-competition.
KITCHENS_BRANDS = {
    "mont alpi", "cal flame", "betterpatio", "betterpatio designer series",
    "betterpatio mountain series", "betterpatio solace series",
    "betterpatio unfinished outdoor kitchens", "betterpatio.com",
    "ufinish by betterpatio outdoor kitchens",
}


def feed_brands(ga, cust):
    ok = Counter()
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.issues
        FROM shopping_product """):
        p = r.shopping_product
        if {i.error_code for i in p.issues} - {"not_eligible_in_any_campaign"}:
            continue
        ok[p.brand.strip().lower()] += 1
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--budget", type=float, default=BUDGET_DAILY)
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id FROM campaign
        WHERE campaign.name = '{CAMPAIGN_NAME}'
          AND campaign.status != 'REMOVED' """):
        print(f"ABORT: campaign {CAMPAIGN_NAME!r} already exists "
              f"[{r.campaign.id}]. Refusing to build a duplicate.")
        return 1

    ok = feed_brands(ga, cust)
    own = [(b, n) for b, n in ok.most_common()
           if b and b not in KITCHENS_BRANDS and n >= OWN_GROUP_MIN]
    tail = [(b, n) for b, n in ok.most_common()
            if b not in KITCHENS_BRANDS and (not b or n < OWN_GROUP_MIN)]
    kitchens_n = sum(n for b, n in ok.items() if b in KITCHENS_BRANDS)

    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print(f"feed: {sum(ok.values())} eligible products across {len(ok)} brands")
    print(f"  kitchens PMax keeps {len(KITCHENS_BRANDS & set(ok))} brands / "
          f"{kitchens_n} products")
    print(f"  own asset group (>= {OWN_GROUP_MIN}): {len(own)} brands / "
          f"{sum(n for _, n in own)} products")
    print(f"  {CATCHALL}: {len(tail)} brands / {sum(n for _, n in tail)} products")
    print(f"  campaign total: {sum(n for _, n in own) + sum(n for _, n in tail)} "
          f"products in {len(own) + 1} asset groups\n")
    for b, n in own:
        print(f"    {b:40} {n:6}")
    print(f"\n  rolled into {CATCHALL}:")
    for b, n in tail:
        print(f"    {b or '(no brand)':40} {n:6}")

    locs = [r.campaign_criterion.location.geo_target_constant
            for r in ga.search(customer_id=cust, query=f"""
                SELECT campaign_criterion.location.geo_target_constant
                FROM campaign_criterion WHERE campaign.id = {KITCHENS_PMAX}
                  AND campaign_criterion.type = 'LOCATION'
                  AND campaign_criterion.negative = FALSE """)]
    mc = next(r.campaign.shopping_setting.merchant_id for r in ga.search(
        customer_id=cust, query=f"""
        SELECT campaign.shopping_setting.merchant_id FROM campaign
        WHERE campaign.id = {KITCHENS_PMAX} """))
    print(f"\n  geo: {len(locs)} locations, PRESENCE    merchant: {mc}")
    print(f"  budget: ${args.budget:.2f}/day    status: PAUSED")
    print(f"  bidding: MAXIMIZE_CONVERSIONS, no target CPA")
    print(f"  conversion goals: inherited from the account (Purchase / Website)")

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
    c.maximize_conversions.target_cpa_micros = 0
    c.bidding_strategy_type = e.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSIONS
    c.shopping_setting.merchant_id = mc
    c.brand_guidelines_enabled = True
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

    # ---- geo --------------------------------------------------------------
    geo_ops = []
    for g in locs:
        o = client.get_type("CampaignCriterionOperation")
        o.create.campaign = camp_rn
        o.create.location.geo_target_constant = g
        geo_ops.append(o)
    if geo_ops:
        client.get_service("CampaignCriterionService").mutate_campaign_criteria(
            customer_id=cust, operations=geo_ops)
        print(f"  {len(geo_ops)} locations")

    # ---- asset groups -----------------------------------------------------
    names = [f"BP · {b.title()}" for b, _ in own] + [CATCHALL]
    ag_ops = []
    for nm in names:
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
    print(f"  {len(ag_rns)} asset groups (no assets -- feed only)")

    # Listing group trees are NOT built here. They must be created one
    # asset group at a time, root and children in a single mutate using
    # temporary resource names, and the "everything else" sibling has to
    # declare its dimension explicitly. Creating bare subdivision roots in
    # a batch fails atomically and leaves the asset groups empty.
    # Run scripts/complete_bp_feedonly_listing_groups.py next.
    print("  asset groups have NO product tree yet -- "
          "run complete_bp_feedonly_listing_groups.py")
    print(f"\nBuilt PAUSED. Campaign id {camp_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
