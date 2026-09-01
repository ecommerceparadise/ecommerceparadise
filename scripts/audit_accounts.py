"""Read-only audit across every managed account (or one, by name/ID).

    python scripts/audit_accounts.py                    # all managed accounts
    python scripts/audit_accounts.py "Laser Engraver"    # one account

Prints campaign status/spend, ad approval issues, settings drift, and the
top wasted (zero-conversion) search terms. Changes nothing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_ads.auth import get_client  # noqa: E402
from google_ads.accounts import list_accounts  # noqa: E402
from google_ads.audit import audit_account  # noqa: E402


def print_report(report):
    print(f"\n{'=' * 70}")
    print(f"{report['account_name']}  ({report['account_id']})")
    print(f"{'=' * 70}")

    if not report["campaigns"]:
        print("  NO CAMPAIGNS EXIST in this account.")
        return

    print(
        f"  30-day totals: ${report['total_spend']:.2f} spend, "
        f"{report['total_conversions']:.1f} conversions, "
        f"${report['total_conv_value']:.2f} conv. value"
    )

    print("\n  Campaigns:")
    for c in report["campaigns"]:
        cpa = f"${c['spend']/c['conversions']:.2f}" if c.get("conversions") else "—"
        print(
            f"    [{c['status']:<9}] {c['name']:<40} "
            f"{c.get('channel_type', '?'):<10} "
            f"spend=${c.get('spend', 0):.2f} budget=${c.get('budget', 0):.2f}/day "
            f"clicks={c.get('clicks', 0)} conv={c.get('conversions', 0):.1f} cpa={cpa}"
        )
        ad_status = c.get("ad_status")
        if ad_status:
            parts = ", ".join(f"{k}={v}" for k, v in ad_status.items() if v)
            print(f"        ads: {parts}")

    if report["settings_flags"]:
        print("\n  SETTINGS DRIFT:")
        for flag in report["settings_flags"]:
            print(f"    - {flag}")

    if report["wasted_search_terms"]:
        print(f"\n  Top wasted search terms (spend, zero conversions):")
        for t in report["wasted_search_terms"][:10]:
            print(f"    ${t['spend']:>6.2f}  {t['clicks']:>3} clicks  \"{t['term']}\"  ({t['ad_group']})")
        total_waste = sum(t["spend"] for t in report["wasted_search_terms"])
        print(f"    Total zero-conversion spend: ${total_waste:.2f}")


def main():
    client = get_client()

    if len(sys.argv) > 1:
        targets = [" ".join(sys.argv[1:])]
    else:
        targets = [a["name"] for a in list_accounts(client=client)]

    for name in targets:
        try:
            report = audit_account(name, client=client)
        except Exception as exc:
            print(f"\n{name}: FAILED — {exc}")
            continue
        print_report(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
