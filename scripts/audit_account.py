"""Read-only account overview: campaigns, spend, structure, settings drift.

Generic across the managed accounts -- pass the account name.
"""
import argparse, sys
from collections import defaultdict
from google_ads.auth import get_client
from google_ads.accounts import resolve_account


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("account")
    ap.add_argument("--days", default="LAST_30_DAYS")
    args = ap.parse_args()

    client = get_client()
    acct = resolve_account(args.account)
    cust = acct["id"]
    ga = client.get_service("GoogleAdsService")
    print(f"ACCOUNT {acct['name']} ({cust})  window={args.days}\n")

    print("=" * 96)
    print("CAMPAIGNS")
    print("=" * 96)
    perf = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.all_conversions, metrics.conversions_value,
               metrics.search_impression_share,
               metrics.search_budget_lost_impression_share,
               metrics.search_rank_lost_impression_share
        FROM campaign WHERE segments.date DURING {args.days}"""):
        perf[r.campaign.id] = r.metrics

    rows = []
    for r in ga.search(customer_id=cust, query="""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type, campaign.bidding_strategy_type,
               campaign.network_settings.target_search_network,
               campaign.network_settings.target_content_network,
               campaign_budget.amount_micros
        FROM campaign WHERE campaign.status != 'REMOVED'"""):
        rows.append(r)
    rows.sort(key=lambda r: -(perf[r.campaign.id].cost_micros if r.campaign.id in perf else 0))

    live_budget = 0.0
    print(f"{'id':>12} {'name':40} {'status':8} {'channel':10} {'bidding':22} "
          f"{'budget':>8} {'cost':>9} {'clicks':>7} {'conv':>6} {'value':>10}")
    for r in rows:
        c, b = r.campaign, r.campaign_budget
        m = perf.get(c.id)
        cost = m.cost_micros/1e6 if m else 0
        if c.status.name == "ENABLED":
            live_budget += b.amount_micros/1e6
        print(f"{c.id:>12} {c.name[:38]:40} {c.status.name[:8]:8} "
              f"{c.advertising_channel_type.name[:10]:10} {c.bidding_strategy_type.name[:22]:22} "
              f"{b.amount_micros/1e6:>8.2f} {cost:>9.2f} "
              f"{(m.clicks if m else 0):>7} {(m.all_conversions if m else 0):>6.1f} "
              f"{(m.conversions_value if m else 0):>10.2f}")
    print(f"\n  enabled campaigns' daily budget total: ${live_budget:,.2f}/day")

    print("\n" + "=" * 96)
    print("ENABLED SEARCH CAMPAIGNS -- impression share")
    print("=" * 96)
    for r in rows:
        c = r.campaign
        m = perf.get(c.id)
        if c.status.name != "ENABLED" or not m or c.advertising_channel_type.name != "SEARCH":
            continue
        print(f"  {c.name[:44]:46} IS={m.search_impression_share:6.1%} "
              f"lost_budget={m.search_budget_lost_impression_share:6.1%} "
              f"lost_rank={m.search_rank_lost_impression_share:6.1%}")

    print("\n" + "=" * 96)
    print("AD GROUP COUNT AND KEYWORDS PER GROUP (SKAG check, enabled only)")
    print("=" * 96)
    kw = defaultdict(lambda: defaultdict(int))
    names = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT campaign.name, ad_group.id, ad_group.name
        FROM ad_group_criterion
        WHERE ad_group_criterion.type = 'KEYWORD'
          AND ad_group_criterion.negative = FALSE
          AND ad_group_criterion.status = 'ENABLED'
          AND ad_group.status = 'ENABLED' AND campaign.status = 'ENABLED'"""):
        kw[r.campaign.name][r.ad_group.id] += 1
        names[r.ad_group.id] = r.ad_group.name
    for camp, groups in sorted(kw.items()):
        counts = sorted(groups.values())
        skag = sum(1 for v in counts if v <= 2)
        print(f"  {camp[:46]:48} {len(groups):>4} ad groups, "
              f"{sum(counts):>5} keywords, {skag} are SKAG-shaped (<=2 kw)")

    print("\n" + "=" * 96)
    print("SETTINGS DRIFT")
    print("=" * 96)
    for r in rows:
        c = r.campaign
        if c.status.name != "ENABLED":
            continue
        flags = []
        n = c.network_settings
        if c.advertising_channel_type.name == "SEARCH":
            if n.target_search_network:
                flags.append("search partners ON")
            if n.target_content_network:
                flags.append("display expansion ON")
        if flags:
            print(f"  {c.name[:46]:48} {', '.join(flags)}")
    for r in ga.search(customer_id=cust, query="""
        SELECT campaign.id, campaign.name,
               campaign.geo_target_type_setting.positive_geo_target_type
        FROM campaign WHERE campaign.status = 'ENABLED'"""):
        t = r.campaign.geo_target_type_setting.positive_geo_target_type.name
        if t != "PRESENCE":
            print(f"  {r.campaign.name[:46]:48} geo target type = {t}  (should be PRESENCE)")

    print("\n" + "=" * 96)
    print("NEGATIVE LISTS APPLIED TO ENABLED CAMPAIGNS")
    print("=" * 96)
    applied = defaultdict(list)
    for r in ga.search(customer_id=cust, query="""
        SELECT campaign.id, campaign.name, campaign.status, shared_set.name
        FROM campaign_shared_set WHERE campaign_shared_set.status != 'REMOVED'"""):
        if r.campaign.status.name == "ENABLED":
            applied[r.campaign.name].append(r.shared_set.name)
    enabled_names = {r.campaign.name for r in rows if r.campaign.status.name == "ENABLED"}
    for n in sorted(enabled_names):
        print(f"  {n[:46]:48} {applied.get(n) or 'NONE'}")

    print("\n" + "=" * 96)
    print("CONVERSION ACTIONS carrying data in this window")
    print("=" * 96)
    seen = defaultdict(lambda: [0.0, 0.0])
    for r in ga.search(customer_id=cust, query=f"""
        SELECT segments.conversion_action_name, segments.conversion_action_category,
               metrics.conversions, metrics.all_conversions
        FROM customer WHERE segments.date DURING {args.days}"""):
        k = (r.segments.conversion_action_name, r.segments.conversion_action_category.name)
        seen[k][0] += r.metrics.conversions
        seen[k][1] += r.metrics.all_conversions
    print(f"  {'action':46} {'category':18} {'bid-on':>8} {'all':>8}")
    for k, v in sorted(seen.items(), key=lambda x: -x[1][1]):
        print(f"  {k[0][:44]:46} {k[1][:18]:18} {v[0]:>8.1f} {v[1]:>8.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
