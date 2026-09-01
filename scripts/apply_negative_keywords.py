"""Apply the drafted negative_keywords/*.json lists to their accounts.

    python scripts/apply_negative_keywords.py

Idempotent -- safe to re-run. Creates a shared "Claude Negatives - Universal"
list per account if missing, adds any terms not already present, and links
the list to every currently-enabled campaign that isn't linked yet.
"""

import sys
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_ads.auth import get_client  # noqa: E402
from google_ads.negatives import apply_negative_list  # noqa: E402


def main():
    client = get_client()
    files = sorted(glob.glob(str(Path(__file__).resolve().parent.parent / "negative_keywords" / "*.json")))

    if not files:
        print("No files in negative_keywords/.")
        return 1

    for f in files:
        try:
            summary = apply_negative_list(f, client=client)
        except Exception as exc:
            print(f"\n{f}: FAILED -- {exc}")
            continue

        print(f"\n{summary['account']} ({summary['account_id']})")
        print(f"  Shared set: {'created new' if summary['shared_set_created'] else 'reused existing'} "
              f"'{summary['shared_set_resource_name'].split('/')[-1]}'")
        if summary["terms_added"]:
            print(f"  Added {len(summary['terms_added'])} new terms: {', '.join(summary['terms_added'])}")
        else:
            print(f"  No new terms added ({summary['terms_already_present']} already present)")
        if summary["campaigns_linked"]:
            print(f"  Linked to {len(summary['campaigns_linked'])} campaign(s): {', '.join(summary['campaigns_linked'])}")
        else:
            print(f"  No campaigns linked (0 of {summary['campaigns_enabled_total']} enabled campaigns needed linking)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
