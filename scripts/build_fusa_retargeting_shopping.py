"""Standard Shopping campaign for Fountains USA that serves ONLY to retargeting
audiences, at a higher bid than cold traffic would justify.

How the "only retargeting" part works: the ad group carries the remarketing
user lists AND a target_restriction on the AUDIENCE dimension with
bid_only=False. That flips audiences from observation to targeting, so the
campaign is eligible only when the searcher is in one of the lists. Attaching
the lists without that restriction would let it serve to everyone, which is the
usual way this setup silently fails.

Settings mirror the live PMax campaign so the two agree: merchant 258983089,
the four states Trevor sells into, and PRESENCE location targeting.

Campaign priority is HIGH. When the account's other Shopping campaigns are
switched back on, a returning visitor should be picked up by this campaign
rather than the cold-traffic ones.

Created PAUSED. Budget is a placeholder until Trevor sets one -- nothing spends
while it is paused.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

MERCHANT_ID = 258983089
CAMPAIGN_NAME = "FUSA - Shopping - Retargeting Only"
AD_GROUP_NAME = "FUSA - Returning Visitors"
DAILY_BUDGET_MICROS = 15_000_000       # placeholder, campaign is paused
CPC_BID_MICROS = 2_000_000             # $2.00 -- above the $1.50 display bid

# CA, AZ, FL, TX -- copied from the live PMax campaign, not typed from memory.
GEO_TARGETS = [21136, 21137, 21142, 21176]

# (user list id, label, size on Search)
AUDIENCES = [
    (9204844723, "All Users of Fountains USA Shopify Store - GA4", 6000),
    (9187533874, "Product viewers (Retail)", 240),
    (9187533871, "General visitors (Retail)", 670),
    (9187533877, "Shopping cart abandoners (Retail)", 0),
]

# Generic irrelevant-traffic lists. Per Trevor: generic lists only, not the
# brand/SKU lists, for feed-driven campaigns.
NEGATIVE_LISTS = [
    (11712268851, "Generic", 169),
    (11765673294, "EP Generic", 321),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Fountains USA")["id"]
    ga = client.get_service("GoogleAdsService")

    dupe = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.name FROM campaign
        WHERE campaign.name = '{CAMPAIGN_NAME}' AND campaign.status != 'REMOVED'"""))
    if dupe:
        print(f"A campaign named {CAMPAIGN_NAME!r} already exists "
              f"({dupe[0].campaign.id}). Aborting rather than making a second one.")
        return 1

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\nCAMPAIGN  {CAMPAIGN_NAME}   [will be created PAUSED]")
    print(f"  channel        SHOPPING (standard)")
    print(f"  merchant       {MERCHANT_ID}")
    print(f"  priority       HIGH")
    print(f"  bidding        MANUAL_CPC, ad group max CPC ${CPC_BID_MICROS/1e6:.2f}")
    print(f"  budget         ${DAILY_BUDGET_MICROS/1e6:.2f}/day  (placeholder -- paused)")
    print(f"  geo            {GEO_TARGETS} on PRESENCE")
    print(f"\nAD GROUP  {AD_GROUP_NAME}")
    print(f"  listing group  all products (single root unit)")
    print(f"  AUDIENCE targeting restriction: bid_only=False  <- this is what")
    print(f"                                                     limits serving")
    for i, n, s in AUDIENCES:
        note = "  (below Search minimum, contributes nothing yet)" if s < 100 else ""
        print(f"    {i}  {n[:44]:46} {s:>6} on Search{note}")
    print(f"\nNEGATIVE KEYWORD LISTS")
    for i, n, c in NEGATIVE_LISTS:
        print(f"    {i}  {n:14} {c} members")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    e = client.enums

    # ---- budget ----------------------------------------------------------
    # A failed run can leave the budget behind; reuse it rather than stacking
    # duplicate budgets in the account.
    budget_name = f"{CAMPAIGN_NAME} budget"
    orphan = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign_budget.resource_name, campaign_budget.name
        FROM campaign_budget
        WHERE campaign_budget.name = '{budget_name}'
          AND campaign_budget.status != 'REMOVED'"""))
    if orphan:
        budget_rn = orphan[0].campaign_budget.resource_name
        print(f"\n  reusing existing budget {budget_rn}")
    else:
        budget_rn = None

    b_op = client.get_type("CampaignBudgetOperation")
    b_op.create.name = budget_name
    b_op.create.amount_micros = DAILY_BUDGET_MICROS
    b_op.create.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b_op.create.explicitly_shared = False
    if budget_rn is None:
        budget_rn = client.get_service("CampaignBudgetService").mutate_campaign_budgets(
            customer_id=cust, operations=[b_op]).results[0].resource_name

    # ---- campaign --------------------------------------------------------
    c_op = client.get_type("CampaignOperation")
    c = c_op.create
    c.name = CAMPAIGN_NAME
    c.status = e.CampaignStatusEnum.PAUSED
    c.advertising_channel_type = e.AdvertisingChannelTypeEnum.SHOPPING
    c.campaign_budget = budget_rn
    c.manual_cpc.enhanced_cpc_enabled = False
    c.shopping_setting.merchant_id = MERCHANT_ID
    c.shopping_setting.campaign_priority = 2          # high
    c.geo_target_type_setting.positive_geo_target_type = (
        e.PositiveGeoTargetTypeEnum.PRESENCE)
    c.contains_eu_political_advertising = (
        e.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    campaign_rn = client.get_service("CampaignService").mutate_campaigns(
        customer_id=cust, operations=[c_op]).results[0].resource_name
    print(f"\n  created campaign {campaign_rn}")

    # ---- geo -------------------------------------------------------------
    cc_ops = []
    for geo in GEO_TARGETS:
        op = client.get_type("CampaignCriterionOperation")
        op.create.campaign = campaign_rn
        op.create.location.geo_target_constant = f"geoTargetConstants/{geo}"
        cc_ops.append(op)
    client.get_service("CampaignCriterionService").mutate_campaign_criteria(
        customer_id=cust, operations=cc_ops)
    print(f"  targeted {len(cc_ops)} locations on PRESENCE")

    # ---- negative keyword lists -----------------------------------------
    css_ops = []
    for lid, name, _ in NEGATIVE_LISTS:
        op = client.get_type("CampaignSharedSetOperation")
        op.create.campaign = campaign_rn
        op.create.shared_set = client.get_service(
            "SharedSetService").shared_set_path(cust, lid)
        css_ops.append(op)
    client.get_service("CampaignSharedSetService").mutate_campaign_shared_sets(
        customer_id=cust, operations=css_ops)
    print(f"  applied {len(css_ops)} negative keyword lists")

    # ---- ad group, with audiences as TARGETING not observation ----------
    ag_op = client.get_type("AdGroupOperation")
    ag = ag_op.create
    ag.name = AD_GROUP_NAME
    ag.campaign = campaign_rn
    ag.status = e.AdGroupStatusEnum.ENABLED
    ag.type_ = e.AdGroupTypeEnum.SHOPPING_PRODUCT_ADS
    ag.cpc_bid_micros = CPC_BID_MICROS
    tr = client.get_type("TargetRestriction")
    tr.targeting_dimension = e.TargetingDimensionEnum.AUDIENCE
    tr.bid_only = False
    ag.targeting_setting.target_restrictions.append(tr)
    ad_group_rn = client.get_service("AdGroupService").mutate_ad_groups(
        customer_id=cust, operations=[ag_op]).results[0].resource_name
    print(f"  created ad group {ad_group_rn} (audiences set to TARGETING)")

    # ---- product ad + listing group (all products) ----------------------
    ada_op = client.get_type("AdGroupAdOperation")
    ada_op.create.ad_group = ad_group_rn
    ada_op.create.status = e.AdGroupAdStatusEnum.ENABLED
    ada_op.create.ad.shopping_product_ad._pb.SetInParent()
    client.get_service("AdGroupAdService").mutate_ad_group_ads(
        customer_id=cust, operations=[ada_op])

    lg_op = client.get_type("AdGroupCriterionOperation")
    lg = lg_op.create
    lg.ad_group = ad_group_rn
    lg.status = e.AdGroupCriterionStatusEnum.ENABLED
    lg.listing_group.type_ = e.ListingGroupTypeEnum.UNIT
    lg.cpc_bid_micros = CPC_BID_MICROS

    aud_ops = [lg_op]
    ul_svc = client.get_service("UserListService")
    for uid, _, _ in AUDIENCES:
        op = client.get_type("AdGroupCriterionOperation")
        op.create.ad_group = ad_group_rn
        op.create.status = e.AdGroupCriterionStatusEnum.ENABLED
        op.create.user_list.user_list = ul_svc.user_list_path(cust, uid)
        aud_ops.append(op)
    client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(
        customer_id=cust, operations=aud_ops)
    print(f"  added the all-products listing group and {len(AUDIENCES)} audiences")

    # ---- verify ----------------------------------------------------------
    cid = campaign_rn.split("/")[-1]
    print("\n-- verify --")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.name, campaign.status, campaign.bidding_strategy_type,
               campaign.shopping_setting.merchant_id,
               campaign.shopping_setting.campaign_priority,
               campaign.geo_target_type_setting.positive_geo_target_type,
               campaign_budget.amount_micros
        FROM campaign WHERE campaign.id = {cid}"""):
        cc = r.campaign
        print(f"  {cc.name} [{cc.status.name}] {cc.bidding_strategy_type.name} "
              f"merchant={cc.shopping_setting.merchant_id} "
              f"priority={cc.shopping_setting.campaign_priority} "
              f"geo={cc.geo_target_type_setting.positive_geo_target_type.name} "
              f"${r.campaign_budget.amount_micros/1e6:.2f}/day")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.targeting_setting.target_restrictions
        FROM ad_group WHERE campaign.id = {cid}"""):
        for t in r.ad_group.targeting_setting.target_restrictions:
            print(f"  restriction {t.targeting_dimension.name} bid_only={t.bid_only}")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group_criterion.display_name, ad_group_criterion.type
        FROM ad_group_criterion WHERE campaign.id = {cid}
          AND ad_group_criterion.type = 'USER_LIST'
          AND ad_group_criterion.status = 'ENABLED'"""):
        print(f"  audience: {r.ad_group_criterion.display_name}")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT shared_set.name FROM campaign_shared_set
        WHERE campaign.id = {cid} AND campaign_shared_set.status != 'REMOVED'"""):
        print(f"  negatives: {r.shared_set.name}")
    print(f"\nCreated PAUSED. Campaign id {cid}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
