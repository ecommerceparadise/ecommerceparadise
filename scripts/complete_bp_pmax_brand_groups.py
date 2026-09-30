"""Finish BP - PMax - Outdoor Kitchens: one asset group per brand, no gaps.

Trevor's instruction, 30 September 2026: "build this pmax feed only campaign
properly. one asset group per brand, no catchall, with the audience signals and
search themes."

Two jobs.

1. WIDEN Cal Flame and Mont Alpi to their whole brand.

   Correcting an earlier misreading of mine: these two are NOT product-type
   groups that bleed across brands. Their trees are

       ROOT SUBDIVISION
        |- SUBDIVISION brand='cal flame'
        |    |- UNIT_INCLUDED type='bbq island'   (and six more types)
        |    '- UNIT_EXCLUDED everything-else     <-- the problem
        '- UNIT_EXCLUDED everything-else          <-- every other brand, out

   The root already excludes other brands, so there is no cross-brand bleed and
   no overlap anywhere in this campaign (verified by walking every tree against
   every product). The only fault is the INNER everything-else being EXCLUDED:
   any product of that brand whose type is not one of the listed ones cannot
   serve. That costs 32 of Cal Flame's 59 products -- its outdoor fireplaces,
   fire pits and entertainment centres. Mont Alpi loses nothing today but would
   lose any new product type.

   Flipping that one node per group to UNIT_INCLUDED fixes both, and leaves the
   asset groups (and their learning history) in place.

2. BUILD a brand asset group for every remaining brand that has products, each
   with 15 search themes written from its own feed titles and the matching one
   of the three BP audiences. No catch-all.

Two things cannot be fixed here and need a Merchant Center edit instead:
  * 102 products have an EMPTY brand field, so no brand group can reach them.
  * 1 product has the brand 'dining table set' -- a description in the brand
    field, not a brand. Left alone rather than given a group named after a typo.
  * 'betterpatio unfinished outdoor kitchens' (1 product) is a stray spelling of
    'ufinish by betterpatio outdoor kitchens' (68), so both strings go into the
    one Ufinish group rather than a group of their own.

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

KITCHEN = 360956845   # BP - Outdoor Kitchen & Grill Buyers
PATIO = 360598793     # BP - Patio Furniture Buyers
FIRE = 360956848      # BP - Fire Feature Buyers
AUD_NAME = {KITCHEN: "Outdoor Kitchen & Grill", PATIO: "Patio Furniture",
            FIRE: "Fire Feature"}

# Widen these to the whole brand by flipping the inner everything-else node.
WIDEN = {"BP · Cal Flame": "cal flame", "BP · Mont Alpi": "mont alpi"}

# group name -> (brands it includes, audience id, 15 search themes)
NEW = {
    "BP · Ufinish by BetterPatio": (
        ["ufinish by betterpatio outdoor kitchens",
         "betterpatio unfinished outdoor kitchens"], KITCHEN, [
        "unfinished outdoor kitchen", "diy outdoor kitchen kit",
        "build your own outdoor kitchen", "unfinished bbq island",
        "diy bbq island kit", "outdoor kitchen frame kit",
        "linear outdoor kitchen", "outdoor kitchen island kit",
        "diy outdoor kitchen island", "stucco ready outdoor kitchen",
        "outdoor kitchen shell", "custom outdoor kitchen kit",
        "modular outdoor kitchen frame", "12 foot outdoor kitchen",
        "ufinish outdoor kitchen"]),
    "BP · BetterPatio Mountain Series": (
        ["betterpatio mountain series"], KITCHEN, [
        "betterpatio mountain series", "quick ship outdoor kitchen",
        "outdoor kitchen with blaze grill", "outdoor kitchen with griddle",
        "8 foot outdoor kitchen island", "luxury outdoor grill island",
        "pizza oven cart", "outdoor pizza oven cart",
        "prefabricated outdoor kitchen", "outdoor kitchen with fridge",
        "grill island with griddle", "stone outdoor kitchen island",
        "outdoor kitchen ready to ship", "custom outdoor kitchen bbq grill",
        "6 foot outdoor grill island"]),
    "BP · Modway": (["modway"], PATIO, [
        "modway outdoor furniture", "modway patio set",
        "aluminum patio furniture set", "powder coated aluminum patio set",
        "outdoor sofa sectional", "modern patio furniture",
        "outdoor daybed lounge", "4 piece patio set",
        "patio bar and dining set", "modway tahoe",
        "contemporary outdoor furniture", "aluminum outdoor sectional",
        "patio conversation set modern", "outdoor lounge furniture set",
        "modway sectional"]),
    "BP · BetterPatio.com": (["betterpatio.com"], KITCHEN, [
        "betterpatio outdoor kitchen", "outdoor kitchen island with grill",
        "outdoor kitchen with storage", "8 foot outdoor kitchen island",
        "6 foot outdoor kitchen island", "outdoor kitchen with griddle",
        "grill island with trash drawer",
        "outdoor kitchen island with access doors", "patio dining set",
        "outdoor deep seating set", "outdoor dining table and chairs",
        "custom bbq island", "outdoor kitchen island with fridge",
        "betterpatio grill island", "outdoor corner table"]),
    "BP · BetterPatio": (["betterpatio"], KITCHEN, [
        "betterpatio", "luxury outdoor grill island",
        "lynx outdoor kitchen island", "high end outdoor kitchen",
        "8 foot luxury grill island", "outdoor kitchen with blaze grill",
        "quick ship outdoor island", "premium bbq island",
        "outdoor kitchen with blaze griddle", "custom luxury outdoor kitchen",
        "outdoor island with trash drawer",
        "professional outdoor kitchen island", "designer outdoor kitchen",
        "outdoor kitchen with power burner", "betterpatio outdoor island"]),
    "BP · Empire Comfort Systems": (["empire comfort systems"], FIRE, [
        "empire comfort systems", "carol rose outdoor fireplace",
        "outdoor linear gas fireplace", "see thru gas fireplace",
        "60 inch outdoor fireplace", "outdoor gas fireplace insert",
        "linear outdoor fireplace", "empire outdoor fireplace",
        "variable flame gas fireplace",
        "outdoor fireplace with crushed glass", "vent free outdoor fireplace",
        "built in outdoor gas fireplace", "outdoor fireplace burner",
        "carol rose fireplace", "modern outdoor gas fireplace"]),
    "BP · Complete Outdoor Living": (["complete outdoor living"], KITCHEN, [
        "complete outdoor living", "complete outdoor kitchen",
        "maui bbq island", "92 inch bbq island",
        "outdoor kitchen with summerset grill", "bbq island with storage",
        "outdoor kitchen with power burner", "prefab bbq island",
        "all in one outdoor kitchen",
        "outdoor kitchen island with grill and fridge", "stucco bbq island",
        "l shaped bbq island", "outdoor kitchen package",
        "bbq island with side burner", "turnkey outdoor kitchen"]),
    "BP · Bull BBQ": (["bull bbq"], KITCHEN, [
        "bull bbq outdoor kitchen", "bull outdoor kitchen island",
        "bull core series", "bull premier q island",
        "4 burner outdoor kitchen island", "bull odk island",
        "outdoor kitchen island with refrigerator",
        "stainless outdoor kitchen island", "bull bbq island",
        "outdoor kitchen island with side burner",
        "premium outdoor kitchen island", "bull grill island",
        "complete bull outdoor kitchen", "outdoor kitchen island 4 burner",
        "bull outdoor kitchen package"]),
    "BP · Panama Jack": (["panama jack"], PATIO, [
        "panama jack", "panama jack key biscayne",
        "outdoor dining set 9 piece", "wicker dining set with cushions",
        "patio seating group", "outdoor bistro set",
        "square patio dining set", "rectangular patio dining set",
        "5 piece patio seating group", "hanging chair outdoor",
        "patio bar set wicker", "outdoor dining table set",
        "panama jack patio set", "7 piece patio dining set",
        "resin wicker dining set"]),
    "BP · BetterPatio Designer Series": (
        ["betterpatio designer series"], KITCHEN, [
        "betterpatio designer series", "modern linear outdoor grill island",
        "modular outdoor grill island", "92 inch outdoor grill island",
        "customizable bbq island", "6 foot grill island",
        "bbq grill cart for pizza oven", "modern outdoor kitchen island",
        "steel grill cart", "designer bbq island", "linear grill island",
        "5 foot outdoor grill island", "outdoor kitchen island modular",
        "custom grill island", "contemporary outdoor kitchen"]),
    "BP · Napoleon Fireplaces": (["napoleon fireplaces"], FIRE, [
        "napoleon fireplaces", "napoleon patioflame table",
        "st tropez patioflame", "patio flame table",
        "linear patioflame burner", "napoleon fire table",
        "outdoor fire table gas", "napoleon allure electric fireplace",
        "linear electric fireplace", "outdoor fire table square",
        "rectangle fire table", "48 inch linear burner kit",
        "napoleon electric fireplace", "outdoor gas fire table",
        "phantom electric fireplace"]),
    "BP · Hospitality Rattan": (["hospitality rattan"], PATIO, [
        "hospitality rattan", "hospitality rattan soho",
        "wicker sectional set", "outdoor party bar", "rattan loveseat",
        "6 piece sectional set outdoor", "wicker bar outdoor",
        "indoor outdoor wicker sectional", "4 piece sectional set",
        "rattan sofa sectional", "commercial wicker furniture",
        "soho sectional", "wicker loveseat set", "outdoor bar furniture",
        "rattan patio bar"]),
    "BP · Haven Outdoor": (["haven outdoor"], KITCHEN, [
        "haven outdoor", "haven outdoor kitchen island",
        "outdoor kitchen with coyote grill", "8 foot outdoor kitchen island",
        "outdoor kitchen with pellet grill", "bbq island with coyote",
        "coyote grill island", "outdoor kitchen island 36 inch grill",
        "premium bbq island", "prefab outdoor kitchen island",
        "outdoor kitchen with s series grill", "haven bbq island",
        "luxury outdoor kitchen island", "outdoor kitchen island stainless",
        "complete bbq island with grill"]),
    "BP · KidKraft": (["kidkraft"], PATIO, [
        "kidkraft", "kidkraft playset", "wooden swing set",
        "outdoor wooden playset", "kids backyard playset",
        "cedar swing set", "wooden playground set",
        "kidkraft charleston lodge", "kidkraft brooksville",
        "backyard play structure", "wooden climbing frame",
        "swing set with slide", "kids outdoor playhouse",
        "residential wooden playset", "garden playset for kids"]),
    "BP · Patio Sense": (["patio sense"], PATIO, [
        "patio sense", "aluminum patio dining set",
        "teak finish patio furniture", "patio dining set aluminum",
        "outdoor dining set 4 seat", "weather resistant patio set",
        "aluminum outdoor dining table", "patio sense dining set",
        "faux teak patio set", "outdoor dining furniture aluminum",
        "patio table and chairs set", "rust proof patio furniture",
        "aged teak finish furniture", "small patio dining set",
        "aluminium garden dining set"]),
}

# Brand strings that stay uncovered on purpose -- a feed fix, not an ads fix.
FEED_FIX_ONLY = {"", "dining table set"}
SEARCH_THEME_MAX, THEMES_PER_GROUP_MAX = 80, 25


def validate():
    bad = []
    for nm, (brands, aud, themes) in NEW.items():
        if aud not in AUD_NAME:
            bad.append(f"{nm}: unknown audience {aud}")
        if len(themes) > THEMES_PER_GROUP_MAX or len(themes) != len(set(themes)):
            bad.append(f"{nm}: {len(themes)} themes, {len(set(themes))} unique")
        for t in themes:
            if len(t) > SEARCH_THEME_MAX or t != t.strip() or not t:
                bad.append(f"{nm}: bad theme {t!r}")
    if bad:
        print("VALIDATION FAILED:")
        for b in bad:
            print("  " + b)
        sys.exit(1)


def load_trees(ga, cust):
    """{asset_group_name: {node_id: node}} for ENABLED asset groups."""
    trees = defaultdict(dict)
    ids = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group_listing_group_filter.id,
               asset_group_listing_group_filter.type,
               asset_group_listing_group_filter.parent_listing_group_filter,
               asset_group_listing_group_filter.case_value.product_brand.value,
               asset_group_listing_group_filter.case_value.product_type.value,
               campaign.id
        FROM asset_group_listing_group_filter WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group.status.name != "ENABLED":
            continue
        f = r.asset_group_listing_group_filter
        ids[r.asset_group.name] = r.asset_group.id
        pid = (int(f.parent_listing_group_filter.split("~")[-1])
               if f.parent_listing_group_filter else None)
        dim = ("brand" if f.case_value.product_brand.value else
               ("type" if f.case_value.product_type.value else None))
        trees[r.asset_group.name][f.id] = {
            "id": f.id, "parent": pid, "type": f.type_.name, "dim": dim,
            "val": (f.case_value.product_brand.value
                    or f.case_value.product_type.value or "").strip().lower()}
    return trees, ids


def reachable(tree, brand, ptype):
    """Walk the tree the way Google does: subdivision by subdivision."""
    kids, root = defaultdict(list), None
    for n in tree.values():
        if n["parent"] is None:
            root = n
        else:
            kids[n["parent"]].append(n)
    cur = root
    while cur is not None:
        if cur["type"] == "UNIT_INCLUDED":
            return True
        if cur["type"] == "UNIT_EXCLUDED":
            return False
        want = {"brand": brand, "type": ptype}
        nxt = fallback = None
        for ch in kids.get(cur["id"], []):
            if ch["dim"] is None:
                fallback = ch
            elif want.get(ch["dim"]) == ch["val"]:
                nxt = ch
        cur = nxt or fallback
    return False


def servable(ga, cust):
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


def coverage(trees, products):
    cov, orphan = 0, Counter()
    for b, ty in products:
        if any(reachable(t, b, ty) for t in trees.values()):
            cov += 1
        else:
            orphan[b] += 1
    return cov, orphan


def retry(fn, attempts=5):
    """Retry a mutate through CONCURRENT_MODIFICATION.

    Google returns that when two requests touch the same resource at once; it
    is transient and the documented response is to retry. Anything else is a
    real error and is re-raised immediately.
    """
    import time
    for i in range(attempts):
        try:
            return fn()
        except Exception as ex:
            if "CONCURRENT_MODIFICATION" not in str(ex) or i == attempts - 1:
                raise
            wait = 2 ** i
            print(f"    CONCURRENT_MODIFICATION, retrying in {wait}s")
            time.sleep(wait)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    validate()
    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    products = servable(ga, cust)
    by_brand = Counter(b for b, _ in products)
    trees, ag_ids = load_trees(ga, cust)
    before_cov, before_orphan = coverage(trees, products)

    print("=" * 76)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 76)
    print(f"\ncampaign {CAMPAIGN}   {len(products)} servable products")
    print(f"BEFORE: {before_cov} reachable, {sum(before_orphan.values())} not")

    # ---- 1. the nodes to flip ---------------------------------------------
    flips, already_wide = [], []
    for gname, brand in WIDEN.items():
        if gname not in trees:
            print(f"ABORT: {gname!r} is not an enabled asset group")
            return 1
        tree = trees[gname]
        # Already in the house shape? A plain brand UNIT_INCLUDED and no brand
        # SUBDIVISION means a previous run finished this one.
        if any(n["type"] == "UNIT_INCLUDED" and n["dim"] == "brand"
               and n["val"] == brand for n in tree.values()):
            already_wide.append(gname)
            continue
        sub = [n for n in tree.values()
               if n["type"] == "SUBDIVISION" and n["dim"] == "brand"
               and n["val"] == brand]
        if len(sub) != 1:
            print(f"ABORT: {gname!r} has {len(sub)} brand subdivisions for "
                  f"{brand!r} and no brand unit, expected one of them")
            return 1
        inner = [n for n in tree.values()
                 if n["parent"] == sub[0]["id"] and n["dim"] is None]
        if len(inner) != 1 or inner[0]["type"] != "UNIT_EXCLUDED":
            print(f"ABORT: {gname!r} inner everything-else is "
                  f"{[n['type'] for n in inner]}, expected one UNIT_EXCLUDED")
            return 1
        missed = sum(1 for b, ty in products
                     if b == brand and not reachable(tree, b, ty))
        flips.append((gname, brand, sub[0]["id"], inner[0]["id"], missed))

    print("\n1. WIDEN to the whole brand:")
    for gname in already_wide:
        print(f"   {gname:36} already a plain brand filter -- skipping")
    for gname, brand, sub_id, node_id, missed in flips:
        print(f"   {gname:36} brand={brand!r:18} recovers {missed:>3} products")

    # ---- 2. the groups to create ------------------------------------------
    # Resumable: a previous run may have created some of these, built some of
    # their trees, and not reached the signals. Work out what is actually
    # missing rather than refusing to run.
    all_groups, node_counts, sig_counts = {}, Counter(), defaultdict(lambda: [0, 0])
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status, campaign.id
        FROM asset_group WHERE campaign.id = {CAMPAIGN}
          AND asset_group.status = 'ENABLED'"""):
        all_groups[r.asset_group.name] = r.asset_group.id
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group_listing_group_filter.id, campaign.id
        FROM asset_group_listing_group_filter WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group.status.name == "ENABLED":
            node_counts[r.asset_group.name] += 1
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, campaign.id
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group_signal.search_theme.text:
            sig_counts[r.asset_group.name][0] += 1
        if r.asset_group_signal.audience.audience:
            sig_counts[r.asset_group.name][1] += 1

    to_create = [nm for nm in NEW if nm not in all_groups]
    to_tree = [nm for nm in NEW if nm in all_groups and not node_counts[nm]]
    to_sign = [nm for nm in NEW
               if sig_counts[nm][0] == 0 or sig_counts[nm][1] == 0]
    claimed = {b for brands, _, _ in NEW.values() for b in brands}
    missing = [b for b in claimed if by_brand[b] == 0]
    if missing:
        print(f"ABORT: no servable products for {missing} -- feed has moved, "
              "re-check before building")
        return 1

    print(f"\n2. BRAND ASSET GROUPS ({len(NEW)} planned): "
          f"{len(to_create)} to create, {len(to_tree)} need a listing tree, "
          f"{len(to_sign)} need signals")
    total = 0
    for nm, (brands, aud, themes) in sorted(NEW.items()):
        n = sum(by_brand[b] for b in brands)
        total += n
        state = []
        if nm in to_create:
            state.append("create")
        if nm in to_tree:
            state.append("tree")
        if nm in to_sign:
            state.append("signals")
        extra = f" (+{brands[1]!r})" if len(brands) > 1 else ""
        print(f"   {nm:36} {n:>4} products  {AUD_NAME[aud]:24} "
              f"{'+'.join(state) or 'done':16}{extra}")
    print(f"   {'':36} {total:>4} products in total")

    left = {b: n for b, n in before_orphan.items()
            if b not in claimed and b not in WIDEN.values()}
    print(f"\n3. STILL UNREACHABLE afterwards ({sum(left.values())} products) "
          "-- needs a Merchant Center fix, not an asset group:")
    for b, n in sorted(left.items(), key=lambda kv: -kv[1]):
        why = ("empty brand field" if b == "" else
               "a description in the brand field, not a brand"
               if b in FEED_FIX_ONLY else "no group planned")
        print(f"   {b or '(no brand)':32} {n:>4}  -- {why}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
        return 0

    svc = client.get_service("AssetGroupListingGroupFilterService")
    ag_svc = client.get_service("AssetGroupService")
    INC = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
    EXC = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
    SUB = e.ListingGroupFilterTypeEnum.SUBDIVISION
    SRC = e.ListingGroupFilterListingSourceEnum.SHOPPING

    # ---- widen: replace the brand subtree with a plain brand UNIT ----------
    # A batch is validated operation by operation, so removing the inner
    # everything-else while its SUBDIVISION still has children is rejected with
    # SUBDIVISION_MUST_HAVE_EVERYTHING_ELSE_CHILD. Removing the whole subtree in
    # one atomic mutate -- children first, the subdivision last -- and creating
    # a brand UNIT_INCLUDED under the root leaves the group in exactly the shape
    # the other 17 use. If the API still refuses, fall back to adding the
    # missing product types, which recovers the same products but is not
    # future-proof against a new product type appearing.
    def path(ag_id, node_id):
        return (f"customers/{cust}/assetGroupListingGroupFilters/"
                f"{ag_id}~{node_id}")

    for gname, brand, sub_id, node_id, missed in flips:
        ag_id = ag_ids[gname]
        tree = trees[gname]
        root = next(n for n in tree.values() if n["parent"] is None)
        subtree = [n for n in tree.values() if n["parent"] == sub_id]
        ops = []
        for n in subtree:                        # children first
            rm = client.get_type("AssetGroupListingGroupFilterOperation")
            rm.remove = path(ag_id, n["id"])
            ops.append(rm)
        rm = client.get_type("AssetGroupListingGroupFilterOperation")
        rm.remove = path(ag_id, sub_id)          # then the subdivision itself
        ops.append(rm)
        add = client.get_type("AssetGroupListingGroupFilterOperation")
        f = add.create
        f.asset_group = ag_svc.asset_group_path(cust, ag_id)
        f.parent_listing_group_filter = path(ag_id, root["id"])
        f.type_ = INC
        f.listing_source = SRC
        f.case_value.product_brand.value = brand
        ops.append(add)
        try:
            svc.mutate_asset_group_listing_group_filters(
                customer_id=cust, operations=ops)
            print(f"  widened {gname}: brand UNIT replaces {len(subtree)} "
                  f"type nodes  (+{missed} products)")
            continue
        except Exception as ex:
            print(f"  clean rebuild refused for {gname} "
                  f"({type(ex).__name__}); adding the missing types instead")

        have = {n["val"] for n in subtree if n["dim"] == "type"}
        want = {ty for b, ty in products if b == brand and ty and ty not in have}
        if not want:
            print(f"    nothing to add for {gname}")
            continue
        ops = []
        for ty in sorted(want):
            o = client.get_type("AssetGroupListingGroupFilterOperation")
            f = o.create
            f.asset_group = ag_svc.asset_group_path(cust, ag_id)
            f.parent_listing_group_filter = path(ag_id, sub_id)
            f.type_ = INC
            f.listing_source = SRC
            f.case_value.product_type.value = ty
            f.case_value.product_type.level = (
                e.ListingGroupFilterProductTypeLevelEnum.LEVEL1)
            ops.append(o)
        svc.mutate_asset_group_listing_group_filters(
            customer_id=cust, operations=ops)
        print(f"    added {len(ops)} product types to {gname}: {sorted(want)}")

    # ---- create asset groups ---------------------------------------------
    made = {nm: ag_svc.asset_group_path(cust, gid)
            for nm, gid in all_groups.items()}
    if to_create:
        ag_ops = []
        for nm in sorted(to_create):
            o = client.get_type("AssetGroupOperation")
            a = o.create
            a.name = nm
            a.campaign = client.get_service("CampaignService").campaign_path(
                cust, CAMPAIGN)
            a.final_urls.append(FINAL_URL)
            a.status = e.AssetGroupStatusEnum.ENABLED
            ag_ops.append(o)
        rns = [r.resource_name for r in ag_svc.mutate_asset_groups(
            customer_id=cust, operations=ag_ops).results]
        made.update(dict(zip(sorted(to_create), rns)))
        print(f"  created {len(rns)} asset groups (no assets -- feed only)")
        to_tree = sorted(set(to_tree) | set(to_create))

    # ---- one tree per group, root + children in ONE atomic mutate ---------
    for nm in sorted(to_tree):
        rn = made[nm]
        ag_id = rn.split("/")[-1]
        brands = NEW[nm][0]
        ops = []
        root = client.get_type("AssetGroupListingGroupFilterOperation")
        f = root.create
        f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                           f"{ag_id}~-1")
        f.asset_group = rn
        f.type_ = SUB
        f.listing_source = SRC
        ops.append(root)
        for i, b in enumerate(brands, start=2):
            o = client.get_type("AssetGroupListingGroupFilterOperation")
            f = o.create
            f.resource_name = (f"customers/{cust}/"
                               f"assetGroupListingGroupFilters/{ag_id}~{-i}")
            f.asset_group = rn
            f.parent_listing_group_filter = (
                f"customers/{cust}/assetGroupListingGroupFilters/{ag_id}~-1")
            f.type_ = INC
            f.listing_source = SRC
            f.case_value.product_brand.value = b
            ops.append(o)
        o = client.get_type("AssetGroupListingGroupFilterOperation")
        f = o.create
        f.resource_name = (f"customers/{cust}/assetGroupListingGroupFilters/"
                           f"{ag_id}~{-(len(brands) + 2)}")
        f.asset_group = rn
        f.parent_listing_group_filter = (
            f"customers/{cust}/assetGroupListingGroupFilters/{ag_id}~-1")
        f.type_ = EXC
        f.listing_source = SRC
        f._pb.case_value.product_brand.SetInParent()
        ops.append(o)
        retry(lambda ops=ops: svc.mutate_asset_group_listing_group_filters(
            customer_id=cust, operations=ops))
    if to_tree:
        print(f"  built {len(to_tree)} listing trees")

    # ---- signals ----------------------------------------------------------
    if to_sign:
        sig_ops = []
        for nm in sorted(to_sign):
            brands, aud, themes = NEW[nm]
            have_th, have_au = sig_counts[nm]
            if not have_au:
                o = client.get_type("AssetGroupSignalOperation")
                o.create.asset_group = made[nm]
                o.create.audience.audience = f"customers/{cust}/audiences/{aud}"
                sig_ops.append(o)
            if not have_th:
                for th in themes:
                    o = client.get_type("AssetGroupSignalOperation")
                    o.create.asset_group = made[nm]
                    o.create.search_theme.text = th
                    sig_ops.append(o)
        retry(lambda: client.get_service(
            "AssetGroupSignalService").mutate_asset_group_signals(
            customer_id=cust, operations=sig_ops))
        print(f"  created {len(sig_ops)} signals across {len(to_sign)} groups")

    # ---- read-back --------------------------------------------------------
    trees2, _ = load_trees(ga, cust)
    after_cov, after_orphan = coverage(trees2, products)
    sig = defaultdict(lambda: [0, 0])
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, campaign.id
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group_signal.search_theme.text:
            sig[r.asset_group.name][0] += 1
        if r.asset_group_signal.audience.audience:
            sig[r.asset_group.name][1] += 1
    print(f"\n--- read-back: {len(trees2)} enabled asset groups ---")
    per = Counter()
    for b, ty in products:
        for nm, t in trees2.items():
            if reachable(t, b, ty):
                per[nm] += 1
    for nm in sorted(trees2):
        th, au = sig[nm]
        bad = "  <-- MISSING SIGNALS" if not th or not au else ""
        print(f"  {nm:36} {per[nm]:>5} prods themes={th:>3} aud={au}{bad}")
    print(f"\nCOVERAGE {before_cov} -> {after_cov} of {len(products)} "
          f"({sum(after_orphan.values())} unreachable)")
    for b, n in after_orphan.most_common():
        print(f"    still unreachable: {b or '(no brand)':32} {n:>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
