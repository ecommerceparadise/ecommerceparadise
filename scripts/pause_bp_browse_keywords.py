"""Pause the browse-intent keyword added in the Search rebuild.

"outdoor kitchen ideas" has the worst record of anything added: 2,071 clicks,
$1,153 spent, CPA $21 -- and every one of those conversions was a raw Zoho
lead upload, which measures a form fill, not a buyer. An "ideas" query is a
person collecting pictures. Trevor called it; the numbers back him.

"backyard kitchen ideas" is the same shape of query but has spent $49 in its
entire life at a $2 CPA, so it stays for now as a cheap test. Say the word and
it goes too.
"""
import sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

AD_GROUP = 190077137940
PAUSE = ["outdoor kitchen ideas"]


def main():
    client = get_client()
    cust = resolve_account("BetterPatio.com")["id"]
    ga = client.get_service("GoogleAdsService")

    q = f"""
      SELECT ad_group_criterion.resource_name, ad_group_criterion.keyword.text,
             ad_group_criterion.status, ad_group_criterion.negative
      FROM ad_group_criterion
      WHERE ad_group.id = {AD_GROUP}
        AND ad_group_criterion.type = 'KEYWORD'
        AND ad_group_criterion.status != 'REMOVED'
    """
    targets = []
    for r in ga.search(customer_id=cust, query=q):
        c = r.ad_group_criterion
        if c.negative:
            continue  # negatives are not updateable; only positives are targeted
        if c.keyword.text in PAUSE and c.status.name == "ENABLED":
            targets.append((c.resource_name, c.keyword.text))

    if not targets:
        print("Nothing to pause -- already paused or absent.")
        return 0

    svc = client.get_service("AdGroupCriterionService")
    ops = []
    for rn, text in targets:
        op = client.get_type("AdGroupCriterionOperation")
        op.update.resource_name = rn
        op.update.status = client.enums.AdGroupCriterionStatusEnum.PAUSED
        op.update_mask.paths.append("status")
        ops.append(op)
        print(f"PAUSE  {text}")

    svc.mutate_ad_group_criteria(customer_id=cust, operations=ops)
    print(f"\nPaused {len(ops)} keyword(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
