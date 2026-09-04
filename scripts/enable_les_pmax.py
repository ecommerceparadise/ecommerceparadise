"""Enable the Laser Engraver Store feed-only PMax campaign.

Trevor said "enable" on 2026-09-03. Only this campaign -- the display and
Shopping retargeting campaigns stay paused until the remarketing lists cross
Google's serving thresholds.

Pre-flight checks run first and the script refuses on any failure. The one
worth calling out is the feed-only check: if an asset group has picked up
creative assets, the campaign is no longer Shopping-only and would start
serving text and display ads built from a store that has never converted.
"""
import argparse
import sys
from collections import defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24208827507
EXPECTED_BUDGET_MICROS = 15_000_000
EXPECTED_ASSET_GROUPS = 5
EXPECTED_THEMES_PER_GROUP = 15


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Laser Engraver Store")["id"]
    ga = client.get_service("GoogleAdsService")
    problems = []

    rows = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.name, campaign.status, campaign.advertising_channel_type,
               campaign.bidding_strategy_type, campaign.shopping_setting.merchant_id,
               campaign.geo_target_type_setting.positive_geo_target_type,
               campaign.asset_automation_settings,
               campaign_budget.amount_micros, campaign_budget.explicitly_shared
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""))
    if len(rows) != 1:
        print(f"Expected 1 campaign, got {len(rows)}. Aborting.")
        return 1
    c, b = rows[0].campaign, rows[0].campaign_budget
    print(f"Campaign: {c.name}  [{c.status.name}]")
    print(f"  channel   {c.advertising_channel_type.name}")
    print(f"  bidding   {c.bidding_strategy_type.name}")
    print(f"  merchant  {c.shopping_setting.merchant_id}")
    print(f"  geo type  {c.geo_target_type_setting.positive_geo_target_type.name}")
    print(f"  budget    ${b.amount_micros/1e6:.2f}/day shared={b.explicitly_shared}")

    if b.amount_micros != EXPECTED_BUDGET_MICROS:
        problems.append(f"budget ${b.amount_micros/1e6:.2f}, expected $15.00")
    if b.explicitly_shared:
        problems.append("budget is shared with other campaigns")
    if not c.shopping_setting.merchant_id:
        problems.append("no merchant id")
    if c.geo_target_type_setting.positive_geo_target_type.name != "PRESENCE":
        problems.append("geo targeting is not PRESENCE")
    opted = {a.asset_automation_type.name for a in c.asset_automation_settings
             if a.asset_automation_status.name == "OPTED_OUT"}
    print(f"  automations opted out: {len(opted)}")
    if "FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION" not in opted:
        problems.append("final URL expansion is not opted out")

    geos = len(list(ga.search(customer_id=cust, query=f"""
        SELECT campaign_criterion.criterion_id FROM campaign_criterion
        WHERE campaign.id = {CAMPAIGN} AND campaign_criterion.type = 'LOCATION'
          AND campaign_criterion.negative = FALSE
          AND campaign_criterion.status != 'REMOVED'""")))
    print(f"  locations {geos}")
    if geos != 48:
        problems.append(f"{geos} locations targeted, expected 48")

    negs = [r.shared_set.name for r in ga.search(customer_id=cust, query=f"""
        SELECT shared_set.name FROM campaign_shared_set
        WHERE campaign.id = {CAMPAIGN} AND campaign_shared_set.status != 'REMOVED'""")]
    print(f"  negatives {negs}")
    if not negs:
        problems.append("no negative keyword lists applied")

    groups = {r.asset_group.id: r.asset_group.name for r in ga.search(
        customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status
        FROM asset_group WHERE campaign.id = {CAMPAIGN}
          AND asset_group.status = 'ENABLED'""")}
    print(f"  asset groups {len(groups)}")
    if len(groups) != EXPECTED_ASSET_GROUPS:
        problems.append(f"{len(groups)} enabled asset groups, expected {EXPECTED_ASSET_GROUPS}")

    # Feed-only integrity: no creative assets anywhere in the campaign.
    creative = defaultdict(int)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group_asset.field_type
        FROM asset_group_asset WHERE campaign.id = {CAMPAIGN}
          AND asset_group_asset.status != 'REMOVED'"""):
        creative[r.asset_group.name] += 1
    if creative:
        problems.append(f"asset groups carry creative assets: {dict(creative)} "
                        f"-- campaign is no longer feed-only")
    else:
        print("  creative assets 0 (feed-only intact)")

    sig = defaultdict(lambda: [0, 0])
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        s = r.asset_group_signal
        if s.search_theme.text:
            sig[r.asset_group.id][0] += 1
        else:
            sig[r.asset_group.id][1] += 1
    for agid, name in groups.items():
        t, a = sig.get(agid, [0, 0])
        print(f"    {name[:30]:32} {t:>3} themes, {a} audience signal(s)")
        if t != EXPECTED_THEMES_PER_GROUP:
            problems.append(f"{name}: {t} search themes, expected {EXPECTED_THEMES_PER_GROUP}")
        if a < 1:
            problems.append(f"{name}: no audience signal")
        filters = len(list(ga.search(customer_id=cust, query=f"""
            SELECT asset_group_listing_group_filter.id
            FROM asset_group_listing_group_filter
            WHERE asset_group.id = {agid}""")))
        if filters < 3:
            problems.append(f"{name}: only {filters} listing filter nodes")

    if problems:
        print("\nREFUSING to enable:")
        for p in problems:
            print("  - " + p)
        return 1

    print("\nAll pre-flight checks passed.")
    if not args.execute:
        print("Dry run only. Re-run with --execute to enable.")
        return 0

    op = client.get_type("CampaignOperation")
    op.update.resource_name = client.get_service(
        "CampaignService").campaign_path(cust, CAMPAIGN)
    op.update.status = client.enums.CampaignStatusEnum.ENABLED
    op.update_mask.paths.append("status")
    client.get_service("CampaignService").mutate_campaigns(
        customer_id=cust, operations=[op])

    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.name, campaign.status, campaign_budget.amount_micros
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""):
        print(f"\nVerified: {r.campaign.name} is now [{r.campaign.status.name}] "
              f"at ${r.campaign_budget.amount_micros/1e6:.2f}/day")
    print("\nStill paused, by design: LES - Display Remarketing, "
          "LES - Shopping - Retargeting Only (remarketing lists too small to serve).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
