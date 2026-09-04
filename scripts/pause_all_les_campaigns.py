"""Pause every enabled campaign in the Laser Engraver Store account.

Trevor's instruction on 2026-09-03, ahead of a rebuild. Pause, never remove --
the existing SKAG structure, negative lists and ad copy stay intact and can be
switched back on if the rebuild turns out worse.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Laser Engraver Store")["id"]
    ga = client.get_service("GoogleAdsService")

    rows = list(ga.search(customer_id=cust, query="""
        SELECT campaign.id, campaign.name, campaign.advertising_channel_type,
               campaign_budget.amount_micros
        FROM campaign WHERE campaign.status = 'ENABLED'"""))
    if not rows:
        print("No enabled campaigns. Nothing to do.")
        return 0

    total = sum(r.campaign_budget.amount_micros for r in rows) / 1e6
    print("=" * 70)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 70)
    print(f"\nPausing {len(rows)} enabled campaigns "
          f"(${total:,.2f}/day of budget released):\n")
    for r in rows:
        c = r.campaign
        print(f"  {c.id:>12} {c.name[:42]:44} "
              f"{c.advertising_channel_type.name[:12]:13} "
              f"${r.campaign_budget.amount_micros/1e6:>7.2f}/day")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to pause.")
        return 0

    svc = client.get_service("CampaignService")
    ops = []
    for r in rows:
        op = client.get_type("CampaignOperation")
        op.update.resource_name = svc.campaign_path(cust, r.campaign.id)
        op.update.status = client.enums.CampaignStatusEnum.PAUSED
        op.update_mask.paths.append("status")
        ops.append(op)
    svc.mutate_campaigns(customer_id=cust, operations=ops)
    print(f"\n  paused {len(ops)} campaigns")

    left = list(ga.search(customer_id=cust, query="""
        SELECT campaign.id, campaign.name FROM campaign
        WHERE campaign.status = 'ENABLED'"""))
    print(f"\nVerified: {len(left)} campaigns still enabled "
          f"{[r.campaign.name for r in left]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
