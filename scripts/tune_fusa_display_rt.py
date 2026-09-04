"""Fountains USA dynamic display remarketing: audiences and desktop-only targeting.

Two changes:

  1. Add the "General visitors (Retail)" remarketing list (1,100 users on
     Display). The ad group already carries "Product viewers" (1,500) and
     "All Users of Fountains USA Shopify Store - GA4" (7,600). It also carries
     "Shopping cart abandoners", which has 16 users -- below the 100-user
     minimum Display requires, so it contributes nothing. Left in place because
     it costs nothing and will grow.

  2. Desktop only. Mobile, tablet and connected TV get a -100% bid modifier,
     which excludes them. Google's device criteria for this campaign currently
     have NO modifier set at all, so every device is presently eligible --
     including the in-app game inventory this is meant to avoid.

Deliberately NOT changed here: the bid. The campaign runs Maximize Conversions
with no conversion history, which is why nothing has served. The ad group's
CPC bid is $0.01, but under an automated strategy that value is ignored
entirely. Making the bid controllable means moving off Maximize Conversions,
which is a bid strategy change and needs its own decision.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24204679673
AD_GROUP = 202276525400

# (user list id, name, Display size) -- verified against this account.
ADD_LISTS = [
    (9187533871, "General visitors (Retail) (AdWords)", 1100),
]

EXCLUDE_DEVICES = ["MOBILE", "TABLET", "CONNECTED_TV"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Fountains USA")["id"]
    ga = client.get_service("GoogleAdsService")

    # What audiences are already on the ad group?
    present = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group_criterion.user_list.user_list,
               ad_group_criterion.display_name
        FROM ad_group_criterion WHERE ad_group.id = {AD_GROUP}
          AND ad_group_criterion.type = 'USER_LIST'
          AND ad_group_criterion.status != 'REMOVED'"""):
        k = r.ad_group_criterion
        present[k.user_list.user_list.split("/")[-1]] = k.display_name

    to_add = [(i, n, s) for i, n, s in ADD_LISTS if str(i) not in present]

    # Device criteria as they stand.
    devices = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign_criterion.resource_name, campaign_criterion.device.type,
               campaign_criterion.bid_modifier
        FROM campaign_criterion WHERE campaign.id = {CAMPAIGN}
          AND campaign_criterion.type = 'DEVICE'
          AND campaign_criterion.status != 'REMOVED'"""):
        k = r.campaign_criterion
        devices[k.device.type_.name] = (
            k.resource_name, k._pb.HasField("bid_modifier"), k.bid_modifier)

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)

    print(f"\nAUDIENCES already on ad group {AD_GROUP}:")
    for i, n in present.items():
        print(f"    {i}  {n}")
    print("\nAUDIENCES to add:")
    if to_add:
        for i, n, s in to_add:
            print(f"    {i}  {n}  ({s:,} on Display)")
    else:
        print("    none -- already present")

    print("\nDEVICES:")
    for d, (rn, has, val) in sorted(devices.items()):
        if d in EXCLUDE_DEVICES:
            state = f"modifier set to {val}" if has else "NO modifier -- currently eligible"
            print(f"    {d:14} {state}   ->  EXCLUDE (-100%)")
        else:
            print(f"    {d:14} left as is (this is the one we keep)")
    missing = [d for d in EXCLUDE_DEVICES if d not in devices]
    if missing:
        print(f"    NOTE: no criterion row for {missing}; will create it excluded.")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    if to_add:
        svc = client.get_service("AdGroupCriterionService")
        ag_path = client.get_service("AdGroupService").ad_group_path(cust, AD_GROUP)
        ul_svc = client.get_service("UserListService")
        ops = []
        for i, n, _ in to_add:
            op = client.get_type("AdGroupCriterionOperation")
            c = op.create
            c.ad_group = ag_path
            c.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
            c.user_list.user_list = ul_svc.user_list_path(cust, i)
            ops.append(op)
        svc.mutate_ad_group_criteria(customer_id=cust, operations=ops)
        print(f"\n  added {len(ops)} audience(s)")

    cc_svc = client.get_service("CampaignCriterionService")
    camp_path = client.get_service("CampaignService").campaign_path(cust, CAMPAIGN)
    ops = []
    for d in EXCLUDE_DEVICES:
        op = client.get_type("CampaignCriterionOperation")
        if d in devices:
            op.update.resource_name = devices[d][0]
            op.update.bid_modifier = 0.0
            op.update_mask.paths.append("bid_modifier")
        else:
            op.create.campaign = camp_path
            op.create.device.type_ = getattr(client.enums.DeviceEnum, d)
            op.create.bid_modifier = 0.0
        ops.append(op)
    cc_svc.mutate_campaign_criteria(customer_id=cust, operations=ops)
    print(f"  excluded {len(ops)} device types (-100%)")

    print("\n-- verify --")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign_criterion.device.type, campaign_criterion.bid_modifier
        FROM campaign_criterion WHERE campaign.id = {CAMPAIGN}
          AND campaign_criterion.type = 'DEVICE'
          AND campaign_criterion.status != 'REMOVED'"""):
        k = r.campaign_criterion
        has = k._pb.HasField("bid_modifier")
        state = "EXCLUDED" if (has and k.bid_modifier == 0.0) else "eligible"
        print(f"  {k.device.type_.name:14} {state}")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group_criterion.display_name FROM ad_group_criterion
        WHERE ad_group.id = {AD_GROUP} AND ad_group_criterion.type = 'USER_LIST'
          AND ad_group_criterion.status = 'ENABLED'"""):
        print(f"  audience: {r.ad_group_criterion.display_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
