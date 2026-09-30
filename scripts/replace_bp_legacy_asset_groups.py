"""Replace BP - Cal Flame and BP - Mont Alpi with genuinely asset-free groups.

Trevor, 30 September 2026: "cal flame and mont alpi still have assets."

He is right, and pausing the asset links was the wrong fix. A paused link is
still attached: the creative still shows on the asset group in the UI and the
group is still not feed only.

Removing the links does not work either. Google validates the FINAL state of an
asset group that has assets and refuses to let it reach zero, returning all five
minimum-asset errors at once:

    NOT_ENOUGH_HEADLINE_ASSET
    NOT_ENOUGH_LONG_HEADLINE_ASSET
    NOT_ENOUGH_DESCRIPTION_ASSET
    NOT_ENOUGH_MARKETING_IMAGE_ASSET
    NOT_ENOUGH_SQUARE_MARKETING_IMAGE_ASSET

A zero-asset asset group is only legal if it is CREATED that way -- which is how
the other 32 groups in this campaign were built. An existing group with creative
cannot be emptied, only replaced.

So: rename and pause the two legacy groups, and create clean replacements that
have never had an asset. The replacements carry over each group's existing 25
search themes and the same audience, and use a plain brand listing filter, the
same shape as the other 32.

What this costs, stated plainly: the two legacy groups lose their PMax learning
history. It is worth little here -- both read LIMITED until their creative was
paused yesterday, and Cal Flame's tree only reached 27 of its 59 products until
it was widened this morning. The legacy groups are paused, not deleted, so the
creative and the history remain in the account.

Run with no flags for a dry run. Pass --execute to apply.
"""
import argparse
import sys
from collections import Counter, defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
CAMPAIGN = 24209664922
FINAL_URL = "https://betterpatio.com"
ARCHIVE_PREFIX = "ZZ REPLACED (had creative) - "

