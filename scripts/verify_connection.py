"""Read-only check that the Google Ads API connection works.

    python scripts/verify_connection.py

Makes no changes to any account. Run this after setting credentials, and any
time you suspect the connection has broken.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_ads.auth import get_client, get_customer_id, missing_vars  # noqa: E402


def main():
    absent = missing_vars()
    if absent:
        print("NOT CONNECTED. Missing credentials:\n")
        for var in absent:
            print(f"  - {var}")
        print("\nSee README.md for where each value comes from.")
        return 1

    print("Credentials found. Testing API connection...\n")

    try:
        client = get_client()
    except Exception as exc:
        print(f"Could not build the client: {exc}")
        return 1

    # 1. Which accounts can these credentials reach?
    try:
        customer_service = client.get_service("CustomerService")
        accessible = customer_service.list_accessible_customers()
    except Exception as exc:
        print(f"Auth failed when listing accessible accounts:\n  {exc}\n")
        print("Common causes:")
        print("  - developer token is wrong, or not approved for this manager account")
        print("  - GOOGLE_ADS_LOGIN_CUSTOMER_ID is not the manager (MCC) account ID")
        print("  - the signing-in email is not a test user on the OAuth consent screen")
        return 1

    ids = [name.split("/")[-1] for name in accessible.resource_names]
    print(f"Authenticated. {len(ids)} account(s) reachable:")
    for account_id in ids:
        print(f"  - {account_id}")

    # 2. Can we read the target account?
    try:
        customer_id = get_customer_id()
    except RuntimeError as exc:
        print(f"\nAuth works, but no target account set.\n  {exc}")
        return 1

    print(f"\nReading campaigns from target account {customer_id}...")

    query = """
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type
        FROM campaign
        ORDER BY campaign.id
        LIMIT 10
    """

    try:
        ga_service = client.get_service("GoogleAdsService")
        rows = list(ga_service.search(customer_id=customer_id, query=query))
    except Exception as exc:
        print(f"Could not read that account:\n  {exc}\n")
        print("Check that GOOGLE_ADS_CUSTOMER_ID is linked under the manager account")
        print("and that the link invitation was accepted.")
        return 1

    if not rows:
        print("  (no campaigns yet — the connection works, the account is just empty)")
    else:
        for row in rows:
            print(
                f"  [{row.campaign.status.name}] {row.campaign.id} "
                f"{row.campaign.name} ({row.campaign.advertising_channel_type.name})"
            )

    print("\nCONNECTED. Read access confirmed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
