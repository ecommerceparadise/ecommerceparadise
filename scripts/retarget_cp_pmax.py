"""Narrow the Culinary Profis PMax to the categories the store actually sells.

The eligible Merchant Center feed (272 of 2,019 products -- the rest are out of
stock) contains exactly these machines: spiral / planetary / stand / dough
mixers and attachments, meat and deli slicers, meat grinders, dough sheeters,
dividers, rounders and moulders, food processors, sausage stuffers, meat
mixers, band saws, a vacuum tumbler and a tenderizer.

It contains no grills, ovens, proofers, refrigeration, ice machines or wine
coolers. Several search themes were buying exactly that traffic.

Worst case is CP - Primo. Every one of its 12 themes targets Primo Ceramic
Grills -- kamado, charcoal, oval, XL. The Primo in this feed is Primo food
equipment: two PS-12 slicers, two PSM spiral mixers and a PM-10 planetary
mixer. The asset group was bidding on grill searches and showing slicers.

Removals are off-catalogue themes or category-level terms too broad to be
useful; additions are grounded in real product titles. Signals only -- no
budget, bid strategy or status change. Run with no flags for a dry run.
"""
import argparse
import sys
from collections import defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "Culinary Profis"
PMAX = 24222890101
MAX_SIGNALS = 25

# (themes to remove, themes to add) per asset group.
PLAN = {
    "CP - Primo": (
        # Primo Ceramic Grills is a different company. None of this is in the feed.
        ["built in kamado grill", "ceramic charcoal grill", "ceramic kamado grill",
         "charcoal kamado smoker", "kamado style grill", "outdoor ceramic smoker",
         "premium charcoal grill", "primo ceramic grill", "primo grill",
         "primo kamado grill", "primo oval grill", "primo xl"],
        ["primo slicer", "primo spiral mixer", "primo planetary mixer",
         "primo ps-12 slicer", "primo psm-60e", "primo psm-80e", "primo pm-10",
         "primo deluxe ps-12d", "primo food equipment", "primo meat slicer"],
    ),
    "CP - Axis": (
        # Axis mixers are 12/20/30/60 qt -- there is no 40 qt. The slicers are
        # gravity-feed and gear-driven, not countertop.
        ["40 qt planetary mixer", "bakery planetary mixer",
         "countertop meat slicer", "axis equipment"],
        ["60 qt planetary mixer", "30 qt planetary mixer", "12 qt planetary mixer",
         "axis meat grinder", "axis dough sheeter", "gravity feed meat slicer",
         "pizza dough planetary mixer", "axis gear slicer"],
    ),
    "CP - BakeMax": (
        # No ovens and no proofers in the feed; the other two are category-level.
        ["bakemax oven", "bakery proofer", "commercial bakery equipment",
         "commercial bread equipment"],
        ["bakemax planetary mixer", "bakemax dough sheeter", "bakemax meat grinder",
         "80 qt planetary mixer", "60 qt floor planetary mixer",
         "countertop dough sheeter"],
    ),
    "CP - Omcan": (
        ["restaurant food equipment", "omcan food equipment"],
        ["omcan trento meat slicer", "trento spiral dough mixer",
         "omcan dough divider", "omcan dough sheeter", "omcan dough rounder",
         "omcan planetary mixer"],
    ),
    "CP - Pro-Cut": (
        ["meat processing equipment", "butcher shop equipment"],
        ["pro-cut deli slicer", "pro-cut meat saw", "32 meat grinder",
         "pro-cut vacuum tumbler", "commercial meat tenderizer",
         "stainless steel band saw"],
    ),
    "CP - Sirman": (
        ["panini grill commercial"],
        ["sirman sausage stuffer", "sirman food processor",
         "commercial sausage stuffer", "commercial meat mixer"],
    ),
    "CP - Ankarsrum": (
        # Comparison / generic-consumer intent rather than product intent.
        ["best stand mixer for baking", "dough mixer for home baking"],
        ["ankarsrum grain flaker", "ankarsrum beater set",
         "ankarsrum stainless steel bowl", "ankarsrum blender attachment"],
    ),
    # CP - Sunmix is left alone: 38 spiral mixers, 3 rounders and 3 dividers
    # back every theme it already carries.
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")

    groups = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name FROM asset_group
        WHERE campaign.id = {PMAX} AND asset_group.status = 'ENABLED' """):
        groups[r.asset_group.name] = r.asset_group.id

    unknown = set(PLAN) - set(groups)
    if unknown:
        print(f"ABORT: no enabled asset group named {unknown}")
        return 1

    # current themes -> resource name, per group
    have = defaultdict(dict)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name,
               asset_group_signal.resource_name,
               asset_group_signal.search_theme.text
        FROM asset_group_signal WHERE campaign.id = {PMAX} """):
        s = r.asset_group_signal
        if r.asset_group.id in groups.values() and s.search_theme.text:
            have[r.asset_group.name][s.search_theme.text] = s.resource_name

    svc_ag = client.get_service("AssetGroupService")
    rm_ops, add_ops, report = [], [], []
    for name, (drop, add) in PLAN.items():
        cur = have.get(name, {})
        missing = [d for d in drop if d not in cur]
        if missing:
            print(f"ABORT: {name} has no theme(s) {missing}; "
                  "the account changed since this plan was written.")
            return 1
        for d in drop:
            op = client.get_type("AssetGroupSignalOperation")
            op.remove = cur[d]
            rm_ops.append(op)

        after = len(cur) - len(drop)
        room = MAX_SIGNALS - after - 1          # 1 audience signal per group
        real_add = [a for a in add if a not in cur][:max(room, 0)]
        for a in real_add:
            op = client.get_type("AssetGroupSignalOperation")
            op.create.asset_group = svc_ag.asset_group_path(cust, groups[name])
            op.create.search_theme.text = a
            add_ops.append(op)
        report.append((name, len(cur), drop, real_add, after + len(real_add)))

    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    for name, before, drop, add, after in report:
        print(f"{name}: {before} themes -> {after}")
        for d in drop:
            print(f"    - {d}")
        for a in add:
            print(f"    + {a}")
        print()
    print(f"total: {len(rm_ops)} removals, {len(add_ops)} additions")

    if not args.execute:
        print("\nDry run. Re-run with --execute to push.")
        return 0

    svc = client.get_service("AssetGroupSignalService")
    if rm_ops:
        svc.mutate_asset_group_signals(customer_id=cust, operations=rm_ops)
        print(f"  removed {len(rm_ops)} themes")
    if add_ops:
        svc.mutate_asset_group_signals(customer_id=cust, operations=add_ops)
        print(f"  added {len(add_ops)} themes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