# asset group id -> (current name, brand it should filter on)
LEGACY = {
    6744483942: ("BP · Cal Flame", "cal flame"),
    6744330872: ("BP · Mont Alpi", "mont alpi"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums
    ag_svc = client.get_service("AssetGroupService")

    # ---- read the legacy groups -------------------------------------------
    found = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group.final_urls, campaign.id
        FROM asset_group WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group.id in LEGACY:
            found[r.asset_group.id] = (r.asset_group.name,
                                       r.asset_group.status.name)
    for gid, (want_name, _) in LEGACY.items():
        if gid not in found:
            print(f"ABORT: asset group {gid} not in campaign {CAMPAIGN}")
            return 1
        if found[gid][0] != want_name:
            print(f"ABORT: {gid} is named {found[gid][0]!r}, expected "
                  f"{want_name!r} -- refusing to touch it")
            return 1

    # ---- carry over signals and asset counts ------------------------------
    themes, auds, assets = defaultdict(list), defaultdict(set), Counter()
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, campaign.id
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group.id in LEGACY:
            if r.asset_group_signal.search_theme.text:
                themes[r.asset_group.id].append(
                    r.asset_group_signal.search_theme.text)
            if r.asset_group_signal.audience.audience:
                auds[r.asset_group.id].add(
                    r.asset_group_signal.audience.audience)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group_asset.status, campaign.id
        FROM asset_group_asset WHERE campaign.id = {CAMPAIGN}
          AND asset_group_asset.status IN ('ENABLED', 'PAUSED')"""):
        if r.asset_group.id in LEGACY:
            assets[r.asset_group.id] += 1

    for gid in LEGACY:
        if len(auds[gid]) != 1:
            print(f"ABORT: {LEGACY[gid][0]!r} has {len(auds[gid])} audience "
                  "signals, expected exactly 1 to carry over")
            return 1
        if not themes[gid]:
            print(f"ABORT: {LEGACY[gid][0]!r} has no search themes to carry over")
            return 1

    existing_names = {r.asset_group.name for r in ga.search(
        customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group.status, campaign.id
        FROM asset_group WHERE campaign.id = {CAMPAIGN}
          AND asset_group.status = 'ENABLED'""")}

    print("=" * 76)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 76)
    print(f"\ncampaign {CAMPAIGN}\n")
    plan = []
    for gid, (name, brand) in LEGACY.items():
        aud = next(iter(auds[gid]))
        print(f"{name}  [{gid}]  status={found[gid][1]}")
        print(f"   {assets[gid]} asset links attached -- cannot be emptied, "
              "so this group is retired")
        print(f"   -> rename to {ARCHIVE_PREFIX + name!r} and PAUSE")
        print(f"   -> create a fresh {name!r}: 0 assets, "
              f"brand={brand!r}, {len(themes[gid])} themes carried over, "
              f"audience {aud.split('/')[-1]}")
        if name in existing_names and name != found[gid][0]:
            print(f"   ABORT: {name!r} already exists as another enabled group")
            return 1
        plan.append((gid, name, brand, sorted(themes[gid]), aud))
        print()

    if not args.execute:
        print("Dry run. Re-run with --execute to apply.")
        return 0

    # ---- 1. rename + pause the legacy groups ------------------------------
    ops = []
    for gid, name, *_ in plan:
        o = client.get_type("AssetGroupOperation")
        o.update.resource_name = ag_svc.asset_group_path(cust, gid)
        o.update.name = ARCHIVE_PREFIX + name
        o.update.status = e.AssetGroupStatusEnum.PAUSED
        o.update_mask.paths.extend(["name", "status"])
        ops.append(o)
    ag_svc.mutate_asset_groups(customer_id=cust, operations=ops)
    print(f"  retired {len(ops)} legacy asset group(s)")

    # ---- 2. create the replacements ---------------------------------------
    ops = []
    for gid, name, *_ in plan:
        o = client.get_type("AssetGroupOperation")
        a = o.create
        a.name = name
        a.campaign = client.get_service("CampaignService").campaign_path(
            cust, CAMPAIGN)
        a.final_urls.append(FINAL_URL)
        a.status = e.AssetGroupStatusEnum.ENABLED
        ops.append(o)
    new_rns = [r.resource_name for r in ag_svc.mutate_asset_groups(
        customer_id=cust, operations=ops).results]
    made = {p[1]: rn for p, rn in zip(plan, new_rns)}
    print(f"  created {len(new_rns)} replacement asset group(s), zero assets")

    # ---- 3. listing tree: root -> brand UNIT + everything-else EXCLUDED ----
    svc = client.get_service("AssetGroupListingGroupFilterService")
    SRC = e.ListingGroupFilterListingSourceEnum.SHOPPING
    for gid, name, brand, _, _ in plan:
        rn = made[name]
        ag_id = rn.split("/")[-1]
        tree_ops = []
        root = client.get_type("AssetGroupListingGroupFilterOperation")
        f = root.create
        f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                           f"{ag_id}~-1")
        f.asset_group = rn
        f.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
        f.listing_source = SRC
        tree_ops.append(root)
        inc = client.get_type("AssetGroupListingGroupFilterOperation")
        f = inc.create
        f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                           f"{ag_id}~-2")
        f.asset_group = rn
        f.parent_listing_group_filter = (
            f"customers/{cust}/assetGroupListingGroupFilters/{ag_id}~-1")
        f.type_ = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
        f.listing_source = SRC
        f.case_value.product_brand.value = brand
        tree_ops.append(inc)
        exc = client.get_type("AssetGroupListingGroupFilterOperation")
        f = exc.create
        f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                           f"{ag_id}~-3")
        f.asset_group = rn
        f.parent_listing_group_filter = (
            f"customers/{cust}/assetGroupListingGroupFilters/{ag_id}~-1")
        f.type_ = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
        f.listing_source = SRC
        f._pb.case_value.product_brand.SetInParent()
        tree_ops.append(exc)
        svc.mutate_asset_group_listing_group_filters(
            customer_id=cust, operations=tree_ops)
        print(f"  {name}: brand filter {brand!r} + everything-else excluded")

    # ---- 4. signals carried over ------------------------------------------
    sig_ops = []
    for gid, name, brand, ths, aud in plan:
        o = client.get_type("AssetGroupSignalOperation")
        o.create.asset_group = made[name]
        o.create.audience.audience = aud
        sig_ops.append(o)
        for th in ths:
            o = client.get_type("AssetGroupSignalOperation")
            o.create.asset_group = made[name]
            o.create.search_theme.text = th
            sig_ops.append(o)
    client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
        customer_id=cust, operations=sig_ops)
    print(f"  created {len(sig_ops)} signals on the replacements")

    # ---- read-back --------------------------------------------------------
    print("\n--- read-back: every ENABLED asset group in the campaign ---")
    live = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group.primary_status, campaign.id
        FROM asset_group WHERE campaign.id = {CAMPAIGN}
          AND asset_group.status = 'ENABLED'"""):
        live[r.asset_group.id] = [r.asset_group.name,
                                  r.asset_group.primary_status.name, 0, 0, 0]
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group_asset.status, campaign.id
        FROM asset_group_asset WHERE campaign.id = {CAMPAIGN}
          AND asset_group_asset.status IN ('ENABLED', 'PAUSED')"""):
        if r.asset_group.id in live:
            live[r.asset_group.id][2] += 1
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, campaign.id
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group.id in live:
            if r.asset_group_signal.search_theme.text:
                live[r.asset_group.id][3] += 1
            if r.asset_group_signal.audience.audience:
                live[r.asset_group.id][4] += 1
    total_assets = 0
    for gid, (nm, ps, na, th, au) in sorted(live.items(), key=lambda kv: kv[1][0]):
        total_assets += na
        flag = "   <-- HAS ASSETS" if na else ""
        print(f"  {nm:38} assets={na:>3} themes={th:>3} aud={au} [{ps}]{flag}")
    print(f"\n{len(live)} enabled asset groups, {total_assets} asset links "
          "attached in total (target: 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
