"""Make Purchase the only conversion goal Culinary Profis bids on.

Trevor set the conversion ACTIONS to primary/secondary correctly, but this
account uses the conversion GOALS model, where the action-level
primary_for_goal flag is ignored and the goal-level `biddable` flag governs.
So Add To Cart was still steering Maximize Conversions: of the 3 "Conversions"
the PMax recorded in 30 days, 2 were Add To Cart and 1 a Begin Checkout, and
zero were purchases.

Three things have to change together, because campaign_conversion_goal
OVERRIDES customer_conversion_goal -- fixing only the account leaves every
campaign bidding on the old set:

1. Account goals: DEFAULT and ADD_TO_CART -> not biddable. PURCHASE stays.
2. The same two on every enabled campaign's own override.
3. The conversion action 'Begin Checkout - Secondary Goal - Data-driven'
   still carries primary_for_goal=True despite its name and contributed 1 of
   the 3 conversions. Set it secondary.

Zero purchases in 90 days is expected here -- the account is five weeks old at
$15/day selling multi-thousand-dollar commercial kitchen equipment. This does
NOT repeat the BetterPatio failure, where Maximize Conversions had a $233
target CPA it could not hit and Google stopped bidding. This campaign has no
target CPA, so it keeps spending; it simply stops optimising toward cheap
add-to-carts.

Run with no flags for a dry run. Pass --execute to apply.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "Culinary Profis"
TURN_OFF = {"DEFAULT", "ADD_TO_CART"}
KEEP = "PURCHASE"
SECONDARY_ACTION = "Begin Checkout - Secondary Goal"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")

    cust_goals = []
    for r in ga.search(customer_id=cust, query="""
        SELECT customer_conversion_goal.resource_name,
               customer_conversion_goal.category,
               customer_conversion_goal.biddable
        FROM customer_conversion_goal """):
        g = r.customer_conversion_goal
        if g.biddable and g.category.name in TURN_OFF:
            cust_goals.append((g.category.name, g.resource_name))

    camps = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT campaign.id, campaign.name FROM campaign
        WHERE campaign.status = 'ENABLED' """):
        camps[r.campaign.id] = r.campaign.name

    camp_goals = []
    for cid, nm in camps.items():
        for r in ga.search(customer_id=cust, query=f"""
            SELECT campaign_conversion_goal.resource_name,
                   campaign_conversion_goal.category,
                   campaign_conversion_goal.biddable
            FROM campaign_conversion_goal WHERE campaign.id = {cid} """):
            g = r.campaign_conversion_goal
            if g.biddable and g.category.name in TURN_OFF:
                camp_goals.append((nm, g.category.name, g.resource_name))

    actions = []
    for r in ga.search(customer_id=cust, query="""
        SELECT conversion_action.resource_name, conversion_action.name,
               conversion_action.primary_for_goal, conversion_action.status
        FROM conversion_action WHERE conversion_action.status = 'ENABLED' """):
        a = r.conversion_action
        if a.primary_for_goal and a.name.startswith(SECONDARY_ACTION):
            actions.append((a.name, a.resource_name))

    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print(f"account goals to make non-biddable ({len(cust_goals)}):")
    for cat, _ in cust_goals:
        print(f"    {cat}")
    print(f"\ncampaign overrides to make non-biddable ({len(camp_goals)}):")
    for nm, cat, _ in camp_goals:
        print(f"    {nm[:42]:44} {cat}")
    print(f"\nconversion actions to mark secondary ({len(actions)}):")
    for nm, _ in actions:
        print(f"    {nm[:66]}")
    print(f"\nremaining biddable goal: {KEEP}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
        return 0

    if cust_goals:
        ops = []
        for _, rn in cust_goals:
            o = client.get_type("CustomerConversionGoalOperation")
            o.update.resource_name = rn
            o.update.biddable = False
            o.update_mask.paths.append("biddable")
            ops.append(o)
        client.get_service("CustomerConversionGoalService") \
              .mutate_customer_conversion_goals(customer_id=cust, operations=ops)
        print(f"  account: {len(ops)} goals off")

    if camp_goals:
        ops = []
        for _, _, rn in camp_goals:
            o = client.get_type("CampaignConversionGoalOperation")
            o.update.resource_name = rn
            o.update.biddable = False
            o.update_mask.paths.append("biddable")
            ops.append(o)
        client.get_service("CampaignConversionGoalService") \
              .mutate_campaign_conversion_goals(customer_id=cust, operations=ops)
        print(f"  campaigns: {len(ops)} overrides off")

    if actions:
        ops = []
        for _, rn in actions:
            o = client.get_type("ConversionActionOperation")
            o.update.resource_name = rn
            o.update.primary_for_goal = False
            o.update_mask.paths.append("primary_for_goal")
            ops.append(o)
        client.get_service("ConversionActionService") \
              .mutate_conversion_actions(customer_id=cust, operations=ops)
        print(f"  actions: {len(ops)} set secondary")

    print("\n-- verification --")
    for r in ga.search(customer_id=cust, query="""
        SELECT customer_conversion_goal.category,
               customer_conversion_goal.biddable
        FROM customer_conversion_goal """):
        g = r.customer_conversion_goal
        if g.biddable:
            print(f"   account biddable: {g.category.name}")
    for cid, nm in camps.items():
        left = [r.campaign_conversion_goal.category.name for r in ga.search(
            customer_id=cust, query=f"""
            SELECT campaign_conversion_goal.category,
                   campaign_conversion_goal.biddable
            FROM campaign_conversion_goal WHERE campaign.id = {cid} """)
            if r.campaign_conversion_goal.biddable]
        print(f"   {nm[:42]:44} biddable: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
