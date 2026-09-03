"""Replicate the core ad group's age exclusions onto the three new ad groups.

Ad group 190077137940 excludes ages 18-24, 25-34, 65+ and Undetermined, so it
only reaches 35-64. New ad groups start with no demographic exclusions at all,
which would have let them run to every age band -- a targeting mismatch against
the proven group. Income ranges need no action: all seven are targeted in the
source, which is the default.

Worth revisiting separately: excluding "Undetermined" age drops every user
Google cannot age-classify, which is a large share of search traffic. That is
the existing setup's choice, not one made here.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

SOURCE = 190077137940
TARGETS = [203689265510, 203689265670, 203689265710]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("BetterPatio.com")["id"]
    ga = client.get_service("GoogleAdsService")
    ag_svc = client.get_service("AdGroupService")

    q = f"""
      SELECT ad_group_criterion.age_range.type, ad_group_criterion.display_name
      FROM ad_group_criterion WHERE ad_group.id = {SOURCE}
        AND ad_group_criterion.type = 'AGE_RANGE'
        AND ad_group_criterion.negative = TRUE
        AND ad_group_criterion.status != 'REMOVED'
    """
    excluded = [(r.ad_group_criterion.age_range.type_.name,
                 r.ad_group_criterion.display_name)
                for r in ga.search(customer_id=cust, query=q)]

    print(f"Source ad group {SOURCE} excludes {len(excluded)} age bands:")
    for _, name in excluded:
        print(f"    {name}")
    print(f"-> applying to {len(TARGETS)} new ad groups "
          f"({len(excluded)*len(TARGETS)} operations)")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    svc = client.get_service("AdGroupCriterionService")
    for ag in TARGETS:
        ops = []
        for enum_name, _ in excluded:
            op = client.get_type("AdGroupCriterionOperation")
            c = op.create
            c.ad_group = ag_svc.ad_group_path(cust, ag)
            c.negative = True
            c.age_range.type_ = getattr(client.enums.AgeRangeTypeEnum, enum_name)
            ops.append(op)
        svc.mutate_ad_group_criteria(customer_id=cust, operations=ops)
        print(f"  ad group {ag}: {len(ops)} age exclusions added")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
