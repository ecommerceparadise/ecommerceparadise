"""Bring the Culinary Profis PMax in line with the feed-only pattern.

The campaign is already structurally feed-only: eight asset groups, zero text,
image, logo or video assets, POOR ad strength, ELIGIBLE. What it is NOT is
feed-only in practice -- over the last 30 days it put 34,829 impressions and
$96.16 onto the Display network against 1,544 impressions and $22.98 on
Search, where Shopping ads actually serve. Fountains USA, on the same pattern,
ran 15,843 Search impressions against 16 on Display.

Only one configuration difference separates them. FUSA opts out of five asset
automations; Culinary Profis opts out of three. This adds the two missing:

    GENERATE_IMAGE_ENHANCEMENT
    GENERATE_ENHANCED_YOUTUBE_VIDEOS

With no assets of its own, those are the remaining routes by which PMax can
assemble display and video creative from the feed and landing pages.

Ruled out on the way: the account's four sitelinks are all PAUSED and served
nothing (0 campaign-asset impression rows), so inherited assets are not the
cause and no account-level change is needed.

NOT fixed here, and it probably matters more -- see the report. Add To Cart is
biddable alongside Purchase, and over 30 days the campaign recorded 5 add to
carts, 1 begin checkout and zero purchases. Maximize Conversions is steering
toward cheap engagement, which Display supplies. Changing biddable goals
affects bidding, so it needs Trevor's go-ahead.

Run with no flags for a dry run. Pass --execute to apply.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "Culinary Profis"
PMAX = 24222890101
REFERENCE = ("Fountains USA", 24209826676)

# Same two opt-outs apply to any feed-only PMax that is short of the
# reference set; pass --account/--campaign to target another one.


def automations(ga, cust, cid):
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.asset_automation_settings
        FROM campaign WHERE campaign.id = {cid} """):
        return {s.asset_automation_type.name: s.asset_automation_status.name
                for s in r.campaign.asset_automation_settings}
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--account", default=ACCOUNT)
    ap.add_argument("--campaign", type=int, default=PMAX)
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(args.account)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    have = automations(ga, cust, args.campaign)
    ref_cust = resolve_account(REFERENCE[0])["id"]
    want = automations(ga, ref_cust, REFERENCE[1])

    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print(f"  {args.account} [{args.campaign}]")
    for k, v in sorted(have.items()):
        print(f"     {k:44} {v}")
    print(f"\n  reference {REFERENCE[0]} [{REFERENCE[1]}]")
    for k, v in sorted(want.items()):
        print(f"     {k:44} {v}")

    missing = sorted(k for k, v in want.items()
                     if v == "OPTED_OUT" and have.get(k) != "OPTED_OUT")
    print(f"\n  to opt out: {missing or 'nothing -- already matching'}")
    if not missing:
        return 0
    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
        return 0

    op = client.get_type("CampaignOperation")
    c = op.update
    c.resource_name = client.get_service("CampaignService").campaign_path(
        cust, args.campaign)
    # AssetAutomationSetting is nested under Campaign, so get_type cannot
    # resolve it; proto-plus accepts a dict for a repeated message field.
    # The field is replaced wholesale, so the existing opt-outs are resent.
    for name, status in sorted(have.items()):
        c.asset_automation_settings.append({
            "asset_automation_type": e.AssetAutomationTypeEnum[name],
            "asset_automation_status": e.AssetAutomationStatusEnum[status]})
    for name in missing:
        c.asset_automation_settings.append({
            "asset_automation_type": e.AssetAutomationTypeEnum[name],
            "asset_automation_status": e.AssetAutomationStatusEnum.OPTED_OUT})
    op.update_mask.paths.append("asset_automation_settings")
    client.get_service("CampaignService").mutate_campaigns(
        customer_id=cust, operations=[op])

    after = automations(ga, cust, args.campaign)
    print("\n  after:")
    for k, v in sorted(after.items()):
        print(f"     {k:44} {v}")
    still = [k for k, v in want.items()
             if v == "OPTED_OUT" and after.get(k) != "OPTED_OUT"]
    print(f"  still not matching reference: {still or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
