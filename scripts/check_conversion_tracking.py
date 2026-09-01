"""Read-only: what conversion actions exist on an account, and are they healthy.

    python scripts/check_conversion_tracking.py "BetterPatio"

Checks status, type, category, whether value is expected from the tag vs. a
flat default, and whether each action is even counted in the conversions
metric. Changes nothing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_ads.auth import get_client  # noqa: E402
from google_ads.accounts import resolve_account  # noqa: E402

QUERY = """
    SELECT
      conversion_action.id,
      conversion_action.name,
      conversion_action.status,
      conversion_action.type,
      conversion_action.category,
      conversion_action.include_in_conversions_metric,
      conversion_action.primary_for_goal,
      conversion_action.value_settings.default_value,
      conversion_action.value_settings.always_use_default_value,
      conversion_action.click_through_lookback_window_days
    FROM conversion_action
"""

# conversions/conversions_value can't be joined to the conversion_action
# resource directly -- pull the same numbers, broken out per action, from
# campaign combined with the segments.conversion_action segment instead.
BY_ACTION_QUERY = """
    SELECT
      segments.conversion_action_name,
      metrics.conversions,
      metrics.conversions_value
    FROM campaign
    WHERE segments.date DURING LAST_30_DAYS
      AND metrics.conversions > 0
"""


def main():
    client = get_client()
    name = " ".join(sys.argv[1:]) or sys.exit("usage: check_conversion_tracking.py <account name or id>")
    account = resolve_account(name, client=client)
    ga_service = client.get_service("GoogleAdsService")

    print(f"\n{account['name']} ({account['id']}) — conversion actions\n")

    rows = list(ga_service.search(customer_id=account["id"], query=QUERY))
    if not rows:
        print("  NO CONVERSION ACTIONS CONFIGURED AT ALL.")
        return 0

    by_action = {}
    for row in ga_service.search(customer_id=account["id"], query=BY_ACTION_QUERY):
        key = row.segments.conversion_action_name
        entry = by_action.setdefault(key, {"conversions": 0.0, "value": 0.0})
        entry["conversions"] += row.metrics.conversions
        entry["value"] += row.metrics.conversions_value

    for row in rows:
        ca = row.conversion_action
        always_default = ca.value_settings.always_use_default_value
        print(f"  {ca.name}")
        print(f"    status={ca.status.name}  type={ca.type_.name}  category={ca.category.name}")
        print(f"    counted_in_conversions_metric={ca.include_in_conversions_metric}  primary_for_goal={ca.primary_for_goal}  id={ca.id}")
        print(
            f"    value setting: {'ALWAYS uses flat default (' + str(ca.value_settings.default_value) + ') -- real order value is IGNORED' if always_default else 'uses real value passed by the tag'}"
        )
        actual = by_action.get(ca.name)
        if actual:
            print(f"    last 30 days: {actual['conversions']:.1f} conversions, ${actual['value']:.2f} value")
        else:
            print(f"    last 30 days: 0 conversions recorded")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
