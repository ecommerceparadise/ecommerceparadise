"""Opt every campaign out of Google's automatically-created assets.

Standing instruction from Trevor: these automations stay off in all campaigns,
always. Run this after building anything new, or on a schedule, to catch
campaigns Google created or re-opted-in.

What gets turned off, by channel -- only the types that channel accepts:

  PERFORMANCE_MAX   FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION
                    TEXT_ASSET_AUTOMATION
                    GENERATE_IMAGE_EXTRACTION
                    GENERATE_IMAGE_ENHANCEMENT
                    GENERATE_ENHANCED_YOUTUBE_VIDEOS

  SEARCH            FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION
                    TEXT_ASSET_AUTOMATION

Display, Shopping, Demand Gen and Local Services do not expose the field at
all and are skipped.

Why it matters: with these on, PMax builds display and video creative from the
feed and landing pages even when an asset group carries no assets, and Search
campaigns get headlines nobody wrote. Culinary Profis was putting 34,829
impressions and $96 onto Display against 1,544 impressions on Search with
three of the five opted out; Fountains USA, with all five off, ran 15,843
Search impressions against 16 on Display.

The settings field is replaced wholesale on update, so the full target set is
written every time. Campaigns already matching are skipped. If a campaign
rejects a type its channel does not support, it retries with only the types
already present plus TEXT_ASSET_AUTOMATION, and reports what it managed.

Read-only by default. Pass --execute to apply.
"""
import argparse
import sys
from collections import Counter

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNTS = ["BetterPatio.com", "Laser Engraver Store", "eCommerce Paradise",
            "Culinary Profis", "Fountains USA"]

BY_CHANNEL = {
    "PERFORMANCE_MAX": [
        "FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION", "TEXT_ASSET_AUTOMATION",
        "GENERATE_IMAGE_EXTRACTION", "GENERATE_IMAGE_ENHANCEMENT",
        "GENERATE_ENHANCED_YOUTUBE_VIDEOS"],
    "SEARCH": [
        "FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION", "TEXT_ASSET_AUTOMATION"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--account", action="append",
                    help="limit to one account (repeatable)")
    args = ap.parse_args()

    client = get_client()
    ga = client.get_service("GoogleAdsService")
    svc = client.get_service("CampaignService")
    e = client.enums
    OUT = e.AssetAutomationStatusEnum.OPTED_OUT

    tally = Counter()
    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    for acct in (args.account or ACCOUNTS):
        cust = resolve_account(acct)["id"]
        plan = []
        for r in ga.search(customer_id=cust, query="""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.advertising_channel_type,
                   campaign.asset_automation_settings
            FROM campaign WHERE campaign.status != 'REMOVED' """):
            c = r.campaign
            want = BY_CHANNEL.get(c.advertising_channel_type.name)
            if not want:
                tally["skipped (channel has no such setting)"] += 1
                continue
            have = {s.asset_automation_type.name: s.asset_automation_status.name
                    for s in c.asset_automation_settings}
            if all(have.get(w) == "OPTED_OUT" for w in want):
                tally["already off"] += 1
                continue
            plan.append((c.id, c.name, c.status.name,
                         c.advertising_channel_type.name, have, want))

        print(f"### {acct}: {len(plan)} campaign(s) to change")
        for cid, nm, st, ch, have, want in plan:
            on = [w for w in want if have.get(w) != "OPTED_OUT"]
            print(f"   [{cid}] {st:7} {ch:16} {nm[:38]:40} -> off: {len(on)}")
            if not args.execute:
                continue
            try:
                op = client.get_type("CampaignOperation")
                op.update.resource_name = svc.campaign_path(cust, cid)
                for t in want:
                    op.update.asset_automation_settings.append({
                        "asset_automation_type": e.AssetAutomationTypeEnum[t],
                        "asset_automation_status": OUT})
                op.update_mask.paths.append("asset_automation_settings")
                svc.mutate_campaigns(customer_id=cust, operations=[op])
                tally["turned off"] += 1
            except Exception as ex:
                fallback = sorted(set(have) | {"TEXT_ASSET_AUTOMATION"})
                try:
                    op = client.get_type("CampaignOperation")
                    op.update.resource_name = svc.campaign_path(cust, cid)
                    for t in fallback:
                        op.update.asset_automation_settings.append({
                            "asset_automation_type": e.AssetAutomationTypeEnum[t],
                            "asset_automation_status": OUT})
                    op.update_mask.paths.append("asset_automation_settings")
                    svc.mutate_campaigns(customer_id=cust, operations=[op])
                    print(f"        full set rejected; applied {fallback}")
                    tally["turned off (reduced set)"] += 1
                except Exception as ex2:
                    print(f"        FAILED: {str(ex2)[:110]}")
                    tally["failed"] += 1
        print()

    print("=== summary ===")
    for k, v in tally.most_common():
        print(f"   {v:4}  {k}")
    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
