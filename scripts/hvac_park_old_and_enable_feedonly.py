"""Park the three superseded Goodman PMax campaigns and enable the new
feed-only PMax on HVAC Saver.

Trevor's instruction, 29 September 2026: "yes pause and park those old goodman
campaigns. enable the new ones." That is the explicit confirmation the standing
rule requires before enabling a campaign.

Parking = rename with a ZZ SUPERSEDED prefix and confirm PAUSED. The campaigns
are NOT deleted -- the standing rule is pause, never delete -- and their spend
history stays intact and attributable. All three are Goodman-only and none
covered Daikin's 102 products, which is why the new campaign replaces them:

  [24269081016] Feed Only | Goodman    $122.11 / 133 clicks / 0 conv (90d)
  [24083016123] Goodman Feed Only      $ 75.40 / 136 clicks / 1 conv (90d)
  [24186739380] Goodman                $132.37 / 252 clicks / 0 conv (90d)

Budgets are untouched, so nothing changes about what they could spend if
someone re-enabled them by hand.

Only ONE campaign is enabled: HS - PMax - HVAC (feed only). The 20+ paused
Shopping and Search campaigns in this account are deliberately left alone --
they were not part of the instruction.

Run with no flags for a dry run. Pass --execute to apply.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "Hvacsaver"
PARK_PREFIX = "ZZ SUPERSEDED - "
PARK = {
    24269081016: "Feed Only | Goodman",
    24083016123: "Goodman Feed Only",
    24186739380: "Goodman",
}
ENABLE = {24305209438: "HS - PMax - HVAC (feed only)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    live = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type, campaign.primary_status,
               campaign_budget.amount_micros
        FROM campaign WHERE campaign.status != 'REMOVED'"""):
        live[r.campaign.id] = (r.campaign.name, r.campaign.status.name,
                               r.campaign.advertising_channel_type.name,
                               r.campaign_budget.amount_micros / 1e6)

    # ---- guards: every id must exist and match the name we expect ----------
    problems = []
    for cid, expect in {**PARK, **ENABLE}.items():
        if cid not in live:
            problems.append(f"{cid} not found (or REMOVED)")
        elif live[cid][0] != expect:
            problems.append(f"{cid} is named {live[cid][0]!r}, expected {expect!r}")
    if problems:
        print("ABORT -- refusing to touch campaigns that are not what this "
              "script was written for:")
        for p in problems:
            print("  " + p)
        return 1

    # The campaign being enabled must be the feed-only one, with product trees
    # and signals in place. Enabling an empty PMax spends without serving well.
    for cid in ENABLE:
        nodes = sum(1 for _ in ga.search(customer_id=cust, query=f"""
            SELECT asset_group.id, campaign.id
            FROM asset_group_listing_group_filter WHERE campaign.id = {cid}"""))
        themes = auds = 0
        for r in ga.search(customer_id=cust, query=f"""
            SELECT asset_group_signal.search_theme.text,
                   asset_group_signal.audience.audience, campaign.id
            FROM asset_group_signal WHERE campaign.id = {cid}"""):
            themes += bool(r.asset_group_signal.search_theme.text)
            auds += bool(r.asset_group_signal.audience.audience)
        groups = [r.asset_group.name for r in ga.search(customer_id=cust, query=f"""
            SELECT asset_group.name, asset_group.status, campaign.id
            FROM asset_group
            WHERE campaign.id = {cid} AND asset_group.status = 'ENABLED'""")]
        off = [s.asset_automation_type.name for r in ga.search(
                   customer_id=cust, query=f"""
               SELECT campaign.asset_automation_settings, campaign.id
               FROM campaign WHERE campaign.id = {cid}""")
               for s in r.campaign.asset_automation_settings
               if s.asset_automation_status.name == "OPTED_OUT"]
        print(f"pre-flight for {live[cid][0]!r}:")
        print(f"  {len(groups)} enabled asset groups, {nodes} listing nodes, "
              f"{themes} search themes, {auds} audience signals, "
              f"{len(off)}/5 automations off")
        if not groups or not nodes or not auds or len(off) != 5:
            print("ABORT: campaign is not fully built. Not enabling.")
            return 1

    print(f"\n{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print("PARK (rename + confirm PAUSED, budgets and history untouched):")
    park_ops = []
    for cid, _ in PARK.items():
        name, status, ch, budget = live[cid]
        if name.startswith(PARK_PREFIX):
            print(f"  [{cid}] already parked: {name!r} -- skipping")
            continue
        new_name = f"{PARK_PREFIX}{name}"
        print(f"  [{cid}] {ch:15} {status:7} ${budget:>6.2f}/d")
        print(f"          {name!r}")
        print(f"       -> {new_name!r}"
              + ("" if status == "PAUSED" else "  + PAUSE"))
        o = client.get_type("CampaignOperation")
        o.update.resource_name = client.get_service(
            "CampaignService").campaign_path(cust, cid)
        o.update.name = new_name
        o.update_mask.paths.append("name")
        if status != "PAUSED":
            o.update.status = e.CampaignStatusEnum.PAUSED
            o.update_mask.paths.append("status")
        park_ops.append(o)

    print("\nENABLE:")
    enable_ops = []
    for cid, _ in ENABLE.items():
        name, status, ch, budget = live[cid]
        print(f"  [{cid}] {ch:15} {status:7} -> ENABLED   ${budget:.2f}/day")
        print(f"          {name!r}")
        if status == "ENABLED":
            print("          already enabled -- skipping")
            continue
        o = client.get_type("CampaignOperation")
        o.update.resource_name = client.get_service(
            "CampaignService").campaign_path(cust, cid)
        o.update.status = e.CampaignStatusEnum.ENABLED
        o.update_mask.paths.append("status")
        enable_ops.append(o)

    print(f"\nThis account currently has 0 enabled campaigns. After this it "
          f"has {len(ENABLE)}, spending up to "
          f"${sum(live[c][3] for c in ENABLE):.2f}/day.")

    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
        return 0

    svc = client.get_service("CampaignService")
    if park_ops:
        svc.mutate_campaigns(customer_id=cust, operations=park_ops)
        print(f"\n  parked {len(park_ops)} campaign(s)")
    if enable_ops:
        svc.mutate_campaigns(customer_id=cust, operations=enable_ops)
        print(f"  enabled {len(enable_ops)} campaign(s)")

    print("\n--- read-back: every non-removed campaign that is ENABLED ---")
    any_on = False
    for r in ga.search(customer_id=cust, query="""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type, campaign.primary_status,
               campaign.primary_status_reasons, campaign_budget.amount_micros
        FROM campaign WHERE campaign.status = 'ENABLED'"""):
        any_on = True
        c = r.campaign
        print(f"  [{c.id}] {c.advertising_channel_type.name:15} "
              f"${r.campaign_budget.amount_micros/1e6:.2f}/d {c.name!r}")
        print(f"        primary={c.primary_status.name} "
              f"{[x.name for x in c.primary_status_reasons]}")
    if not any_on:
        print("  none")

    print("\n--- read-back: the parked three ---")
    for cid in PARK:
        for r in ga.search(customer_id=cust, query=f"""
            SELECT campaign.id, campaign.name, campaign.status
            FROM campaign WHERE campaign.id = {cid}"""):
            print(f"  [{r.campaign.id}] {r.campaign.status.name:7} {r.campaign.name!r}")

    print("\n--- read-back: asset groups on the enabled campaign ---")
    for cid in ENABLE:
        for r in ga.search(customer_id=cust, query=f"""
            SELECT asset_group.name, asset_group.status,
                   asset_group.primary_status, asset_group.primary_status_reasons,
                   campaign.id
            FROM asset_group WHERE campaign.id = {cid}"""):
            a = r.asset_group
            print(f"  {a.name:26} {a.status.name:8} {a.primary_status.name:12} "
                  f"{[x.name for x in a.primary_status_reasons]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
