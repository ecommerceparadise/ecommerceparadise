"""List every client account under the manager account.

    python scripts/list_accounts.py            # active, non-manager accounts
    python scripts/list_accounts.py --all      # include managers and closed

Use this to get the exact account names and IDs to work with.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_ads.accounts import list_accounts  # noqa: E402


def main():
    show_all = "--all" in sys.argv
    accounts = list_accounts(include_managers=show_all, include_closed=show_all)

    if not accounts:
        print("No accounts found.")
        return 0

    width = max(len(a["name"]) for a in accounts)
    for account in accounts:
        flag = "" if account["status"] == "ENABLED" else f"  [{account['status']}]"
        print(f"{account['name']:<{width}}  {account['id']}  {account['currency']}{flag}")

    print(f"\n{len(accounts)} account(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
