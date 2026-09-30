"""Make BP - PMax - Outdoor Kitchens genuinely feed only.

Trevor, 30 September 2026: "this pmax is supposed to be feed only pmax, why
are there any other assets". He is right -- two of the 34 enabled asset groups
still carry creative:

    BP - Cal Flame   34 enabled assets
    BP - Mont Alpi   34 enabled assets

Ten headlines, two long headlines, four descriptions, eleven images and five
YouTube videos apiece. These are the two original asset groups, built before
the feed-only rebuild, and nothing ever stripped them. The other 32 groups
carry zero.

This matters more than it looks. The five asset automations are opted out, but
those settings only stop Google GENERATING creative -- they do nothing about
creative a human uploaded. With real headlines, images and video attached,
PMax can assemble Display and Video ads for these two groups, which is exactly
the Display-spend leak the feed-only pattern exists to avoid, and exactly what
happened at Culinary Profis.

The asset LINKS are set to PAUSED, not REMOVED. The underlying assets stay in
the account's asset library either way, so nothing is destroyed and relinking
is a one-click job, but PAUSED keeps the link itself visible and reversible.

Campaign-level assets are deliberately NOT touched: one LOGO, one BUSINESS_NAME
and eight SITELINKs. The logo and business name are required while
brand_guidelines_enabled is true, and sitelinks only extend Search-surface ads.
Those are a separate decision -- see the report at the end.

Run with no flags for a dry run. Pass --execute to apply.
"""
import argparse
import sys
from collections import Counter, defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
CAMPAIGN = 24209664922


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    # Only ENABLED asset groups. Paused and removed groups keep returning their
    # asset links, and pausing links on a group nobody serves is noise.
    live = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status, campaign.id
        FROM asset_group
        WHERE campaign.id = {CAMPAIGN} AND asset_group.status = 'ENABLED'"""):
        live[r.asset_group.id] = r.asset_group.name

    targets = defaultdict(list)
    kinds = defaultdict(Counter)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group_asset.resource_name, asset_group_asset.field_type,
               asset_group_asset.status, asset.type, asset.id, campaign.id
        FROM asset_group_asset
        WHERE campaign.id = {CAMPAIGN}
          AND asset_group_asset.status = 'ENABLED'"""):
        if r.asset_group.id not in live:
            continue
        targets[r.asset_group.name].append(
            r.asset_group_asset.resource_name)
        kinds[r.asset_group.name][r.asset_group_asset.field_type.name] += 1

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\ncampaign {CAMPAIGN}   {len(live)} enabled asset groups")
    clean = [n for n in live.values() if n not in targets]
    print(f"{len(clean)} already carry zero assets (feed only, as intended)")

    if not targets:
        print("\nNothing to do: every enabled asset group is already feed only.")
        return 0

    print(f"\n{len(targets)} asset group(s) still carrying creative:")
    total = 0
    for nm in sorted(targets):
        n = len(targets[nm])
        total += n
        print(f"\n  {nm}  --  {n} enabled assets to PAUSE")
        for ft, c in sorted(kinds[nm].items(), key=lambda kv: -kv[1]):
            print(f"      {ft:28} {c:>3}")
    print(f"\nTOTAL asset links to pause: {total}")
    print("The underlying assets stay in the account library and can be "
          "relinked at any time.")

    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
        return 0

    svc = client.get_service("AssetGroupAssetService")
    ops = []
    for nm in sorted(targets):
        for rn in targets[nm]:
            o = client.get_type("AssetGroupAssetOperation")
            o.update.resource_name = rn
            o.update.status = e.AssetLinkStatusEnum.PAUSED
            o.update_mask.paths.append("status")
            ops.append(o)
    svc.mutate_asset_group_assets(customer_id=cust, operations=ops)
    print(f"\n  paused {len(ops)} asset links")

    # ---- read-back --------------------------------------------------------
    still = Counter()
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group_asset.status, campaign.id
        FROM asset_group_asset
        WHERE campaign.id = {CAMPAIGN}
          AND asset_group_asset.status = 'ENABLED'"""):
        if r.asset_group.id in live:
            still[r.asset_group.name] += 1
    print("\n--- read-back: enabled assets per enabled asset group ---")
    for gid, nm in sorted(live.items(), key=lambda kv: kv[1]):
        flag = "   <-- STILL HAS ASSETS" if still[nm] else ""
        print(f"  {nm:38} {still[nm]:>3} enabled assets{flag}")
    print(f"\n{sum(still.values())} enabled assets left across "
          f"{len(live)} asset groups (target: 0)")

    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group.status, asset_group.primary_status,
               asset_group.primary_status_reasons, campaign.id
        FROM asset_group WHERE campaign.id = {CAMPAIGN}
          AND asset_group.status = 'ENABLED'"""):
        a = r.asset_group
        if a.primary_status.name not in ("ELIGIBLE", "PENDING"):
            print(f"  note: {a.name} is {a.primary_status.name} "
                  f"{[x.name for x in a.primary_status_reasons]}")

    print("\n--- campaign-level assets, NOT touched ---")
    camp = Counter()
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign_asset.field_type, campaign_asset.status, campaign.id
        FROM campaign_asset WHERE campaign.id = {CAMPAIGN}
          AND campaign_asset.status = 'ENABLED'"""):
        camp[r.campaign_asset.field_type.name] += 1
    for ft, c in sorted(camp.items()):
        print(f"  {ft:24} {c:>3}")
    print("  LOGO and BUSINESS_NAME are required while "
          "brand_guidelines_enabled is true; SITELINKs only extend "
          "Search-surface ads. Removing them is a separate decision.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
