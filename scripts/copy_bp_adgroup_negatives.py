"""Copy the core ad group's 224 ad-group-level negatives to the new ad groups.

The three campaign-level shared negative lists (EP Generic, BP Generic
Irrelevants, irrelevant nkws jun week 1) already cover every ad group in the
campaign. But ad group 190077137940 also carries 224 negatives of its own --
mostly grill brand names -- and those do NOT propagate. Without this the new
ad groups would run unprotected.
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
      SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type
      FROM ad_group_criterion
      WHERE ad_group.id = {SOURCE}
        AND ad_group_criterion.type = 'KEYWORD'
        AND ad_group_criterion.negative = TRUE
        AND ad_group_criterion.status != 'REMOVED'
    """
    negs = [(r.ad_group_criterion.keyword.text,
             r.ad_group_criterion.keyword.match_type.name)
            for r in ga.search(customer_id=cust, query=q)]

    print(f"{len(negs)} negatives in source ad group {SOURCE}")
    print(f"-> copying to {len(TARGETS)} ad groups = {len(negs)*len(TARGETS)} operations")
    print("  sample:", ", ".join(f"{t} [{m[:1]}]" for t, m in negs[:8]))

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    svc = client.get_service("AdGroupCriterionService")
    for ag in TARGETS:
        ops = []
        for text, mt in negs:
            op = client.get_type("AdGroupCriterionOperation")
            c = op.create
            c.ad_group = ag_svc.ad_group_path(cust, ag)
            c.negative = True
            c.keyword.text = text
            c.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, mt)
            ops.append(op)
        svc.mutate_ad_group_criteria(customer_id=cust, operations=ops)
        print(f"  ad group {ag}: {len(ops)} negatives added")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
