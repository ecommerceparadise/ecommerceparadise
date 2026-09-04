"""Enable the Fountains USA retargeting Shopping campaign.

Trevor said "enable" in conversation on 2026-09-03, after confirming the
$5/day budget and the audience set.

Before flipping the status the script re-checks the things that would make
this campaign spend badly if they were wrong: the audience restriction must be
TARGETING (bid_only=False) or it serves to cold traffic, the budget must be
$5/day and unshared, and the negative keyword lists must be attached. It
aborts rather than enabling a misconfigured campaign.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24214263728
EXPECTED_BUDGET_MICROS = 5_000_000
EXPECTED_CPC_MICROS = 2_000_000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Fountains USA")["id"]
    ga = client.get_service("GoogleAdsService")

    problems = []

    rows = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.name, campaign.status, campaign.bidding_strategy_type,
               campaign.shopping_setting.merchant_id,
               campaign.geo_target_type_setting.positive_geo_target_type,
               campaign_budget.amount_micros, campaign_budget.explicitly_shared
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""))
    if len(rows) != 1:
        print(f"Expected 1 campaign, got {len(rows)}. Aborting.")
        return 1
    c, b = rows[0].campaign, rows[0].campaign_budget
    print(f"Campaign: {c.name}  [{c.status.name}]")
    print(f"  bidding   {c.bidding_strategy_type.name}")
    print(f"  merchant  {c.shopping_setting.merchant_id}")
    print(f"  geo type  {c.geo_target_type_setting.positive_geo_target_type.name}")
    print(f"  budget    ${b.amount_micros/1e6:.2f}/day shared={b.explicitly_shared}")

    if b.amount_micros != EXPECTED_BUDGET_MICROS:
        problems.append(f"budget is ${b.amount_micros/1e6:.2f}, expected $5.00")
    if b.explicitly_shared:
        problems.append("budget is shared with other campaigns")
    if c.geo_target_type_setting.positive_geo_target_type.name != "PRESENCE":
        problems.append("location targeting is not PRESENCE")

    # The one setting that separates "retargeting only" from "everyone".
    targeting_ok = False
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.id, ad_group.name, ad_group.status, ad_group.cpc_bid_micros,
               ad_group.targeting_setting.target_restrictions
        FROM ad_group WHERE campaign.id = {CAMPAIGN}
          AND ad_group.status != 'REMOVED'"""):
        a = r.ad_group
        print(f"  ad group  {a.name} [{a.status.name}] max CPC ${a.cpc_bid_micros/1e6:.2f}")
        if a.cpc_bid_micros != EXPECTED_CPC_MICROS:
            problems.append(f"ad group CPC is ${a.cpc_bid_micros/1e6:.2f}, expected $2.00")
        for t in a.targeting_setting.target_restrictions:
            if t.targeting_dimension.name == "AUDIENCE":
                targeting_ok = not t.bid_only
                print(f"  AUDIENCE restriction bid_only={t.bid_only} "
                      f"-> {'TARGETING (retargeting only)' if targeting_ok else 'OBSERVATION (would serve to everyone)'}")
    if not targeting_ok:
        problems.append("AUDIENCE restriction is not set to TARGETING; the campaign "
                        "would serve to cold traffic")

    auds = [r.ad_group_criterion.display_name for r in ga.search(
        customer_id=cust, query=f"""
        SELECT ad_group_criterion.display_name FROM ad_group_criterion
        WHERE campaign.id = {CAMPAIGN} AND ad_group_criterion.type = 'USER_LIST'
          AND ad_group_criterion.status = 'ENABLED'""")]
    print(f"  audiences {len(auds)}")
    for a in auds:
        print(f"      {a}")
    if not auds:
        problems.append("no audiences attached")

    negs = [r.shared_set.name for r in ga.search(customer_id=cust, query=f"""
        SELECT shared_set.name FROM campaign_shared_set
        WHERE campaign.id = {CAMPAIGN} AND campaign_shared_set.status != 'REMOVED'""")]
    print(f"  negatives {negs}")
    if not negs:
        problems.append("no negative keyword lists applied")

    ads = list(ga.search(customer_id=cust, query=f"""
        SELECT ad_group_ad.ad.id, ad_group_ad.status FROM ad_group_ad
        WHERE campaign.id = {CAMPAIGN} AND ad_group_ad.status = 'ENABLED'"""))
    print(f"  ads       {len(ads)} enabled")
    if not ads:
        problems.append("no enabled ad")

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
