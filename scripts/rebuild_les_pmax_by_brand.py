"""Re-segment the Laser Engraver Store PMax campaign into ONE ASSET GROUP PER
BRAND, matching the Fountains USA pattern.

Replaces the five laser-type asset groups built earlier. Trevor's call: the
house pattern is brand asset groups, and it is his to set.

Six brands, all lasers:

    gweike cloud   69   CO2, fiber, diode, dual, accessories   $1,279-$13,699
    monportlaser   69   MOPA, fiber, CO2, industrial CO2, UV     $800-$12,520
    sculpfun       30   diode, some fiber and UV                 $550-$3,999
    toocaa          6   diode                                    $649-$1,199
    atomstack       5   laser engravers, CNC hybrid              $898-$3,239
    flux            4   CO2                                    $2,799-$8,999

The seventh brand, vision miner, is exactly the two products typed '3d printer'
at $19,370 each. It gets no asset group, so those two fall into every group's
"everything else" bucket and stay excluded -- Trevor chose "drop 3D printers
for now" earlier in this session. Adding a seventh asset group is a one-line
change if he wants them back.

Removes and creates in a single atomic mutate so the campaign is never left
without an asset group. Signals are re-applied afterwards against the real IDs.

Dry run unless --live.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24208827507
STORE_URL = "https://laserengraverstore.com"
AUDIENCE_RN_ID = 358310333          # LES - Laser Engraver Buyers, already built

BRANDS = [
    ("Gweike Cloud", "gweike cloud", 69, [
        "gweike cloud laser", "gweike laser engraver", "co2 laser cutter",
        "desktop co2 laser engraver", "laser cutter for small business",
        "dual laser engraver", "fiber and co2 combo laser",
        "50w co2 laser engraver", "enclosed laser cutter",
        "laser cutter with air filter", "laser engraver for wood and acrylic",
        "gweike cloud pro", "laser cutter with camera",
        "all in one laser engraver", "laser engraver with fume extractor"]),
    ("Monport", "monportlaser", 69, [
        "monport laser", "monport laser engraver", "mopa fiber laser",
        "fiber laser marking machine", "metal laser engraver",
        "industrial co2 laser cutter", "100w co2 laser",
        "uv laser marking machine", "laser engraver for metal",
        "60w fiber laser engraver", "monport co2 laser",
        "color laser marking metal", "large format co2 laser",
        "laser marking machine for steel", "handheld laser engraver"]),
    ("Sculpfun", "sculpfun", 30, [
        "sculpfun laser engraver", "sculpfun s30", "diode laser engraver",
        "laser engraver for wood", "desktop laser engraver",
        "10w diode laser", "20w diode laser engraver",
        "laser engraver for beginners", "hobby laser engraver",
        "enclosed diode laser", "laser engraver for crafts",
        "sculpfun s30 pro", "compact laser engraver",
        "laser engraver for leather", "affordable laser engraver"]),
    ("TOOCAA", "toocaa", 6, [
        "toocaa laser engraver", "toocaa nova",
        "desktop diode laser engraver", "10w laser engraver",
        "entry level laser engraver", "laser engraver for wood",
        "small laser engraver", "beginner laser engraver",
        "diode laser cutter", "portable laser engraver",
        "laser engraver for hobbyists", "compact diode laser",
        "laser engraver for crafts", "tabletop laser engraver",
        "laser engraver for small business"]),
    ("AtomStack", "atomstack", 5, [
        "atomstack laser engraver", "atomstack c4", "cnc laser hybrid",
        "cnc router laser combo", "atomstack atelier",
        "laser and cnc machine", "desktop cnc router",
        "diode laser engraver", "laser engraver with cnc",
        "hybrid laser cnc machine", "atomstack laser",
        "cnc machine for wood", "laser engraver and cutter",
        "multifunction laser machine", "compact cnc router"]),
    ("FLUX", "flux", 4, [
        "flux beamo", "flux beambox", "flux laser cutter",
        "30w co2 laser engraver", "40w co2 laser engraver",
        "desktop co2 laser cutter", "compact co2 laser", "beambox pro",
        "laser cutter for acrylic", "flux laser engraver",
        "co2 laser for small business", "enclosed co2 laser cutter",
        "laser cutter with camera", "laser engraver for glass",
        "co2 laser engraving machine"]),
]


def validate():
    bad = []
    for label, _, _, themes in BRANDS:
        if len(themes) > 25:
            bad.append(f"{label}: {len(themes)} themes exceeds 25")
        if len(set(themes)) != len(themes):
            bad.append(f"{label}: duplicate themes")
        for t in themes:
            if len(t) > 80:
                bad.append(f"{label}: theme too long: {t!r}")
    if bad:
        print("VALIDATION FAILED:")
        for b in bad:
            print("  " + b)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    validate()

    client = get_client()
    cust = resolve_account("Laser Engraver Store", client=client)["id"]
    e = client.enums
    ga = client.get_service("GoogleAdsService")

    existing = [(r.asset_group.id, r.asset_group.name) for r in ga.search(
        customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name FROM asset_group
        WHERE campaign.id = {CAMPAIGN} AND asset_group.status != 'REMOVED'""")]

    print(f"{'LIVE' if args.live else 'DRY RUN'}")
    print(f"\nREMOVE {len(existing)} laser-type asset groups:")
    for _id, name in existing:
        print(f"    {_id}  {name}")
    print(f"\nCREATE {len(BRANDS)} brand asset groups:")
    covered = 0
    for label, feed_brand, count, themes in BRANDS:
        covered += count
        print(f"    LES - {label:14} brand={feed_brand!r:18} {count:>3} products, "
              f"{len(themes)} themes")
    print(f"\n    {covered} of 185 products. vision miner (2 products, both typed "
          f"'3d printer',\n    $19,370 each) gets no asset group and stays excluded.")

    ops = []
    def op():
        o = client.get_type("MutateOperation")
        ops.append(o)
        return o
    tmp = [0]
    def nxt():
        tmp[0] -= 1
        return tmp[0]

    for _id, _ in existing:
        op().asset_group_operation.remove = f"customers/{cust}/assetGroups/{_id}"

    for label, feed_brand, _count, _themes in BRANDS:
        ag_t = nxt()
        ag_rn = f"customers/{cust}/assetGroups/{ag_t}"
        ag = op().asset_group_operation.create
        ag.resource_name = ag_rn
        ag.campaign = f"customers/{cust}/campaigns/{CAMPAIGN}"
        ag.name = f"LES - {label}"
        ag.final_urls.append(STORE_URL)
        ag.status = e.AssetGroupStatusEnum.ENABLED

        root_rn = f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        r = op().asset_group_listing_group_filter_operation.create
        r.resource_name = root_rn
        r.asset_group = ag_rn
        r.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
        r.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING

        inc = op().asset_group_listing_group_filter_operation.create
        inc.resource_name = f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        inc.asset_group = ag_rn
        inc.type_ = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
        inc.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        inc.parent_listing_group_filter = root_rn
        inc.case_value.product_brand.value = feed_brand

        oth = op().asset_group_listing_group_filter_operation.create
        oth.resource_name = f"customers/{cust}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        oth.asset_group = ag_rn
        oth.type_ = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
        oth.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        oth.parent_listing_group_filter = root_rn
        oth.case_value._pb.product_brand.SetInParent()

    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = cust
    req.mutate_operations.extend(ops)
    req.validate_only = not args.live
    resp = ga.mutate(request=req)
    print(f"\n  {len(ops)} operations "
          f"{'applied' if args.live else 'validated OK'}")

    if not args.live:
        print("\nRe-run with --live to apply.")
        return 0

    new = {r.asset_group.name: r.asset_group.id for r in ga.search(
        customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name FROM asset_group
        WHERE campaign.id = {CAMPAIGN} AND asset_group.status != 'REMOVED'""")}
    audience_rn = f"customers/{cust}/audiences/{AUDIENCE_RN_ID}"
    ag_svc = client.get_service("AssetGroupService")
    sig_ops = []
    for label, _fb, _c, themes in BRANDS:
        agid = new[f"LES - {label}"]
        ag_rn = ag_svc.asset_group_path(cust, agid)
        o = client.get_type("AssetGroupSignalOperation")
        o.create.asset_group = ag_rn
        o.create.audience.audience = audience_rn
        sig_ops.append(o)
        for t in themes:
            o = client.get_type("AssetGroupSignalOperation")
            o.create.asset_group = ag_rn
            o.create.search_theme.text = t
            sig_ops.append(o)
    client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
        customer_id=cust, operations=sig_ops)
    print(f"  {len(sig_ops)} signals created "
          f"({len(BRANDS)} audience + {sum(len(b[3]) for b in BRANDS)} themes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
