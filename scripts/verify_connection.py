"""Read-only check that the Google Ads API connection works.

    python scripts/verify_connection.py

Confirms the credentials authenticate, then lists every client account
reachable under the manager account. Changes nothing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_ads.auth import get_client, get_login_customer_id, missing_vars  # noqa: E402
from google_ads.accounts import list_accounts  # noqa: E402


def main():
    absent = missing_vars()
    if absent:
        print("NOT CONNECTED. Missing credentials:\n")
        for var in absent:
            print(f"  - {var}")
        print("\nSee README.md for where each value comes from.")
        return 1

    print("Credentials found. Testing connection...\n")

    try:
        client = get_client()
        client.get_service("CustomerService").list_accessible_customers()
    except Exception as exc:
        print(f"Authentication failed:\n  {exc}\n")
        print("Common causes:")
        print("  - developer token wrong, or not from this manager account")
        print("  - GOOGLE_ADS_LOGIN_CUSTOMER_ID is not the manager (MCC) ID")
        print("  - refresh token expired (7-day limit while the OAuth app is")
        print("    in Testing mode) — redo the OAuth Playground step")
        return 1

    print(f"Authenticated against manager account {get_login_customer_id()}.\n")

    try:
        accounts = list_accounts(client=client)
    except Exception as exc:
        print(f"Authenticated, but could not read the account list:\n  {exc}")
        return 1

    if not accounts:
        print("No active client accounts found under this manager account.")
        return 0

    width = max(len(a["name"]) for a in accounts)
    print(f"{len(accounts)} client account(s) reachable:\n")
    for account in accounts:
        print(f"  {account['name']:<{width}}  {account['id']}  {account['currency']}")

    print("\nCONNECTED. Read access confirmed on all accounts above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
