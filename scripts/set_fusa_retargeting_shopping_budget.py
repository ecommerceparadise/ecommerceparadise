"""Set the Fountains USA retargeting Shopping campaign budget to $5/day.

Trevor's number, given in conversation on 2026-09-03. Replaces the $15/day
placeholder the build script used while the campaign sat paused.

The campaign stays PAUSED -- enabling is a separate decision.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24214263728
NEW_DAILY_MICROS = 5_000_000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Fountains USA")["id"]
    ga = client.get_service("GoogleAdsService")

    rows = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.name, campaign.status, campaign_budget.resource_name,
               campaign_budget.amount_micros, campaign_budget.explicitly_shared,
               campaign_budget.reference_count
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""))
    if len(rows) != 1:
        print(f"Expected 1 campaign, got {len(rows)}. Aborting.")
        return 1
    c, b = rows[0].campaign, rows[0].campaign_budget
    print(f"Campaign: {c.name}  [{c.status.name}]")
    print(f"  budget ${b.amount_micros/1e6:.2f}/day -> ${NEW_DAILY_MICROS/1e6:.2f}/day"
          f"   shared={b.explicitly_shared} refs={b.reference_count}")

    if b.explicitly_shared or b.reference_count > 1:
        print("\nREFUSING: budget is shared with other campaigns.")
        return 1

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    op = client.get_type("CampaignBudgetOperation")
    op.update.resource_name = b.resource_name
    op.update.amount_micros = NEW_DAILY_MICROS
    op.update_mask.paths.append("amount_micros")
    client.get_service("CampaignBudgetService").mutate_campaign_budgets(
        customer_id=cust, operations=[op])

    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.status, campaign_budget.amount_micros
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""):
        print(f"\nVerified: ${r.campaign_budget.amount_micros/1e6:.2f}/day  "
              f"campaign still [{r.campaign.status.name}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
