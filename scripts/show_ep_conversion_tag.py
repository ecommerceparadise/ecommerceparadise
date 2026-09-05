"""Print the gtag send_to value for the niches-list conversion action.

The conversion label lives only in conversion_action.tag_snippets, which Google
generates after the action is created. The onsite snippet needs the full
'AW-<tracking id>/<label>' string, so this pulls it back out.
"""
import re
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACTION_ID = 7748493747


def main():
    client = get_client()
    cust = resolve_account("eCommerce Paradise")["id"]
    ga = client.get_service("GoogleAdsService")

    for r in ga.search(customer_id=cust, query=f"""
        SELECT conversion_action.id, conversion_action.name,
               conversion_action.status, conversion_action.category,
               conversion_action.primary_for_goal,
               conversion_action.include_in_conversions_metric,
               conversion_action.counting_type,
               conversion_action.tag_snippets
        FROM conversion_action WHERE conversion_action.id = {ACTION_ID} """):
        c = r.conversion_action
        print(f"[{c.id}] {c.name}")
        print(f"  status={c.status.name} category={c.category.name} "
              f"counting={c.counting_type.name}")
        print(f"  primary_for_goal={c.primary_for_goal} "
              f"include_in_conversions_metric={c.include_in_conversions_metric}")
        sends = set()
        for t in c.tag_snippets:
            for m in re.findall(r"AW-[\d]+/[\w\-]+", t.event_snippet or ""):
                sends.add(m)
        print(f"\n  send_to values found: {sorted(sends) or 'NONE'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
