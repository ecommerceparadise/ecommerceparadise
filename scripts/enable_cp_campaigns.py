"""Pre-flight and enable the three Culinary Profis campaigns.

Built PAUSED on Trevor's instruction; this enables them after checking the
things that silently waste budget:

  - conversion tracking actually fires (the LES failure: a purchase tag that
    had never recorded a single conversion across 611 clicks, with PMax on
    Maximize Conversions and nothing to learn from)
  - remarketing lists have enough members to serve at all
  - the feed still has eligible products for every live asset group
  - the PMax is genuinely feed-only (no creative assets crept in)
  - geo targeting is PRESENCE, not PRESENCE_OR_INTEREST

Run with no flags for the pre-flight report. Pass --execute to enable.
"""
import argparse
import sys
from collections import defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "Culinary Profis"
CAMPAIGNS = {
    24222890101: "CP - PMax - Culinary (feed only)",
    24211935318: "CP - Display Remarketing",
    24211933860: "CP - Shopping - Retargeting Only",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")

    problems, warnings = [], []
    ids = ",".join(str(i) for i in CAMPAIGNS)

    # --- campaign settings ---------------------------------------------------
    print("== campaigns ==")
    seen = set()
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.bidding_strategy_type, campaign.advertising_channel_type,
               campaign_budget.amount_micros, campaign_budget.explicitly_shared
        FROM campaign WHERE campaign.id IN ({ids}) """):
        c, b = r.campaign, r.campaign_budget
        seen.add(c.id)
        print(f"  [{c.id}] {c.name}")
        print(f"      {c.status.name} / {c.advertising_channel_type.name} / "
              f"{c.bidding_strategy_type.name} / ${b.amount_micros/1e6:.2f}/day")
        if b.explicitly_shared:
            warnings.append(f"{c.name}: budget is SHARED -- enabling affects "
                            f"other campaigns on the same budget")
    missing = set(CAMPAIGNS) - seen
    if missing:
        problems.append(f"campaigns not found: {missing}")

    # --- geo targeting -------------------------------------------------------
    print("\n== geo targeting ==")
    geo = defaultdict(set)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.geo_target_type_setting.positive_geo_target_type
        FROM campaign WHERE campaign.id IN ({ids}) """):
        t = r.campaign.geo_target_type_setting.positive_geo_target_type.name
        geo[t].add(CAMPAIGNS[r.campaign.id])
        if t != "PRESENCE":
            problems.append(f"{CAMPAIGNS[r.campaign.id]}: positive geo target "
                            f"is {t}, must be PRESENCE")
    for t, names in geo.items():
        print(f"  {t}: {len(names)} campaign(s)")

    # --- conversion tracking -------------------------------------------------
    print("\n== conversion actions ==")
    actions = []
    for r in ga.search(customer_id=cust, query="""
        SELECT conversion_action.id, conversion_action.name,
               conversion_action.status, conversion_action.type,
               conversion_action.category, conversion_action.primary_for_goal
        FROM conversion_action
        WHERE conversion_action.status = 'ENABLED' """):
        c = r.conversion_action
        actions.append(c)
        print(f"  [{c.id}] {c.name}  {c.type_.name} / {c.category.name} "
              f"primary={c.primary_for_goal}")
    if not actions:
        problems.append("no ENABLED conversion actions in the account")

    print("\n== conversions recorded, last 90 days ==")
    fired = defaultdict(float)
    for r in ga.search(customer_id=cust, query="""
        SELECT segments.conversion_action_name, metrics.all_conversions
        FROM customer
        WHERE segments.date BETWEEN '2026-06-09' AND '2026-09-07' """):
        fired[r.segments.conversion_action_name] += r.metrics.all_conversions
    if fired:
        for name, v in sorted(fired.items(), key=lambda kv: -kv[1]):
            print(f"  {name}: {v:.1f}")
    else:
        print("  NONE -- no conversion of any kind recorded in 90 days")
        warnings.append("no conversions recorded account-wide in 90 days: "
                        "Smart Bidding has nothing to learn from")

    # --- remarketing list sizes ---------------------------------------------
    print("\n== audiences attached to the retargeting campaigns ==")
    lists = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT user_list.id, user_list.name, user_list.size_for_display,
               user_list.size_for_search, user_list.membership_status
        FROM user_list """):
        u = r.user_list
        lists[u.resource_name] = u

    # Audiences may live at campaign OR ad group level. Display and Shopping
    # campaigns attach them at ad group level -- checking only campaign level
    # reports a false "no audiences attached".
    attached = defaultdict(list)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign_criterion.user_list.user_list,
               campaign_criterion.negative
        FROM campaign_criterion
        WHERE campaign.id IN ({ids})
          AND campaign_criterion.type = 'USER_LIST'
          AND campaign_criterion.status != 'REMOVED' """):
        attached[r.campaign.id].append(
            (r.campaign_criterion.user_list.user_list,
             r.campaign_criterion.negative, "campaign"))
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, ad_group_criterion.user_list.user_list,
               ad_group_criterion.negative
        FROM ad_group_criterion
        WHERE campaign.id IN ({ids})
          AND ad_group_criterion.type = 'USER_LIST'
          AND ad_group_criterion.status != 'REMOVED' """):
        attached[r.campaign.id].append(
            (r.ad_group_criterion.user_list.user_list,
             r.ad_group_criterion.negative, "ad group"))

    for cid in (24211935318, 24211933860):
        rows = attached.get(cid, [])
        if not rows:
            problems.append(f"{CAMPAIGNS[cid]}: no user lists attached -- "
                            f"cannot serve as retargeting")
            continue
        need_search = cid == 24211933860
        servable = 0
        print(f"  {CAMPAIGNS[cid]}:")
        for rn, negative, level in rows:
            u = lists.get(rn)
            if not u or negative:
                continue
            size = u.size_for_search if need_search else u.size_for_display
            floor = 1000 if need_search else 100
            mark = "" if size >= floor else "   (below serving minimum)"
            servable += size >= floor
            print(f"      {u.name}  display={u.size_for_display} "
                  f"search={u.size_for_search}  [{level}]{mark}")
        if not servable:
            problems.append(
                f"{CAMPAIGNS[cid]}: no attached list clears the serving minimum")

    # --- audience targeting mode (campaign or ad group level) ----------------
    print("\n== audience targeting mode ==")
    modes = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.targeting_setting.target_restrictions
        FROM campaign WHERE campaign.id IN ({ids}) """):
        for tr in r.campaign.targeting_setting.target_restrictions:
            if tr.targeting_dimension.name == "AUDIENCE":
                modes[r.campaign.id] = ("campaign", tr.bid_only)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, ad_group.targeting_setting.target_restrictions
        FROM ad_group WHERE campaign.id IN ({ids})
          AND ad_group.status != 'REMOVED' """):
        for tr in r.ad_group.targeting_setting.target_restrictions:
            if tr.targeting_dimension.name == "AUDIENCE":
                modes[r.campaign.id] = ("ad group", tr.bid_only)

    for cid in (24211935318, 24211933860):
        if cid not in modes:
            print(f"  {CAMPAIGNS[cid]}: no explicit AUDIENCE restriction "
                  f"(defaults to targeting)")
            continue
        level, bid_only = modes[cid]
        print(f"  {CAMPAIGNS[cid]}: "
              f"{'OBSERVATION' if bid_only else 'TARGETING'} [{level}]")
        if bid_only:
            problems.append(
                f"{CAMPAIGNS[cid]}: audience restriction is OBSERVATION -- "
                f"would serve to cold traffic, not retargeting")

    # --- feed-only integrity + product eligibility ---------------------------
    print("\n== PMax asset groups ==")
    groups = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT asset_group.id, asset_group.name, asset_group.status
        FROM asset_group WHERE campaign.id = 24222890101
          AND asset_group.status != 'REMOVED' """):
        groups[r.asset_group.id] = r.asset_group.name
    print(f"  {len(groups)} live asset groups: {sorted(groups.values())}")

    creative = defaultdict(int)
    for r in ga.search(customer_id=cust, query="""
        SELECT asset_group.name, asset_group_asset.field_type
        FROM asset_group_asset WHERE campaign.id = 24222890101 """):
        creative[r.asset_group.name] += 1
    if creative:
        problems.append(f"asset groups carry creative assets {dict(creative)} -- "
                        f"campaign is no longer feed-only")
    else:
        print("  feed-only confirmed: zero creative assets")

    print("\n== product eligibility by brand ==")
    ok, dead = defaultdict(int), defaultdict(int)
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.issues
        FROM shopping_product """):
        p = r.shopping_product
        blocking = {i.error_code for i in p.issues} - {"not_eligible_in_any_campaign"}
        # Feed brands come back lowercase; asset group names are title-case.
        (dead if blocking else ok)[p.brand.strip().lower()] += 1
    for name in sorted(groups.values()):
        brand = name.replace("CP - ", "").strip().lower()
        live, bad = ok.get(brand, 0), dead.get(brand, 0)
        flag = "  <-- NO ELIGIBLE PRODUCTS" if live == 0 else ""
        print(f"  {brand:16} eligible={live:4}  blocked={bad:4}{flag}")
        if live == 0:
            problems.append(f"asset group '{name}' has no eligible products")

    # --- verdict -------------------------------------------------------------
    print("\n" + "=" * 60)
    for w in warnings:
        print(f"  WARNING: {w}")
    for p in problems:
        print(f"  PROBLEM: {p}")
    if problems:
        print("\nRefusing to enable. Fix the problems above first.")
        return 1
    if not args.execute:
        print("\nPre-flight clean. Re-run with --execute to enable.")
        return 0

    svc = client.get_service("CampaignService")
    ops = []
    for cid in CAMPAIGNS:
        op = client.get_type("CampaignOperation")
        op.update.resource_name = (
            client.get_service("CampaignService").campaign_path(cust, cid))
        op.update.status = client.enums.CampaignStatusEnum.ENABLED
        op.update_mask.paths.append("status")
        ops.append(op)
    svc.mutate_campaigns(customer_id=cust, operations=ops)
    print(f"\n  ENABLED {len(ops)} campaigns.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
