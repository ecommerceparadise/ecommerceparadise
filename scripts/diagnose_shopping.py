"""Read-only: why is an enabled Shopping campaign spending nothing?

    python scripts/diagnose_shopping.py "Laser Engraver Store"

Checks the usual culprits the Ads API can see: missing Merchant Center
link, ad groups paused under an enabled campaign, and an empty or
fully-excluded product partition tree. Merchant Center feed disapprovals
are NOT visible here -- that needs Merchant Center access.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_ads.auth import get_client  # noqa: E402
from google_ads.accounts import resolve_account  # noqa: E402

SHOPPING_CAMPAIGNS_QUERY = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.status,
      campaign.shopping_setting.merchant_id,
      campaign.shopping_setting.campaign_priority,
      campaign.bidding_strategy_type,
      campaign_budget.amount_micros,
      campaign_budget.explicitly_shared
    FROM campaign
    WHERE campaign.advertising_channel_type = 'SHOPPING'
      AND campaign.status = 'ENABLED'
"""

AD_GROUPS_QUERY = """
    SELECT campaign.id, ad_group.id, ad_group.name, ad_group.status
    FROM ad_group
    WHERE campaign.advertising_channel_type = 'SHOPPING'
"""

LISTING_GROUPS_QUERY = """
    SELECT
      campaign.id,
      ad_group.id,
      ad_group_criterion.criterion_id,
      ad_group_criterion.status,
      ad_group_criterion.negative,
      ad_group_criterion.listing_group.type
    FROM ad_group_criterion
    WHERE ad_group_criterion.type = 'LISTING_GROUP'
"""


def main():
    client = get_client()
    name = " ".join(sys.argv[1:])
    if not name:
        sys.exit("usage: diagnose_shopping.py <account name or id>")

    account = resolve_account(name, client=client)
    cid = account["id"]
    ga = client.get_service("GoogleAdsService")

    print(f"\n{account['name']} ({cid}) -- enabled Shopping campaigns\n")

    campaigns = {}
    for row in ga.search(customer_id=cid, query=SHOPPING_CAMPAIGNS_QUERY):
        campaigns[row.campaign.id] = {
            "name": row.campaign.name,
            "merchant_id": row.campaign.shopping_setting.merchant_id,
            "priority": row.campaign.shopping_setting.campaign_priority,
            "bidding": row.campaign.bidding_strategy_type.name,
            "budget": row.campaign_budget.amount_micros / 1_000_000,
            "shared_budget": row.campaign_budget.explicitly_shared,
            "ad_groups": [],
            "listing_groups": 0,
            "negative_listing_groups": 0,
        }

    if not campaigns:
        print("  No enabled Shopping campaigns.")
        return 0

    for row in ga.search(customer_id=cid, query=AD_GROUPS_QUERY):
        if row.campaign.id in campaigns:
            campaigns[row.campaign.id]["ad_groups"].append(
                (row.ad_group.name, row.ad_group.status.name)
            )

    for row in ga.search(customer_id=cid, query=LISTING_GROUPS_QUERY):
        if row.campaign.id in campaigns:
            campaigns[row.campaign.id]["listing_groups"] += 1
            if row.ad_group_criterion.negative:
                campaigns[row.campaign.id]["negative_listing_groups"] += 1

    for cid_key, c in campaigns.items():
        print(f"  {c['name']}")
        print(f"    merchant_id={c['merchant_id'] or 'NOT LINKED'}  priority={c['priority']}  bidding={c['bidding']}")
        print(f"    budget=${c['budget']:.2f}/day  shared_budget={c['shared_budget']}")

        enabled_ags = [a for a in c["ad_groups"] if a[1] == "ENABLED"]
        print(f"    ad groups: {len(c['ad_groups'])} total, {len(enabled_ags)} ENABLED")
        for ag_name, ag_status in c["ad_groups"]:
            if ag_status != "ENABLED":
                print(f"      [{ag_status}] {ag_name}")

        print(
            f"    product partitions: {c['listing_groups']} "
            f"({c['negative_listing_groups']} excluded)"
        )

        problems = []
        if not c["merchant_id"]:
            problems.append("NO MERCHANT CENTER LINKED -- cannot serve")
        if not enabled_ags:
            problems.append("NO ENABLED AD GROUPS -- cannot serve")
        if c["listing_groups"] == 0:
            problems.append("NO PRODUCT PARTITIONS -- nothing to advertise")
        elif c["negative_listing_groups"] == c["listing_groups"]:
            problems.append("ALL PRODUCT PARTITIONS EXCLUDED -- nothing can serve")
        if c["budget"] == 0:
            problems.append("ZERO BUDGET")

        if problems:
            for p in problems:
                print(f"    >>> {p}")
        else:
            print("    >>> Ads-API-visible config looks serviceable.")
            print("        Remaining likely causes are outside this API:")
            print("        Merchant Center product disapprovals, feed expiry,")
            print("        account suspension, or bids below the auction floor.")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
