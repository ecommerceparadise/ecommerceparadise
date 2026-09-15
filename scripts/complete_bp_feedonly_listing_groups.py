"""Build the product trees for the BetterPatio feed-only PMax asset groups.

Split out from build_bp_feedonly_pmax.py because listing group filters cannot
be created the way that script first tried. Two rules the API enforces:

1. A SUBDIVISION and its children must be created in ONE mutate, using
   temporary resource names (negative ids) for the parent reference. A bare
   subdivision is rejected -- "SUBDIVISION node must have everything else
   child" -- and since the request is atomic, one bad operation rolls the
   whole batch back.
2. The "everything else" sibling must still declare which dimension it
   belongs to. Touching an empty proto3 message does not set the oneof, so
   the field has to be marked present explicitly (SetInParent) with no value.

Each brand asset group gets: root SUBDIVISION -> UNIT_INCLUDED brand=X,
UNIT_EXCLUDED everything-else. The catch-all group gets: root SUBDIVISION ->
UNIT_EXCLUDED for every brand handled elsewhere (its own groups plus the nine
the kitchens campaign serves) -> UNIT_INCLUDED everything-else, so brands
added to the feed later are picked up with no rebuild.

Idempotent: asset groups that already have listing nodes are skipped.
Run with no flags for a dry run. Pass --execute to build.
"""
import argparse
import sys
from collections import Counter, defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
CAMPAIGN_NAME = "BP · PMax — All Brands (feed only)"
OWN_GROUP_MIN = 20
CATCHALL = "BP · All Other Brands"
KITCHENS_BRANDS = {
    "mont alpi", "cal flame", "betterpatio", "betterpatio designer series",
    "betterpatio mountain series", "betterpatio solace series",
    "betterpatio unfinished outdoor kitchens", "betterpatio.com",
    "ufinish by betterpatio outdoor kitchens",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    camp = [r.campaign.id for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id FROM campaign WHERE campaign.name = '{CAMPAIGN_NAME}'
          AND campaign.status != 'REMOVED' """)]
    if len(camp) != 1:
        print(f"ABORT: expected exactly one {CAMPAIGN_NAME!r}, found {len(camp)}")
        return 1
    camp_id = camp[0]

    ok = Counter()
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.issues
        FROM shopping_product """):
        p = r.shopping_product
        if not ({i.error_code for i in p.issues} - {"not_eligible_in_any_campaign"}):
            ok[p.brand.strip().lower()] += 1
    own = [b for b, n in ok.most_common()
           if b and b not in KITCHENS_BRANDS and n >= OWN_GROUP_MIN]
    want = {f"BP · {b.title()}": b for b in own}

    groups = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.resource_name
        FROM asset_group WHERE campaign.id = {camp_id}
          AND asset_group.status != 'REMOVED' """):
        groups[r.asset_group.name] = (r.asset_group.id, r.asset_group.resource_name)

    missing = set(want) | {CATCHALL} - set(groups)
    if missing - set(groups):
        print(f"ABORT: asset groups not found: {sorted(missing - set(groups))}")
        return 1

    existing = defaultdict(int)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name FROM asset_group_listing_group_filter
        WHERE campaign.id = {camp_id} """):
        existing[r.asset_group.name] += 1

    svc = client.get_service("AssetGroupListingGroupFilterService")
    INC = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
    EXC = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
    SUB = e.ListingGroupFilterTypeEnum.SUBDIVISION

    def build(ag_id, ag_rn, children):
        """children: list of (type, brand|None). Returns the operation list."""
        ops = []

        def node(temp, parent, kind, brand):
            o = client.get_type("AssetGroupListingGroupFilterOperation")
            f = o.create
            f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                               f"{ag_id}~{temp}")
            f.asset_group = ag_rn
            if parent is not None:
                f.parent_listing_group_filter = (
                    f"customers/{cust}/assetGroupListingGroupFilters/"
                    f"{ag_id}~{parent}")
            f.type_ = kind
            f.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            if brand is not None:
                f.case_value.product_brand.value = brand
            else:
                f._pb.case_value.product_brand.SetInParent()
            ops.append(o)

        o = client.get_type("AssetGroupListingGroupFilterOperation")
        f = o.create
        f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                           f"{ag_id}~-1")
        f.asset_group = ag_rn
        f.type_ = SUB
        f.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        ops.append(o)
        for i, (kind, brand) in enumerate(children, start=2):
            node(-i, -1, kind, brand)
        return ops

    plan = []
    for name, brand in sorted(want.items()):
        if existing.get(name):
            continue
        plan.append((name, [(INC, brand), (EXC, None)]))
    if not existing.get(CATCHALL):
        kids = [(EXC, b) for b in sorted(set(own) | KITCHENS_BRANDS)]
        kids.append((INC, None))
        plan.append((CATCHALL, kids))

    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print(f"campaign {camp_id}; {len(groups)} asset groups, "
          f"{len(existing)} already have trees")
    for name, kids in plan:
        inc = [b for k, b in kids if k == INC]
        exc = [b for k, b in kids if k == EXC]
        print(f"  {name:40} include={inc[:2]}  exclude={len(exc)} node(s)")
    print(f"\n{len(plan)} asset groups to build")

    if not args.execute:
        print("\nDry run. Re-run with --execute to build.")
        return 0

    built = 0
    for name, kids in plan:
        ag_id, ag_rn = groups[name]
        ops = build(ag_id, ag_rn, kids)
        svc.mutate_asset_group_listing_group_filters(
            customer_id=cust, operations=ops)
        built += len(ops)
        print(f"  {name}: {len(ops)} nodes")
    print(f"\n{built} listing nodes created")
    return 0


if __name__ == "__main__":
    sys.exit(main())
