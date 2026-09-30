"""Enforce the three asset-group rules on every live PMax campaign.

Trevor's instruction, 30 September 2026: "we should only have asset groups for
specific brands that have products in the feed. we should not have an all other
brands asset group either. and they all need search themes and audience
signals" -- then "get rid of the catch all we need to hyper focus these asset
groups one per brand."

So, for each ENABLED Performance Max campaign in every managed account:

  1. An asset group whose listing filter matches NO servable product is PAUSED.
     Asset groups outlive the brands they filter on; a group for a brand that
     has left the catalogue reads ELIGIBLE and can never serve.
  2. A catch-all asset group -- one whose tree includes the "everything else"
     node rather than a named brand -- is PAUSED. This reverses the catch-all
     built into HS - PMax - HVAC (feed only) on 29 Sept.
  3. Every asset group left ENABLED must carry search themes AND an audience
     signal. This script does NOT invent themes (they are written per brand
     from the feed, by hand); it reports any group that is short so the gap is
     visible rather than silent.

PAUSED, never REMOVED. The house rule is pause, not delete, and a paused group
can be switched back on in one click. Note that both PAUSED and REMOVED asset
groups keep returning their listing filters from the API, so any coverage query
must still join on asset_group.status either way.

Dropping the catch-all has a cost worth stating: products whose brand has no
asset group of its own become unreachable. The script prints exactly how many.

Run with no flags for a dry run. Pass --execute to apply.
"""
import argparse
import sys
from collections import Counter, defaultdict

from google_ads.auth import get_client
from google_ads.accounts import load_managed_accounts, resolve_account

# A group named like this is treated as a catch-all even if its tree looks
# brand-shaped, so a rename can never smuggle one past the rule.
CATCHALL_NAME_HINTS = ("all other", "everything else", "other brands",
                       "catch all", "catch-all", "catchall")

# Brands the client has asked NOT to advertise. Their products are unreachable
# on purpose, so they are reported as withheld rather than as a coverage gap --
# otherwise every run flags them and someone eventually "fixes" it by building
# the group the client asked not to have.
#   HVAC Saver: the client asked to serve Goodman only, not Daikin
#   (Trevor, 30 September 2026). The HS - Daikin asset group is paused and
#   must stay paused; the 13 paused Daikin-named campaigns must not be enabled.
WITHHELD_BRANDS = {
    "4357556670": {"daikin"},
}

# The inverse, where the client named what they DO want rather than what they
# do not: any brand outside the set is withheld on purpose. An allowlist is
# used here rather than a list of the excluded brands so that a brand added to
# the feed later is withheld too, instead of surfacing as a new coverage gap.
#   Fountains USA: the client only wants the brands originally set up
#   (Trevor, 30 September 2026). That leaves 1,934 of 8,324 products
#   deliberately unadvertised -- do not build groups for them.
ADVERTISE_ONLY = {
    "8148956333": {"giannini garden", "metropolitan galleries inc.",
                   "the outdoor plus", "fiore stone"},
}


