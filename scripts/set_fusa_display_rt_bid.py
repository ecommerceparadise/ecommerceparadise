"""Move the Fountains USA display remarketing campaign onto a controllable bid.

Approved by Trevor in conversation on 2026-09-03: Manual CPC at a $1.50 max,
budget held at $5/day.

Why the change was needed. The campaign ran MAXIMIZE_CONVERSIONS with zero
conversion history in the account's display remarketing, so the bidder had
nothing to learn from and never entered auctions -- 0 impressions since it was
created on 1 September. Under an automated strategy the ad group's CPC bid is
ignored, which is why the $0.01 sitting there had no visible effect. Manual CPC
makes that value the operative bid, so it has to be raised in the same change
or the campaign stays exactly as stuck.

$1.50 sits comfortably above typical display remarketing CPCs, which is the
point: the audience is small and the goal is decent desktop placements rather
than remnant inventory.

At $5/day this buys roughly three clicks a day. That is enough to confirm the
campaign serves and to judge placement quality; it is not enough to judge
conversion performance for some weeks.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24204679673
AD_GROUP = 202276525400
NEW_CPC_MICROS = 1_500_000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Fountains USA")["id"]
    ga = client.get_service("GoogleAdsService")

    rows = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.name, campaign.status, campaign.bidding_strategy_type,
               campaign.bidding_strategy, campaign_budget.amount_micros
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""))
    if len(rows) != 1:
        print(f"Expected 1 campaign, got {len(rows)}. Aborting.")
        return 1
    c = rows[0].campaign
    print(f"Campaign: {c.name}  [{c.status.name}]")
    print(f"  bidding:  {c.bidding_strategy_type.name}  ->  MANUAL_CPC")
    print(f"  budget:   ${rows[0].campaign_budget.amount_micros/1e6:.2f}/day (unchanged)")

    if c.bidding_strategy:
        print("\nREFUSING: this campaign uses a PORTFOLIO bid strategy "
              f"({c.bidding_strategy}). Switching it here would affect every other "
              "campaign sharing it. Detach it manually first.")
        return 1

    ag = list(ga.search(customer_id=cust, query=f"""
        SELECT ad_group.name, ad_group.cpc_bid_micros
        FROM ad_group WHERE ad_group.id = {AD_GROUP}"""))[0].ad_group
    print(f"  ad group: {ag.name}")
    print(f"  max CPC:  ${ag.cpc_bid_micros/1e6:.2f}  ->  ${NEW_CPC_MICROS/1e6:.2f}")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    # Bid strategy and the bid it depends on, in that order.
    camp_op = client.get_type("CampaignOperation")
    camp_op.update.resource_name = client.get_service(
        "CampaignService").campaign_path(cust, CAMPAIGN)
    camp_op.update.manual_cpc.enhanced_cpc_enabled = False
    camp_op.update_mask.paths.append("manual_cpc.enhanced_cpc_enabled")
    client.get_service("CampaignService").mutate_campaigns(
        customer_id=cust, operations=[camp_op])
    print("\n  bid strategy -> MANUAL_CPC")

    ag_op = client.get_type("AdGroupOperation")
    ag_op.update.resource_name = client.get_service(
        "AdGroupService").ad_group_path(cust, AD_GROUP)
    ag_op.update.cpc_bid_micros = NEW_CPC_MICROS
    ag_op.update_mask.paths.append("cpc_bid_micros")
    client.get_service("AdGroupService").mutate_ad_groups(
        customer_id=cust, operations=[ag_op])
    print(f"  ad group max CPC -> ${NEW_CPC_MICROS/1e6:.2f}")

    print("\n-- verify --")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.bidding_strategy_type, campaign_budget.amount_micros
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""):
        print(f"  bidding={r.campaign.bidding_strategy_type.name} "
              f"budget=${r.campaign_budget.amount_micros/1e6:.2f}/day")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.cpc_bid_micros, ad_group.status
        FROM ad_group WHERE ad_group.id = {AD_GROUP}"""):
        print(f"  ad group max CPC=${r.ad_group.cpc_bid_micros/1e6:.2f} "
              f"[{r.ad_group.status.name}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
