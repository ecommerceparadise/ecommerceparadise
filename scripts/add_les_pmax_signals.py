"""Search themes and an audience signal for the Laser Engraver Store PMax campaign.

Same approach as Fountains USA: one shared audience built from in-market
segments that match who actually buys these machines, plus search themes
written per asset group from the laser type that group carries.

The buyer here is not a consumer shopper -- median price is $4,499 and the feed
is fiber, MOPA, CO2, diode and UV engravers. The audience is weighted to
business and industrial buyers: sign shops, jewellers, small manufacturers and
people who have just started a business, alongside the makers and DIYers who
buy the diode machines.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24208827507
AUDIENCE_NAME = "LES - Laser Engraver Buyers"

IN_MARKET = [
    (80883, "Business & Industrial Products"),
    (80271, "Tools"),
    (80874, "Arts & Crafts Supplies"),
    (80886, "Signage"),
    (80921, "Measuring Tools & Sensors"),
    (80433, "Jewelry & Watches"),
]
AFFINITY = [
    (90700, "Do-It-Yourselfers"),
]
LIFE_EVENTS = [
    (95021, "Business Creation"),
    (95023, "Recently Started a Business"),
]
DETAILED_DEMOGRAPHICS = [
    (30026, "Manufacturing Industry"),
    (30028, "Small Employer (1-249 Employees)"),
]

THEMES = {
    6744990183: [  # Fiber & MOPA -- metal marking
        "fiber laser engraver", "fiber laser marking machine",
        "metal laser engraver", "mopa fiber laser",
        "laser engraver for metal", "30w fiber laser",
        "50w fiber laser engraver", "jpt fiber laser",
        "laser marking machine for metal", "color laser engraving metal",
        "industrial fiber laser marker", "fiber laser for jewelry",
        "metal etching machine", "laser annealing machine",
        "fiber laser engraving machine",
    ],
    6744990186: [  # Diode -- wood, hobby, entry level
        "diode laser engraver", "laser engraver for wood",
        "desktop laser engraver", "20w diode laser",
        "laser cutter for wood", "hobby laser engraver",
        "laser engraving machine for beginners", "sculpfun laser engraver",
        "40w diode laser engraver", "laser engraver for small business",
        "wood burning laser machine", "leather laser engraver",
        "laser engraver for crafts", "compact laser engraver",
        "diode laser cutter",
    ],
    6744990189: [  # CO2 -- acrylic, large format, production
        "co2 laser cutter", "co2 laser engraver",
        "laser cutter for acrylic", "100w co2 laser",
        "industrial laser cutter", "laser cutting machine for wood",
        "60w co2 laser engraver", "glass laser engraver",
        "large format laser cutter", "co2 laser engraving machine",
        "laser cutter for small business", "leather laser cutter",
        "fabric laser cutter", "enclosed co2 laser",
        "laser cutter with rotary",
    ],
    6744907054: [  # UV -- plastics, glass, electronics, cold marking
        "uv laser engraver", "uv laser marking machine",
        "laser engraver for plastic", "cold laser marking",
        "laser engraver for glass", "uv laser marker",
        "laser marking for electronics", "3w uv laser engraver",
        "laser engraver for acrylic", "uv laser engraving machine",
        "laser etching machine for glass", "laser marking machine for plastic",
        "high precision laser engraver", "uv laser cutting machine",
        "uv laser printer",
    ],
    6744907057: [  # Accessories & kits
        "laser fume extractor", "laser engraver enclosure",
        "laser rotary attachment", "laser engraver accessories",
        "laser air assist pump", "laser honeycomb bed",
        "laser safety glasses", "laser engraver upgrade kit",
        "hepa filter for laser", "laser chiller",
        "laser engraver stand", "cnc machine",
        "laser engraver bundle", "laser engraving starter kit",
        "laser exhaust fan",
    ],
}

SEARCH_THEME_MAX, THEMES_PER_GROUP_MAX = 80, 25


def validate():
    bad = []
    for ag, themes in THEMES.items():
        if len(themes) > THEMES_PER_GROUP_MAX:
            bad.append(f"{ag}: {len(themes)} themes exceeds {THEMES_PER_GROUP_MAX}")
        if len(set(themes)) != len(themes):
            bad.append(f"{ag}: duplicate themes")
        for t in themes:
            if len(t) > SEARCH_THEME_MAX:
                bad.append(f"{ag}: theme too long: {t!r}")
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
    cust = resolve_account("Laser Engraver Store")["id"]
    ga = client.get_service("GoogleAdsService")

    live = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name FROM asset_group
        WHERE campaign.id = {CAMPAIGN} AND asset_group.status != 'REMOVED'"""):
        live[r.asset_group.id] = r.asset_group.name
    unknown = [ag for ag in THEMES if ag not in live]
    if unknown:
        print(f"Asset groups not in campaign {CAMPAIGN}: {unknown}. Aborting.")
        return 1

    total_segments = (len(IN_MARKET) + len(AFFINITY)
                      + len(LIFE_EVENTS) + len(DETAILED_DEMOGRAPHICS))
    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\nAUDIENCE  {AUDIENCE_NAME!r}  ({total_segments} segments, OR'd)")
    for label, items in (("in-market", IN_MARKET), ("affinity", AFFINITY),
                         ("life event", LIFE_EVENTS),
                         ("demographic", DETAILED_DEMOGRAPHICS)):
        for _id, name in items:
            print(f"    {label:12} {_id:>6}  {name}")
    for ag, themes in THEMES.items():
        print(f"\nSEARCH THEMES  {live[ag]}  ({len(themes)})")
        for t in themes:
            print(f"    {t}")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    aud_op = client.get_type("AudienceOperation")
    aud = aud_op.create
    aud.name = AUDIENCE_NAME
    aud.description = ("Business and industrial buyers of laser engraving and "
                       "marking machines: sign shops, jewellers, small "
                       "manufacturers, new business owners and makers.")
    dim = client.get_type("AudienceDimension")
    seg = dim.audience_segments
    for _id, _ in IN_MARKET + AFFINITY:
        s = client.get_type("AudienceSegment")
        s.user_interest.user_interest_category = f"customers/{cust}/userInterests/{_id}"
        seg.segments.append(s)
    for _id, _ in LIFE_EVENTS:
        s = client.get_type("AudienceSegment")
        s.life_event.life_event = f"customers/{cust}/lifeEvents/{_id}"
        seg.segments.append(s)
    for _id, _ in DETAILED_DEMOGRAPHICS:
        s = client.get_type("AudienceSegment")
        s.detailed_demographic.detailed_demographic = (
            f"customers/{cust}/detailedDemographics/{_id}")
        seg.segments.append(s)
    aud.dimensions.append(dim)
    audience_rn = client.get_service("AudienceService").mutate_audiences(
        customer_id=cust, operations=[aud_op]).results[0].resource_name
    print(f"\n  created audience {audience_rn}")

    ag_svc = client.get_service("AssetGroupService")
    sig_ops = []
    for ag, themes in THEMES.items():
        ag_rn = ag_svc.asset_group_path(cust, ag)
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
    print(f"  created {len(sig_ops)} signals "
          f"({len(THEMES)} audience + {sum(len(v) for v in THEMES.values())} themes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