def servable_products(ga, cust):
    """Every product that could serve, as a list of (brand, product_type).

    Reachability has to be judged per PRODUCT, not per brand: this campaign
    mixes groups that filter on product_brand with groups that filter on
    product_type, so a brand with no group of its own may still be fully
    covered by a type-based group (BetterPatio's Cal Flame and Mont Alpi
    groups work that way). Counting by brand alone reports those as orphans.

    The account-wide "no campaigns advertising this product" error is a
    consequence of campaign state, not a fault in the product, so it is
    discounted. Any other error, or being out of stock, disqualifies it.
    """
    out = []
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.product_type_level1,
               shopping_product.availability, shopping_product.issues
        FROM shopping_product"""):
        p = r.shopping_product
        real = {i.error_code for i in p.issues} - {"not_eligible_in_any_campaign",
                                                  "low_manual_bids"}
        if real or p.availability.name != "IN_STOCK":
            continue
        out.append(((p.brand or "").strip().lower(),
                    (p.product_type_level1 or "").strip().lower()))
    return out


def read_campaign(ga, cust, cid):
    """Enabled asset groups in one campaign, with what each includes."""
    groups = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group.primary_status, campaign.id
        FROM asset_group
        WHERE campaign.id = {cid} AND asset_group.status = 'ENABLED'"""):
        groups[r.asset_group.id] = {
            "name": r.asset_group.name, "ps": r.asset_group.primary_status.name,
            "inc": set(), "catchall": False, "themes": 0, "aud": 0}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.status,
               asset_group_listing_group_filter.type,
               asset_group_listing_group_filter.case_value.product_brand.value,
               asset_group_listing_group_filter.case_value.product_type.value,
               campaign.id
        FROM asset_group_listing_group_filter WHERE campaign.id = {cid}"""):
        g = groups.get(r.asset_group.id)
        if not g or r.asset_group.status.name != "ENABLED":
            continue
        f = r.asset_group_listing_group_filter
        if f.type_.name != "UNIT_INCLUDED":
            continue
        b = f.case_value.product_brand.value.strip().lower()
        t = f.case_value.product_type.value.strip().lower()
        if b:
            g["inc"].add(("brand", b))
        elif t:
            g["inc"].add(("type", t))
        else:
            # UNIT_INCLUDED with no dimension value == "everything else".
            g["catchall"] = True
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, campaign.id
        FROM asset_group_signal WHERE campaign.id = {cid}"""):
        g = groups.get(r.asset_group.id)
        if not g:
            continue
        if r.asset_group_signal.search_theme.text:
            g["themes"] += 1
        if r.asset_group_signal.audience.audience:
            g["aud"] += 1
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--account", action="append",
                    help="limit to these accounts (default: all managed)")
    args = ap.parse_args()

    client = get_client()
    e = client.enums
    ga = client.get_service("GoogleAdsService")
    ag_svc = client.get_service("AssetGroupService")

    print("=" * 78)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 78)

    accounts = args.account or [a["id"] for a in load_managed_accounts()]
    tally = Counter()
    all_ops = []          # (cust, op, label)
    gaps = []             # groups left enabled but short on signals

    for key in accounts:
        acct = resolve_account(key)
        cust, name = acct["id"], acct["name"]
        camps = {}
        for r in ga.search(customer_id=cust, query="""
            SELECT campaign.id, campaign.name, campaign_budget.amount_micros
            FROM campaign
            WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
              AND campaign.status = 'ENABLED'"""):
            camps[r.campaign.id] = (r.campaign.name,
                                    r.campaign_budget.amount_micros / 1e6)
        if not camps:
            print(f"\n### {name}: no ENABLED PMax campaign")
            continue

        products = servable_products(ga, cust)
        by_brand, by_type = Counter(), Counter()
        for b, ty in products:
            by_brand[b] += 1
            by_type[ty] += 1
        print(f"\n### {name} [{cust}]   {len(products)} servable products")

        for cid, (cname, budget) in camps.items():
            groups = read_campaign(ga, cust, cid)
            keep, pause = [], []
            for gid, g in sorted(groups.items(), key=lambda kv: kv[1]["name"]):
                prods = sum(by_brand[v] if k == "brand" else by_type[v]
                            for k, v in g["inc"])
                named = any(h in g["name"].lower() for h in CATCHALL_NAME_HINTS)
                if g["catchall"] or named:
                    pause.append((gid, g, prods, "catch-all"))
                elif prods == 0:
                    pause.append((gid, g, prods, "no servable products"))
                else:
                    keep.append((gid, g, prods))

            print(f"\n  [{cid}] ${budget:.2f}/day  {cname!r}")
            print(f"      KEEP ({len(keep)}):")
            for gid, g, prods in keep:
                short = []
                if not g["themes"]:
                    short.append("NO THEMES")
                if not g["aud"]:
                    short.append("NO AUDIENCE")
                flag = "   <-- " + ", ".join(short) if short else ""
                if short:
                    gaps.append((name, cname, g["name"], g["themes"], g["aud"]))
                print(f"        {g['name'][:40]:40} {prods:>5} prods  "
                      f"themes={g['themes']:>3} aud={g['aud']}{flag}")
            if pause:
                print(f"      PAUSE ({len(pause)}):")
                for gid, g, prods, why in pause:
                    print(f"        {g['name'][:40]:40} {prods:>5} prods  "
                          f"[{g['ps']}]  -- {why}")
                    o = client.get_type("AssetGroupOperation")
                    o.update.resource_name = ag_svc.asset_group_path(cust, gid)
                    o.update.status = e.AssetGroupStatusEnum.PAUSED
                    o.update_mask.paths.append("status")
                    all_ops.append((cust, o, f"{name}: {g['name']}"))
                    tally[why] += 1

            # What becomes unreachable once the catch-all is gone. Judged per
            # product: a product is reachable if a kept group includes its
            # brand OR its product type.
            kept_brands = {v for _, g, _ in keep for k, v in g["inc"] if k == "brand"}
            kept_types = {v for _, g, _ in keep for k, v in g["inc"] if k == "type"}
            withheld_brands = WITHHELD_BRANDS.get(str(cust), set())
            allowed = ADVERTISE_ONLY.get(str(cust))
            orphan, withheld = Counter(), Counter()
            for b, ty in products:
                deliberate = (b in withheld_brands
                              or (allowed is not None and b not in allowed))
                if deliberate:
                    withheld[b] += 1
                elif b not in kept_brands and ty not in kept_types:
                    orphan[b] += 1
            if withheld:
                why = ("only the brands the client named are advertised"
                       if allowed is not None
                       else "the client asked not to advertise these")
                print(f"      WITHHELD on purpose ({sum(withheld.values())} "
                      f"products, {len(withheld)} brands) -- {why}, "
                      f"so this is not a gap:")
                for b, n in withheld.most_common(8):
                    print(f"        {b or '(no brand)':40} {n:>5}")
                if len(withheld) > 8:
                    print(f"        ... and {len(withheld) - 8} more brands")
            if orphan:
                n_prod = sum(orphan.values())
                print(f"      NOT REACHABLE by any kept group "
                      f"({n_prod} of {len(products)} products, "
                      f"{len(orphan)} brands) -- no catch-all to collect them:")
                for b, n in orphan.most_common(12):
                    print(f"        {b or '(no brand -- needs a feed fix)':40} {n:>5}")
                if len(orphan) > 12:
                    print(f"        ... and {len(orphan) - 12} more brands")

    print("\n" + "=" * 78)
    print(f"TO PAUSE: {sum(tally.values())}  " + ", ".join(
        f"{v} {k}" for k, v in tally.most_common()))
    if gaps:
        print(f"\nGROUPS STAYING ENABLED BUT SHORT ON SIGNALS ({len(gaps)}) -- "
              "themes are written per brand by hand, not generated here:")
        for acct_name, cname, gname, th, au in gaps:
            print(f"  {acct_name:22} {gname[:36]:36} themes={th:>3} aud={au}")
    else:
        print("\nEvery group left enabled has search themes and an audience. Good.")

    if not all_ops:
        print("\nNothing to pause.")
        return 0
    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
        return 0

    by_cust = defaultdict(list)
    for cust, op, label in all_ops:
        by_cust[cust].append(op)
    for cust, ops in by_cust.items():
        ag_svc.mutate_asset_groups(customer_id=cust, operations=ops)
        print(f"  {cust}: paused {len(ops)} asset group(s)")

    print("\n--- read-back: enabled asset groups per live PMax ---")
    for key in accounts:
        acct = resolve_account(key)
        cust, name = acct["id"], acct["name"]
        for r in ga.search(customer_id=cust, query="""
            SELECT campaign.id, campaign.name FROM campaign
            WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
              AND campaign.status = 'ENABLED'"""):
            groups = read_campaign(ga, cust, r.campaign.id)
            print(f"\n  {name} -- {r.campaign.name!r}: "
                  f"{len(groups)} enabled asset groups")
            for gid, g in sorted(groups.items(), key=lambda kv: kv[1]["name"]):
                bad = ""
                if g["catchall"]:
                    bad = "  <-- STILL A CATCH-ALL"
                elif not g["themes"] or not g["aud"]:
                    bad = "  <-- still short on signals"
                print(f"      {g['name'][:40]:40} themes={g['themes']:>3} "
                      f"aud={g['aud']} [{g['ps']}]{bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
