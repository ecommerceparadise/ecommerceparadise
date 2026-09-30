"""Audience signals and search themes for the live BetterPatio PMax asset groups.

`BP - PMax - Outdoor Kitchens` [24209664922] runs at $180/day -- the largest
budget in the portfolio -- with 26 enabled asset groups. Before this script,
24 of them had a brand listing filter and NOTHING else: no search themes, no
audience. Only Cal Flame and Mont Alpi carried themes (25 each), and not one
group in the campaign carried an audience signal. That is the failure mode
CLAUDE.md warns about: the groups serve from the feed, but PMax has no query
intent to work from and no seed for who to show them to.

Unlike LES and HVAC Saver, ONE shared audience would be wrong here. This store
sells grills, sofas and fire pits. Blending "Garden & Outdoor Furniture" into
the Blaze grill group tells Google a sofa shopper is a grill prospect. So three
audiences are built, one per product family, and each group gets the one that
matches what its listing filter actually includes.

Groups whose brand has NO servable products in the feed are skipped, not
signalled. Writing themes for them would spend budget chasing queries the
store cannot fulfil. As of 2026-09-30 that is seven groups (American Outdoor
Grill, Chicago Brick Oven, Douglas Nance, Fire Magic, Hospitality Rattan Home,
Mayne, Skyline Design) -- brands that have left the catalogue since the groups
were built on 15 September. They are reported, not touched; pausing them is a
separate decision.

Idempotent: signals already present are skipped, so a re-run adds nothing.
Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys
from collections import Counter, defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
CAMPAIGN = 24209664922

KITCHEN = "BP - Outdoor Kitchen & Grill Buyers"
PATIO = "BP - Patio Furniture Buyers"
FIRE = "BP - Fire Feature Buyers"

# (in_market, affinity, life_events, detailed_demographics)
AUDIENCES = {
    KITCHEN: (
        "People building or kitting out an outdoor kitchen: built-in grills, "
        "islands, griddles, refrigeration and vent hoods. Weighted to "
        "homeowners mid-renovation and the contractors who build these.",
        [(80264, "BBQs & Grills"), (80925, "BBQ & Grill Accessories"),
         (80241, "Home Improvement"), (80266, "Kitchen & Bathroom Cabinets"),
         (80490, "General Contracting & Remodeling Services"),
         (80501, "Outdoor Items"), (80237, "Home & Garden")],
        [(92946, "Home & Garden"), (92501, "Luxury Shoppers")],
        [(95015, "Home Renovation"), (95017, "Renovating Home Soon"),
         (95034, "Recently Purchased a Home")],
        [(30007, "Homeowners")],
    ),
    PATIO: (
        "Buyers of high-ticket outdoor seating and dining: teak, wicker, "
        "sectionals, daybeds and dining sets. Homeowners furnishing a patio "
        "or deck, plus hospitality buyers.",
        [(80253, "Garden & Outdoor Furniture"), (80926, "Outdoor Furniture Sets"),
         (80501, "Outdoor Items"), (80241, "Home Improvement"),
         (80237, "Home & Garden"), (80494, "Landscape Design")],
        [(90100, "Outdoor Enthusiasts"), (92946, "Home & Garden"),
         (92501, "Luxury Shoppers")],
        [(95034, "Recently Purchased a Home"), (95015, "Home Renovation"),
         (95016, "Recently Renovated Home")],
        [(30007, "Homeowners")],
    ),
    FIRE: (
        "Buyers of fire pits, fire tables, fire and water bowls and electric "
        "fireplaces -- a backyard focal point purchase, not an impulse buy.",
        [(80256, "Fireplaces"), (80501, "Outdoor Items"),
         (80241, "Home Improvement"), (80237, "Home & Garden"),
         (80494, "Landscape Design"), (80243, "Pools & Spas")],
        [(90100, "Outdoor Enthusiasts"), (92946, "Home & Garden"),
         (92501, "Luxury Shoppers")],
        [(95015, "Home Renovation"), (95017, "Renovating Home Soon"),
         (95034, "Recently Purchased a Home")],
        [(30007, "Homeowners")],
    ),
}

# asset group name -> (audience, [search themes])
# Themes written from the product types and titles actually in the feed.
# Cal Flame and Mont Alpi already carry 25 themes each, so they take the
# audience only -- an empty theme list means "audience only, do not add themes".
GROUPS = {
    "BP · Cal Flame": (KITCHEN, []),
    "BP · Mont Alpi": (KITCHEN, []),

    "BP · Blaze": (KITCHEN, [
        "blaze grill", "blaze built in grill", "built in gas grill",
        "stainless steel built in grill", "blaze griddle",
        "outdoor refrigerator", "bbq vent hood", "blaze professional grill",
        "4 burner built in grill", "outdoor kitchen grill insert",
        "blaze outdoor products", "built in grill with rotisserie",
        "outdoor grill vent hood", "blaze grill accessories",
        "premium built in bbq grill"]),
    "BP · Bull": (KITCHEN, [
        "bull grill", "bull bbq grill", "bull outdoor products",
        "bbq grill cart", "outdoor kegerator", "built in bull grill",
        "bull angus grill", "stainless bbq grill cart", "bull grill parts",
        "outdoor kitchen kegerator", "bull bbq island", "propane grill cart",
        "bull power burner", "bbq side burner", "bull brahma grill"]),
    "BP · Coyote Outdoor Living": (KITCHEN, [
        "coyote grill", "coyote outdoor living", "coyote built in grill",
        "outdoor kitchen doors and drawers", "coyote griddle",
        "outdoor refrigeration drawer", "coyote c series grill",
        "built in outdoor griddle", "stainless access doors outdoor kitchen",
        "coyote s series grill", "outdoor kitchen storage drawers",
        "coyote pellet grill", "built in outdoor refrigerator",
        "coyote asado smoker", "outdoor kitchen appliance package"]),
    "BP · Le Griddle": (KITCHEN, [
        "le griddle", "outdoor teppanyaki griddle", "built in outdoor griddle",
        "stainless steel griddle", "gas griddle for outdoor kitchen",
        "le griddle wee", "griddle cart", "electric outdoor griddle",
        "flat top griddle outdoor", "le griddle lid",
        "built in flat top grill", "portable outdoor griddle",
        "commercial outdoor griddle", "griddle for bbq island",
        "le griddle accessories"]),
    "BP · Napoleon": (KITCHEN, [
        "napoleon grill", "napoleon gas grill", "napoleon built in grill",
        "napoleon prestige", "infrared gas grill", "napoleon bbq",
        "built in propane grill", "napoleon rogue",
        "grill with infrared side burner", "napoleon phantom grill",
        "stainless gas grill", "napoleon power burner",
        "napoleon grill accessories", "4 burner gas grill",
        "napoleon prestige pro"]),
    "BP · Primo Ceramic Grills": (KITCHEN, [
        "primo ceramic grills", "kamado grill", "ceramic charcoal grill",
        "primo oval grill", "kamado smoker", "primo grill cart",
        "ceramic kamado cooker", "built in kamado grill",
        "charcoal ceramic smoker", "primo grill table", "oval ceramic grill",
        "kamado grill island top", "primo xl grill",
        "ceramic grill accessories", "egg style charcoal grill"]),
    "BP · RCS": (KITCHEN, [
        "rcs grill", "rcs gas grill", "rcs premier grill",
        "built in stainless grill", "bbq access doors",
        "outdoor kitchen drawers", "rcs cutlass grill",
        "grill cart stainless", "outdoor power burner", "rcs bbq",
        "built in bbq grill 30 inch", "outdoor kitchen doors",
        "rcs grill accessories", "stainless steel bbq cart",
        "rcs outdoor fireplace"]),
    "BP · Summerset Professional Grills": (KITCHEN, [
        "summerset grill", "summerset professional grills",
        "summerset sizzler", "built in bbq grill", "summerset alturi",
        "outdoor vent hood", "outdoor kitchen sink",
        "bbq doors and drawers", "double side burner", "summerset trl grill",
        "freestanding gas grill", "outdoor kitchen griddle",
        "stainless outdoor kitchen components", "summerset grill accessories",
        "built in grill with lights"]),
    "BP · Big Ridge Outdoor Kitchens": (KITCHEN, [
        "big ridge outdoor kitchens", "outdoor kitchen island",
        "prefab outdoor kitchen", "bbq island with grill",
        "modular outdoor kitchen", "outdoor bar island",
        "outdoor kitchen with sink", "stone outdoor kitchen island",
        "complete outdoor kitchen", "l shaped outdoor kitchen",
        "outdoor kitchen island kit", "built in bbq island",
        "outdoor kitchen cabinets", "backyard kitchen island",
        "granite outdoor kitchen"]),
    "BP · MirageVision TV": (KITCHEN, [
        "miragevision tv", "outdoor tv", "weatherproof outdoor television",
        "all weather outdoor tv", "outdoor tv for patio",
        "full sun outdoor tv", "75 inch outdoor tv", "outdoor tv enclosure",
        "waterproof tv", "patio television", "outdoor smart tv",
        "high brightness outdoor tv", "poolside tv",
        "outdoor entertainment tv", "large outdoor tv"]),

    "BP · Anderson Teak": (PATIO, [
        "anderson teak", "teak patio furniture", "teak outdoor furniture",
        "teak dining set", "outdoor teak bench", "grade a teak furniture",
        "teak patio dining set", "teak deep seating set",
        "teak bar set outdoor", "luxury teak furniture",
        "teak outdoor armchair", "teak garden bench", "teak chaise lounge",
        "solid teak patio set", "outdoor teak furniture set"]),
    "BP · Hospitality Rattan Patio": (PATIO, [
        "hospitality rattan patio", "wicker patio furniture",
        "outdoor daybed", "rattan sectional sofa",
        "outdoor modular sectional", "wicker deep seating set",
        "outdoor bistro set", "hanging patio chair",
        "resin wicker furniture", "outdoor daybed with canopy",
        "patio conversation set", "all weather wicker furniture",
        "outdoor bar and pub table", "wicker outdoor sofa set",
        "commercial patio furniture"]),
    "BP · Panama Jack Outdoor": (PATIO, [
        "panama jack outdoor", "panama jack patio furniture",
        "outdoor conversation set", "chaise lounge set", "patio bar set",
        "outdoor adirondack chair", "wicker chaise lounge",
        "outdoor bistro set", "patio sectional set", "outdoor daybed set",
        "coastal patio furniture", "rattan dining set outdoor",
        "patio arm chairs", "outdoor deep seating set",
        "panama jack bar stool"]),
    "BP · Panama Jack Sunroom": (PATIO, [
        "panama jack sunroom", "sunroom furniture set",
        "indoor wicker furniture", "sunroom seating set",
        "rattan living room set", "wicker sunroom furniture",
        "sunroom sofa set", "indoor rattan furniture",
        "5 piece living set", "panama jack exuma",
        "tropical sunroom furniture", "wicker indoor sofa",
        "sunroom furniture with cushions", "indoor wicker seating",
        "conservatory furniture"]),

    "BP · The Outdoor Plus": (FIRE, [
        "the outdoor plus", "fire table", "concrete fire table",
        "gas fire pit table", "fire and water bowl", "fire bowl",
        "rectangular fire table", "gfrc fire table", "outdoor water bowl",
        "fire pit with electronic ignition", "modern fire table",
        "custom fire pit table", "planter and water bowl",
        "linear fire table", "copper fire bowl"]),
    "BP · Fire Pit Art": (FIRE, [
        "fire pit art", "steel fire pit", "sculptural fire pit",
        "handcrafted fire pit", "carbon steel fire pit", "luxury fire pit",
        "wood burning fire pit", "large outdoor fire pit",
        "designer fire pit bowl", "gas fire pit sphere", "artistic fire pit",
        "metal fire pit bowl", "custom fire pit", "fire pit with lid",
        "high end fire pit"]),
    "BP · Dimplex": (FIRE, [
        "dimplex electric fireplace", "electric fireplace insert",
        "wall mounted electric fireplace", "linear electric fireplace",
        "dimplex fireplace", "electric fireplace log set",
        "built in electric fireplace", "electric stove heater",
        "dimplex ignite", "modern electric fireplace",
        "electric fireplace with heater", "recessed electric fireplace",
        "multi sided electric fireplace", "electric firebox insert",
        "72 inch electric fireplace"]),
}

SEARCH_THEME_MAX, THEMES_PER_GROUP_MAX = 80, 25


def validate():
    bad = []
    for nm, (aud, themes) in GROUPS.items():
        if aud not in AUDIENCES:
            bad.append(f"{nm}: unknown audience {aud!r}")
        if len(themes) > THEMES_PER_GROUP_MAX:
            bad.append(f"{nm}: {len(themes)} themes exceeds {THEMES_PER_GROUP_MAX}")
        if len(set(themes)) != len(themes):
            bad.append(f"{nm}: duplicate themes within the group")
        for t in themes:
            if len(t) > SEARCH_THEME_MAX or not t.strip() or t != t.strip():
                bad.append(f"{nm}: bad theme {t!r} (len {len(t)})")
    if bad:
        print("VALIDATION FAILED:")
        for b in bad:
            print("  " + b)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    validate()
    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")

    # ---- servable products per brand and per product type -------------------
    # Discount the account-wide "no campaigns advertising this product" error;
    # any other error means the product genuinely cannot serve.
    by_brand, by_type = Counter(), Counter()
    for r in ga.search(customer_id=cust, query="""
        SELECT shopping_product.brand, shopping_product.product_type_level1,
               shopping_product.availability, shopping_product.issues
        FROM shopping_product"""):
        p = r.shopping_product
        real = {i.error_code for i in p.issues} - {"not_eligible_in_any_campaign",
                                                   "low_manual_bids"}
        if real or p.availability.name != "IN_STOCK":
            continue
        by_brand[(p.brand or "").strip().lower()] += 1
        by_type[(p.product_type_level1 or "").strip().lower()] += 1

    # ---- live asset groups and what each one includes -----------------------
    live, included = {}, defaultdict(set)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group.primary_status, campaign.id
        FROM asset_group
        WHERE campaign.id = {CAMPAIGN} AND asset_group.status = 'ENABLED'"""):
        live[r.asset_group.name] = (r.asset_group.id,
                                    r.asset_group.primary_status.name)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status,
               asset_group_listing_group_filter.type,
               asset_group_listing_group_filter.case_value.product_brand.value,
               asset_group_listing_group_filter.case_value.product_type.value,
               campaign.id
        FROM asset_group_listing_group_filter WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group.status.name != "ENABLED":
            continue
        f = r.asset_group_listing_group_filter
        if f.type_.name != "UNIT_INCLUDED":
            continue
        b, t = f.case_value.product_brand.value, f.case_value.product_type.value
        if b:
            included[r.asset_group.name].add(("brand", b.strip().lower()))
        elif t:
            included[r.asset_group.name].add(("type", t.strip().lower()))

    def servable(nm):
        return sum(by_brand[v] if kind == "brand" else by_type[v]
                   for kind, v in included[nm])

    unknown = [nm for nm in GROUPS if nm not in live]
    if unknown:
        print(f"ABORT: not ENABLED in campaign {CAMPAIGN}: {unknown}")
        return 1

    # A group I wrote themes for must actually have products. If the feed moved
    # under us, stop rather than push themes for something that cannot serve.
    empty_but_planned = [nm for nm in GROUPS if servable(nm) == 0]
    if empty_but_planned:
        print("ABORT: these groups are in the plan but have 0 servable "
              "products -- the feed has changed, re-check before pushing:")
        for nm in empty_but_planned:
            print(f"    {nm}  includes {sorted(included[nm])}")
        return 1

    dead = sorted(nm for nm in live if nm not in GROUPS and servable(nm) == 0)
    other = sorted(nm for nm in live if nm not in GROUPS and servable(nm) > 0)

    # ---- existing signals, so a re-run is a no-op ---------------------------
    have = defaultdict(lambda: {"themes": set(), "aud": set()})
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name,
               asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, campaign.id
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group_signal.search_theme.text:
            have[r.asset_group.name]["themes"].add(
                r.asset_group_signal.search_theme.text)
        if r.asset_group_signal.audience.audience:
            have[r.asset_group.name]["aud"].add(
                r.asset_group_signal.audience.audience)

    existing_auds = {r.audience.name: r.audience.id
                     for r in ga.search(customer_id=cust, query="""
        SELECT audience.id, audience.name, audience.status FROM audience
        WHERE audience.status = 'ENABLED'""")}

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\naccount {ACCOUNT} [{cust}]   campaign {CAMPAIGN}")
    print(f"{len(live)} enabled asset groups: {len(GROUPS)} in the plan, "
          f"{len(dead)} skipped as empty, {len(other)} other")

    print("\nAUDIENCES to create:")
    for nm, (desc, im, aff, le, dd) in AUDIENCES.items():
        n = len(im) + len(aff) + len(le) + len(dd)
        exists = " (ALREADY EXISTS -- will reuse)" if nm in existing_auds else ""
        print(f"\n  {nm!r}  {n} segments{exists}")
        for label, items in (("in-market", im), ("affinity", aff),
                             ("life event", le), ("demographic", dd)):
            for _id, lbl in items:
                print(f"      {label:12} {_id:>6}  {lbl}")

    # Resolve audiences that already exist up front, so the dry run can tell
    # whether a group's audience signal is genuinely missing.
    known_aud_rn = {nm: f"customers/{cust}/audiences/{existing_auds[nm]}"
                    for nm in AUDIENCES if nm in existing_auds}

    print("\n\nPER-GROUP PLAN")
    total_themes = total_aud = 0
    plan = []
    for nm, (aud, themes) in sorted(GROUPS.items(),
                                    key=lambda kv: (kv[1][0], kv[0])):
        new_themes = [t for t in themes if t not in have[nm]["themes"]]
        # If the audience does not exist yet it cannot be signalled yet, so it
        # is certainly needed; if it does, check whether this group has it.
        need_aud = known_aud_rn.get(aud) not in have[nm]["aud"]
        total_themes += len(new_themes)
        total_aud += need_aud
        plan.append((nm, aud, new_themes))
        note = "" if themes else "  (already has themes)"
        print(f"  {nm:38} {servable(nm):>5} products  aud={aud.split(' - ')[1][:22]:24} "
              f"{'+aud' if need_aud else '   .'} +{len(new_themes):>2} themes{note}")

    if dead:
        print(f"\n\nSKIPPED -- brand has NO servable products, so themes would "
              f"buy traffic the store cannot fulfil ({len(dead)}):")
        for nm in dead:
            print(f"  {nm:38} includes {sorted(v for _, v in included[nm])}")
        print("  These are left untouched. Pausing them is a separate call.")
    if other:
        print(f"\nNOT IN THE PLAN but has products ({len(other)}): {other}")

    new_auds = [nm for nm in AUDIENCES if nm not in existing_auds]
    print(f"\nTOTAL: {len(new_auds)} audiences to create "
          f"({len(AUDIENCES) - len(new_auds)} reused), "
          f"{total_aud} audience signals, {total_themes} search themes")
    if not total_aud and not total_themes and not new_auds:
        print("Everything already in place -- nothing to do.")
        return 0

    if not args.execute:
        print("\nDry run. Re-run with --execute to push.")
        return 0

    # ---- audiences ---------------------------------------------------------
    aud_rn = {}
    for nm, (desc, im, aff, le, dd) in AUDIENCES.items():
        if nm in existing_auds:
            aud_rn[nm] = f"customers/{cust}/audiences/{existing_auds[nm]}"
            print(f"  reusing audience {nm!r}")
            continue
        op = client.get_type("AudienceOperation")
        a = op.create
        a.name = nm
        a.description = desc
        dim = client.get_type("AudienceDimension")
        seg = dim.audience_segments
        for _id, _ in im + aff:
            s = client.get_type("AudienceSegment")
            s.user_interest.user_interest_category = (
                f"customers/{cust}/userInterests/{_id}")
            seg.segments.append(s)
        for _id, _ in le:
            s = client.get_type("AudienceSegment")
            s.life_event.life_event = f"customers/{cust}/lifeEvents/{_id}"
            seg.segments.append(s)
        for _id, _ in dd:
            s = client.get_type("AudienceSegment")
            s.detailed_demographic.detailed_demographic = (
                f"customers/{cust}/detailedDemographics/{_id}")
            seg.segments.append(s)
        a.dimensions.append(dim)
        aud_rn[nm] = client.get_service("AudienceService").mutate_audiences(
            customer_id=cust, operations=[op]).results[0].resource_name
        print(f"  created audience {aud_rn[nm]}  {nm!r}")

    # ---- signals -----------------------------------------------------------
    ag_svc = client.get_service("AssetGroupService")
    ops = []
    for nm, aud, new_themes in plan:
        gid = live[nm][0]
        rn = ag_svc.asset_group_path(cust, gid)
        if aud_rn[aud] not in have[nm]["aud"]:
            o = client.get_type("AssetGroupSignalOperation")
            o.create.asset_group = rn
            o.create.audience.audience = aud_rn[aud]
            ops.append(o)
        for t in new_themes:
            o = client.get_type("AssetGroupSignalOperation")
            o.create.asset_group = rn
            o.create.search_theme.text = t
            ops.append(o)
    if not ops:
        print("\nNothing to create.")
        return 0
    client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
        customer_id=cust, operations=ops)
    print(f"\n  created {len(ops)} signals")

    # ---- read-back ---------------------------------------------------------
    print("\n--- read-back: every enabled asset group in the campaign ---")
    back = defaultdict(lambda: [0, 0])
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name,
               asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, campaign.id
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        if r.asset_group_signal.search_theme.text:
            back[r.asset_group.name][0] += 1
        if r.asset_group_signal.audience.audience:
            back[r.asset_group.name][1] += 1
    for nm in sorted(live):
        t, a = back[nm]
        tag = "  <-- skipped, no products" if nm in dead else ""
        print(f"  {nm:38} themes={t:>3} audience={a}{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
