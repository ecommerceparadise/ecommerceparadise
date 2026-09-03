"""Raise the BetterPatio Search campaign budget from $45 to $65/day.

Approved by Trevor in conversation on 2026-09-03. Evidence: the campaign lost
57.7% of available impressions to budget over the prior 30 days while running a
$111 CPA against a $233 target -- it was buying leads at half the target price
and running out of money to buy more.

The budget is NOT shared (explicitly_shared=False), so this affects only this
campaign. Account daily total moves from ~$195 to ~$215.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 23303878302
NEW_DAILY_MICROS = 65_000_000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("BetterPatio.com")["id"]
    ga = client.get_service("GoogleAdsService")

    q = f"""
      SELECT campaign.name, campaign_budget.resource_name,
             campaign_budget.amount_micros, campaign_budget.explicitly_shared
      FROM campaign WHERE campaign.id = {CAMPAIGN}
    """
    rows = list(ga.search(customer_id=cust, query=q))
    if len(rows) != 1:
        print(f"Expected 1 campaign, got {len(rows)}. Aborting.")
        return 1
    b = rows[0].campaign_budget
    print(f"Campaign: {rows[0].campaign.name}")
    print(f"  current: ${b.amount_micros/1e6:.2f}/day   shared={b.explicitly_shared}")
    print(f"  new:     ${NEW_DAILY_MICROS/1e6:.2f}/day")

    if b.explicitly_shared:
        print("\nREFUSING: this budget is shared with other campaigns; raising it "
              "would change their delivery too. Resolve manually.")
        return 1

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    svc = client.get_service("CampaignBudgetService")
    op = client.get_type("CampaignBudgetOperation")
    op.update.resource_name = b.resource_name
    op.update.amount_micros = NEW_DAILY_MICROS
    op.update_mask.paths.append("amount_micros")
    svc.mutate_campaign_budgets(customer_id=cust, operations=[op])

    for r in ga.search(customer_id=cust, query=q):
        print(f"\nVerified: ${r.campaign_budget.amount_micros/1e6:.2f}/day")
    return 0


if __name__ == "__main__":
    sys.exit(main())
