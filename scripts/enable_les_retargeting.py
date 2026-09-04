"""Enable both Laser Engraver Store retargeting campaigns.

Trevor's call on 2026-09-03, after being told the audience lists are likely
below Google's serving thresholds. The downside is bounded: if they cannot
serve they simply spend nothing, so the cost of finding out is $0 and the
upside is that the lists may be larger than the reported figures suggest.

Pre-flight checks per campaign; refuses on any failure. The one that matters
for the Shopping campaign is the AUDIENCE target restriction -- if it were set
to observation rather than targeting, a campaign named "Retargeting Only" would
spend its budget on cold traffic.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

DISPLAY, SHOPPING = 24208833015, 24208833018
EXPECTED_BUDGET = 5_000_000


def check(ga, client, cust, cid, kind):
    problems = []
    rows = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.name, campaign.status, campaign.advertising_channel_type,
               campaign.bidding_strategy_type,
               campaign.geo_target_type_setting.positive_geo_target_type,
               campaign_budget.amount_micros, campaign_budget.explicitly_shared
        FROM campaign WHERE campaign.id = {cid}"""))
    if len(rows) != 1:
        return [f"campaign {cid} not found"], None
    c, b = rows[0].campaign, rows[0].campaign_budget
    print(f"\n{c.name}  [{c.status.name}]")
    print(f"  {c.advertising_channel_type.name} / {c.bidding_strategy_type.name} "
          f"/ ${b.amount_micros/1e6:.2f}/day / geo {c.geo_target_type_setting.positive_geo_target_type.name}")
    if b.amount_micros != EXPECTED_BUDGET:
        problems.append(f"{c.name}: budget ${b.amount_micros/1e6:.2f}, expected $5.00")
    if b.explicitly_shared:
        problems.append(f"{c.name}: budget is shared")
    if c.bidding_strategy_type.name != "MANUAL_CPC":
        problems.append(f"{c.name}: bidding is {c.bidding_strategy_type.name}, expected MANUAL_CPC")
    if c.geo_target_type_setting.positive_geo_target_type.name != "PRESENCE":
        problems.append(f"{c.name}: geo targeting is not PRESENCE")

    auds = [r.ad_group_criterion.display_name for r in ga.search(
        customer_id=cust, query=f"""
        SELECT ad_group_criterion.display_name FROM ad_group_criterion
        WHERE campaign.id = {cid} AND ad_group_criterion.type = 'USER_LIST'
          AND ad_group_criterion.status = 'ENABLED'""")]
    print(f"  audiences {len(auds)}")
    if not auds:
        problems.append(f"{c.name}: no audiences attached")

    ads = list(ga.search(customer_id=cust, query=f"""
        SELECT ad_group_ad.ad.id, ad_group_ad.policy_summary.approval_status
        FROM ad_group_ad WHERE campaign.id = {cid}
          AND ad_group_ad.status = 'ENABLED'"""))
    print(f"  ads {len(ads)} "
          f"{[a.ad_group_ad.policy_summary.approval_status.name for a in ads]}")
    if not ads:
        problems.append(f"{c.name}: no enabled ad")

    negs = [r.shared_set.name for r in ga.search(customer_id=cust, query=f"""
        SELECT shared_set.name FROM campaign_shared_set
        WHERE campaign.id = {cid} AND campaign_shared_set.status != 'REMOVED'""")]
    print(f"  negatives {negs}")

    if kind == "display":
        excluded = set()
        for r in ga.search(customer_id=cust, query=f"""
            SELECT campaign_criterion.device.type, campaign_criterion.bid_modifier
            FROM campaign_criterion WHERE campaign.id = {cid}
              AND campaign_criterion.type = 'DEVICE'
              AND campaign_criterion.status != 'REMOVED'"""):
            k = r.campaign_criterion
            if k._pb.HasField("bid_modifier") and k.bid_modifier == 0.0:
                excluded.add(k.device.type_.name)
        print(f"  devices excluded {sorted(excluded)}")
        for d in ("MOBILE", "TABLET"):
            if d not in excluded:
                problems.append(f"{c.name}: {d} is not excluded (desktop-only was the point)")
    else:
        ok = False
        for r in ga.search(customer_id=cust, query=f"""
            SELECT ad_group.targeting_setting.target_restrictions
            FROM ad_group WHERE campaign.id = {cid}"""):
            for t in r.ad_group.targeting_setting.target_restrictions:
                if t.targeting_dimension.name == "AUDIENCE":
                    ok = not t.bid_only
                    print(f"  AUDIENCE restriction bid_only={t.bid_only} -> "
                          f"{'TARGETING' if ok else 'OBSERVATION'}")
        if not ok:
            problems.append(f"{c.name}: AUDIENCE restriction is not TARGETING; "
                            f"the campaign would serve to cold traffic")
        lg = len(list(ga.search(customer_id=cust, query=f"""
            SELECT ad_group_criterion.criterion_id FROM ad_group_criterion
            WHERE campaign.id = {cid} AND ad_group_criterion.type = 'LISTING_GROUP'
              AND ad_group_criterion.status != 'REMOVED'""")))
        print(f"  listing group nodes {lg}")
        if lg < 1:
            problems.append(f"{c.name}: no listing group")
    return problems, c.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Laser Engraver Store")["id"]
    ga = client.get_service("GoogleAdsService")

    problems = []
    for cid, kind in ((DISPLAY, "display"), (SHOPPING, "shopping")):
        p, _ = check(ga, client, cust, cid, kind)
        problems += p

    if problems:
        print("\nREFUSING to enable:")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nAll pre-flight checks passed.")
    if not args.execute:
        print("Dry run only. Re-run with --execute to enable.")
        return 0

    svc = client.get_service("CampaignService")
    ops = []
    for cid in (DISPLAY, SHOPPING):
        op = client.get_type("CampaignOperation")
        op.update.resource_name = svc.campaign_path(cust, cid)
        op.update.status = client.enums.CampaignStatusEnum.ENABLED
        op.update_mask.paths.append("status")
        ops.append(op)
    svc.mutate_campaigns(customer_id=cust, operations=ops)

    print("\n-- verify --")
    for r in ga.search(customer_id=cust, query="""
        SELECT campaign.name, campaign.status, campaign_budget.amount_micros
        FROM campaign WHERE campaign.status = 'ENABLED'"""):
        print(f"  {r.campaign.name[:42]:44} [{r.campaign.status.name}] "
              f"${r.campaign_budget.amount_micros/1e6:.2f}/day")
    return 0


if __name__ == "__main__":
    sys.exit(main())
