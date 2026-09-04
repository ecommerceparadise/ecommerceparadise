"""Attach the remaining Analytics and Google Ads remarketing lists to both
Fountains USA retargeting campaigns.

The account holds 17 open lists, but most are duplicates: five identical copies
of "All visitors (AdWords)" at 3,200/2,100 each, plus system-defined twins of
the General visitors, Product viewers and cart abandoner lists already
attached. Attaching duplicates adds no reach and makes the audience report
unreadable, so this adds one of each distinct list only.

Added here (none of these are on either campaign yet):

  AdWords optimized list      9,200 search / 8,300 display  -- the largest
  All visitors (AdWords)      3,200 / 2,100                 -- one of five copies
  All Converters                190 /    88
  Purchasers of ... GA4          48 /    48

Skipped deliberately: the four system-defined duplicates of lists already on
the campaigns, the four surplus "All visitors" copies, and both "Past buyers"
lists (8 users, and themselves duplicates).

Worth a decision separately: All Converters and Purchasers are people who have
already bought. Adding them as TARGETING audiences means these campaigns can
spend on re-showing ads to existing customers. For a $2,595-median fountain
that is usually low value, and the common setup is to EXCLUDE them instead.
They are added here because Trevor asked for the remarketing lists; say the
word and they become exclusions.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGNS = {
    24214263728: "FUSA - Shopping - Retargeting Only",
    24204679673: "FUSA - Dynamic Display Remarketing",
}

ADD = [
    (9176468083, "AdWords optimized list"),
    (9177340115, "All visitors (AdWords)"),
    (9194820544, "All Converters"),
    (9204844606, "Purchasers of Fountains USA Shopify Store - GA4"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Fountains USA")["id"]
    ga = client.get_service("GoogleAdsService")

    sizes = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT user_list.id, user_list.size_for_search, user_list.size_for_display
        FROM user_list"""):
        sizes[r.user_list.id] = (r.user_list.size_for_search,
                                 r.user_list.size_for_display)

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)

    plan = {}
    for cid, name in CAMPAIGNS.items():
        rows = list(ga.search(customer_id=cust, query=f"""
            SELECT ad_group.id, ad_group_criterion.user_list.user_list
            FROM ad_group_criterion WHERE campaign.id = {cid}
              AND ad_group_criterion.type = 'USER_LIST'
              AND ad_group_criterion.status = 'ENABLED'"""))
        if not rows:
            print(f"\n{name}: no ad group with audiences found. Skipping.")
            continue
        ad_group_id = rows[0].ad_group.id
        have = {int(r.ad_group_criterion.user_list.user_list.split("/")[-1])
                for r in rows}
        todo = [(i, n) for i, n in ADD if i not in have]
        plan[cid] = (name, ad_group_id, todo)
        print(f"\n{name}  (ad group {ad_group_id})")
        print(f"  already has {len(have)} lists")
        for i, n in todo:
            s, d = sizes.get(i, (0, 0))
            print(f"  + {i}  {n[:44]:46} search={s:>6} display={d:>6}")
        if not todo:
            print("  nothing to add")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    svc = client.get_service("AdGroupCriterionService")
    ag_svc = client.get_service("AdGroupService")
    ul_svc = client.get_service("UserListService")
    for cid, (name, ad_group_id, todo) in plan.items():
        if not todo:
            continue
        ops = []
        for uid, _ in todo:
            op = client.get_type("AdGroupCriterionOperation")
            c = op.create
            c.ad_group = ag_svc.ad_group_path(cust, ad_group_id)
            c.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
            c.user_list.user_list = ul_svc.user_list_path(cust, uid)
            ops.append(op)
        svc.mutate_ad_group_criteria(customer_id=cust, operations=ops)
        print(f"\n  {name}: added {len(ops)} lists")

    print("\n-- verify --")
    for cid, name in CAMPAIGNS.items():
        print(f"\n{name}")
        total_s = 0
        for r in ga.search(customer_id=cust, query=f"""
            SELECT ad_group_criterion.display_name,
                   ad_group_criterion.user_list.user_list
            FROM ad_group_criterion WHERE campaign.id = {cid}
              AND ad_group_criterion.type = 'USER_LIST'
              AND ad_group_criterion.status = 'ENABLED'"""):
            uid = int(r.ad_group_criterion.user_list.user_list.split("/")[-1])
            s, d = sizes.get(uid, (0, 0))
            total_s += s
            print(f"    {r.ad_group_criterion.display_name[:46]:48} "
                  f"search={s:>6} display={d:>6}")
        print(f"    (sum of search sizes, before overlap: {total_s:,})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
