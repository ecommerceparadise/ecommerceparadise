"""Search themes and the shared audience signal for the four LES brand asset
groups added on 2026-09-28 (Ortur, LaserPecker, Full Spectrum Laser, FlashForge).

Those groups were created to close a coverage gap and went in with listing
filters only. The seven older brand groups each carry 15 search themes plus the
'LES - Laser Engraver Buyers' audience; these four carried none, so PMax had no
query signal for them at all. This brings them to the same shape.

Themes are written from the titles actually in the feed, not from the brand name:
Full Spectrum Laser is industrial CO2 and galvo at $2,999-$54,945, FlashForge is
multi-colour FDM 3D printers, LaserPecker is portable dual fiber+diode, Ortur is
entry and mid-range diode with IR modules.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24208827507
# The same audience the seven existing brand groups already signal with.
AUDIENCE_ID = 358310333
AUDIENCE_NAME = "LES - Laser Engraver Buyers"

THEMES = {
    6750246364: (  # LES - Ortur -- diode + IR, $620-$1,740, LM3 / H20 / R2 / H10
        "LES - Ortur", [
            "ortur laser engraver", "ortur laser master 3", "ortur lm3",
            "ortur h20", "diode laser engraver", "40w diode laser engraver",
            "laser engraver for wood", "laser engraver with air assist",
            "infrared laser module", "ir laser engraver for metal",
            "desktop laser engraver", "laser engraver for beginners",
            "20w diode laser engraver", "laser engraver with rotary",
            "dual laser diode and infrared",
        ]),
    6750246367: (  # LES - LaserPecker -- portable dual, $1,099-$5,155
        "LES - LaserPecker", [
            "laserpecker", "laserpecker lp5", "laserpecker lx2",
            "laserpecker lp4", "portable laser engraver",
            "fiber and diode dual laser engraver",
            "handheld laser engraver", "laser engraver for metal and wood",
            "dual laser engraver", "compact laser cutter",
            "laser engraver for small business", "40w diode laser cutter",
            "all in one laser engraver", "laser engraver with enclosure",
            "cordless laser engraver",
        ]),
    6750246088: (  # LES - Full Spectrum Laser -- industrial, $2,999-$54,945
        "LES - Full Spectrum Laser", [
            "full spectrum laser", "muse laser engraver",
            "full spectrum muse", "industrial co2 laser engraver",
            "uv galvo laser engraver", "fiber galvo laser marking machine",
            "pro series industrial laser cutter",
            "150w co2 laser cutter", "large format co2 laser engraver",
            "production laser engraver", "commercial laser cutter",
            "laser engraver made in usa", "autofocus co2 laser engraver",
            "galvo laser marking system", "high power co2 laser engraver",
        ]),
    6750357714: (  # LES - FlashForge -- Creator 5 multi-colour FDM
        "LES - FlashForge", [
            "flashforge", "flashforge creator 5",
            "multi color 3d printer", "4 toolhead 3d printer",
            "multi material 3d printer", "enclosed 3d printer",
            "flashforge 3d printer", "multi tool head 3d printer",
            "3d printer with multiple extruders",
            "color 3d printer", "desktop 3d printer for business",
            "professional multi color 3d printer",
            "3d printer for prototyping", "toolchanger 3d printer",
            "flashforge creator 5 pro",
        ]),
}

SEARCH_THEME_MAX, THEMES_PER_GROUP_MAX = 80, 25


def validate():
    bad = []
    seen_global = {}
    for ag, (name, themes) in THEMES.items():
        if len(themes) > THEMES_PER_GROUP_MAX:
            bad.append(f"{name}: {len(themes)} themes exceeds {THEMES_PER_GROUP_MAX}")
        if len(set(themes)) != len(themes):
            bad.append(f"{name}: duplicate themes within the group")
        for t in themes:
            if len(t) > SEARCH_THEME_MAX:
                bad.append(f"{name}: theme too long ({len(t)}): {t!r}")
            if t != t.strip() or not t:
                bad.append(f"{name}: blank or padded theme {t!r}")
            seen_global.setdefault(t, []).append(name)
    # Overlap across groups is allowed (the existing groups overlap on generic
    # terms too) but worth printing so it is a decision, not an accident.
    if bad:
        print("VALIDATION FAILED:")
        for b in bad:
            print("  " + b)
        sys.exit(1)
    dupes = {t: g for t, g in seen_global.items() if len(g) > 1}
    if dupes:
        print("note: themes shared by more than one group (allowed):")
        for t, g in sorted(dupes.items()):
            print(f"    {t!r} -> {', '.join(g)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    validate()
    client = get_client()
    cust = resolve_account("Laser Engraver Store")["id"]
    ga = client.get_service("GoogleAdsService")

    # Only ENABLED groups. Removed asset groups still return from the API and
    # five of them sit in this campaign, so never trust an unfiltered read.
    live = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status, campaign.id
        FROM asset_group
        WHERE campaign.id = {CAMPAIGN} AND asset_group.status = 'ENABLED'"""):
        live[r.asset_group.id] = r.asset_group.name

    missing = [f"{ag} ({THEMES[ag][0]})" for ag in THEMES if ag not in live]
    if missing:
        print(f"Not ENABLED in campaign {CAMPAIGN}: {missing}. Aborting.")
        return 1
    for ag, (name, _) in THEMES.items():
        if live[ag] != name:
            print(f"Name mismatch for {ag}: expected {name!r}, "
                  f"live is {live[ag]!r}. Aborting.")
            return 1

    # Refuse to double up: these groups are meant to have no signals yet.
    existing = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, asset_group.id, campaign.id
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        existing.setdefault(r.asset_group.id, {"themes": set(), "aud": set()})
        if r.asset_group_signal.search_theme.text:
            existing[r.asset_group.id]["themes"].add(
                r.asset_group_signal.search_theme.text)
        if r.asset_group_signal.audience.audience:
            existing[r.asset_group.id]["aud"].add(
                r.asset_group_signal.audience.audience)

    audience_rn = f"customers/{cust}/audiences/{AUDIENCE_ID}"
    found = [r.audience.name for r in ga.search(customer_id=cust, query=f"""
        SELECT audience.id, audience.name, audience.status FROM audience
        WHERE audience.id = {AUDIENCE_ID} AND audience.status = 'ENABLED'""")]
    if not found:
        print(f"Audience {AUDIENCE_ID} not found or not ENABLED. Aborting.")
        return 1
    if found[0] != AUDIENCE_NAME:
        print(f"Audience {AUDIENCE_ID} is {found[0]!r}, expected "
              f"{AUDIENCE_NAME!r}. Aborting.")
        return 1

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\naccount  {cust}   campaign {CAMPAIGN}")
    print(f"audience {AUDIENCE_ID}  {found[0]!r}  (shared with the 7 existing groups)")

    plan = []
    for ag, (name, themes) in THEMES.items():
        have = existing.get(ag, {"themes": set(), "aud": set()})
        new_themes = [t for t in themes if t not in have["themes"]]
        need_aud = audience_rn not in have["aud"]
        plan.append((ag, name, new_themes, need_aud))
        print(f"\n{name}  [{ag}]")
        print(f"    has {len(have['themes'])} themes, {len(have['aud'])} audience(s)")
        print(f"    + audience: {'yes' if need_aud else 'already present, skipping'}")
        print(f"    + {len(new_themes)} search themes")
        for t in new_themes:
            print(f"        {t}")
        skipped = [t for t in themes if t in have["themes"]]
        if skipped:
            print(f"    already present, skipping: {skipped}")

    total = sum(len(p[2]) for p in plan) + sum(1 for p in plan if p[3])
    print(f"\nTOTAL signals to create: {total}")
    if not total:
        print("Nothing to do.")
        return 0
    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    ag_svc = client.get_service("AssetGroupService")
    ops = []
    for ag, name, new_themes, need_aud in plan:
        ag_rn = ag_svc.asset_group_path(cust, ag)
        if need_aud:
            o = client.get_type("AssetGroupSignalOperation")
            o.create.asset_group = ag_rn
            o.create.audience.audience = audience_rn
            ops.append(o)
        for t in new_themes:
            o = client.get_type("AssetGroupSignalOperation")
            o.create.asset_group = ag_rn
            o.create.search_theme.text = t
            ops.append(o)
    client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
        customer_id=cust, operations=ops)
    print(f"\n  created {len(ops)} signals")

    print("\n--- read-back: all LIVE asset groups in the campaign ---")
    back = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group_signal.search_theme.text,
               asset_group_signal.audience.audience, asset_group.id, campaign.id
        FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
        b = back.setdefault(r.asset_group.id, [0, 0])
        if r.asset_group_signal.search_theme.text:
            b[0] += 1
        if r.asset_group_signal.audience.audience:
            b[1] += 1
    for agid, nm in sorted(live.items(), key=lambda kv: kv[1]):
        t, a = back.get(agid, [0, 0])
        flag = "  <-- still empty" if t == 0 else ""
        print(f"    {nm:32} themes={t:>3} audience={a}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
