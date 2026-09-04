"""Give the Fountains USA PMax campaign the signals it is currently missing.

The campaign (24209826676, feed-only, $15/day) has four brand asset groups and
ZERO asset group signals. With no signals and no creative assets, Google has
nothing to steer on except the product feed, so it explores blind.

This adds both kinds of signal:

  * ONE shared audience -- in-market segments for the product category, plus
    the two affinity segments and two life events that match a $2,500-median
    outdoor water feature, plus homeowners. In-market is the literal
    "actively shopping right now" segment type, so it carries most of the
    weight here.

  * Search themes per asset group, written from what is actually in each
    brand's feed rather than from the brand name. That distinction matters:
    The Outdoor Plus is water bowls, fire & water bowls and pool scuppers --
    modern water features -- not the cast stone garden fountains the other
    three brands sell.

Signals are hints, not targeting. They tell Google where to start; the
campaign still reaches beyond them.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24209826676
AUDIENCE_NAME = "FUSA - In-Market Fountain Buyers"

# Verified against this account's own taxonomy, not guessed from memory.
IN_MARKET = [
    (80239, "Home Decor"),
    (80237, "Home & Garden"),
    (80253, "Garden & Outdoor Furniture"),
    (80494, "Landscape Design"),
    (80501, "Outdoor Items"),
    (80241, "Home Improvement"),
    (80240, "Home Furnishings"),
]
AFFINITY = [
    (92508, "Home Decor Enthusiasts"),
    (92501, "Luxury Shoppers"),
]
LIFE_EVENTS = [
    (95034, "Recently Purchased a Home"),
    (95015, "Home Renovation"),
]
DETAILED_DEMOGRAPHICS = [
    (30007, "Homeowners"),
]

# asset group id -> search themes, drawn from that brand's real product titles
# and product types in the Merchant Center feed.
THEMES = {
    6744416779: [  # FUSA - Giannini Garden -- cast stone / concrete, courtyard, tiered
        "cast stone outdoor fountain", "concrete garden fountain",
        "outdoor courtyard fountain", "tiered garden fountain",
        "large outdoor water fountain", "outdoor wall fountain",
        "stone bird bath", "italian garden fountain",
        "garden fountain with basin", "backyard water fountain",
        "concrete fountain for yard", "outdoor pond fountain",
        "classical garden fountain", "giannini garden fountain",
        "spout wall fountain outdoor",
    ],
    6744416959: [  # FUSA - Metropolitan Galleries -- bronze & marble sculpture
        "bronze outdoor fountain", "marble tiered fountain",
        "lion head wall fountain", "bronze garden sculpture",
        "large marble fountain", "estate garden fountain",
        "bronze wall fountain", "luxury outdoor fountain",
        "sculpture fountain for garden", "tuscan style fountain",
        "two tier marble fountain", "metropolitan galleries fountain",
        "bronze statue fountain", "high end garden fountain",
        "courtyard sculpture fountain",
    ],
    6744417094: [  # FUSA - The Outdoor Plus -- water bowls, scuppers, fire & water
        "outdoor water bowl", "fire and water bowl",
        "concrete water bowl fountain", "copper water bowl",
        "pool scupper", "water scupper for pool",
        "modern water feature", "gfrc concrete fire bowl",
        "rainfall water fountain", "fire and water feature",
        "stainless steel water bowl", "pool water feature",
        "self contained water bowl", "the outdoor plus water bowl",
        "modern outdoor fountain",
    ],
    6744417097: [  # FUSA - Fiore Stone -- cast stone, tiered, lion, bubbler
        "cast stone fountain", "tiered outdoor fountain",
        "lion fountain outdoor", "cast stone wall fountain",
        "large garden fountain", "outdoor fountain with basin",
        "two tier stone fountain", "classic garden fountain",
        "stone courtyard fountain", "fiore stone fountain",
        "outdoor bubbler fountain", "cast stone garden statuary",
        "large cast stone fountain", "traditional outdoor fountain",
        "cast stone rain fountain",
    ],
}

SEARCH_THEME_MAX = 80
THEMES_PER_GROUP_MAX = 25


def validate():
    bad = []
    for ag, themes in THEMES.items():
        if len(themes) > THEMES_PER_GROUP_MAX:
            bad.append(f"{ag}: {len(themes)} themes exceeds {THEMES_PER_GROUP_MAX}")
        if len(set(themes)) != len(themes):
            bad.append(f"{ag}: duplicate themes")
        for t in themes:
            if len(t) > SEARCH_THEME_MAX:
                bad.append(f"{ag}: theme {len(t)}>{SEARCH_THEME_MAX}: {t!r}")
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
    cust = resolve_account("Fountains USA")["id"]
    ga = client.get_service("GoogleAdsService")

    # Confirm the asset groups are the ones we think they are before writing.
    live = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name, asset_group.status
        FROM asset_group WHERE campaign.id = {CAMPAIGN}
          AND asset_group.status != 'REMOVED'"""):
        live[r.asset_group.id] = r.asset_group.name
    unknown = [ag for ag in THEMES if ag not in live]
    if unknown:
        print(f"Asset groups not found in campaign {CAMPAIGN}: {unknown}. Aborting.")
        return 1

    existing = list(ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id FROM asset_group_signal
        WHERE campaign.id = {CAMPAIGN}"""))

    total_segments = (len(IN_MARKET) + len(AFFINITY)
                      + len(LIFE_EVENTS) + len(DETAILED_DEMOGRAPHICS))
    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\nCampaign {CAMPAIGN} currently has {len(existing)} asset group signals.\n")
    print(f"NEW AUDIENCE  {AUDIENCE_NAME!r}  ({total_segments} segments, OR'd together)")
    for label, items in (("in-market", IN_MARKET), ("affinity", AFFINITY),
                         ("life event", LIFE_EVENTS),
                         ("demographic", DETAILED_DEMOGRAPHICS)):
        for _id, name in items:
            print(f"    {label:12} {_id:>6}  {name}")
    print(f"\n  -> attached as an audience signal to all {len(THEMES)} asset groups")
    for ag, themes in THEMES.items():
        print(f"\nSEARCH THEMES  {live[ag]}  ({len(themes)})")
        for t in themes:
            print(f"    {t}")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    # ---- 1. build the audience -------------------------------------------
    aud_op = client.get_type("AudienceOperation")
    aud = aud_op.create
    aud.name = AUDIENCE_NAME
    aud.description = ("In-market home and garden shoppers, homeowners, and "
                       "recent home buyers/renovators. Prospecting signal for "
                       "the feed-only PMax campaign.")
    dim = client.get_type("AudienceDimension")
    seg_dim = dim.audience_segments
    for _id, _ in IN_MARKET + AFFINITY:
        s = client.get_type("AudienceSegment")
        s.user_interest.user_interest_category = f"customers/{cust}/userInterests/{_id}"
        seg_dim.segments.append(s)
    for _id, _ in LIFE_EVENTS:
        s = client.get_type("AudienceSegment")
        s.life_event.life_event = f"customers/{cust}/lifeEvents/{_id}"
        seg_dim.segments.append(s)
    for _id, _ in DETAILED_DEMOGRAPHICS:
        s = client.get_type("AudienceSegment")
        s.detailed_demographic.detailed_demographic = (
            f"customers/{cust}/detailedDemographics/{_id}")
        seg_dim.segments.append(s)
    aud.dimensions.append(dim)

    res = client.get_service("AudienceService").mutate_audiences(
        customer_id=cust, operations=[aud_op])
    audience_rn = res.results[0].resource_name
    print(f"\n  created audience {audience_rn}")

    # ---- 2. signals: one audience + the search themes ---------------------
    ag_svc = client.get_service("AssetGroupService")
    sig_ops = []
    for ag, themes in THEMES.items():
        ag_rn = ag_svc.asset_group_path(cust, ag)

        op = client.get_type("AssetGroupSignalOperation")
        op.create.asset_group = ag_rn
        op.create.audience.audience = audience_rn
        sig_ops.append(op)

        for t in themes:
            op = client.get_type("AssetGroupSignalOperation")
            op.create.asset_group = ag_rn
            op.create.search_theme.text = t
            sig_ops.append(op)

    client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
        customer_id=cust, operations=sig_ops)
    print(f"  created {len(sig_ops)} signals "
          f"({len(THEMES)} audience + {sum(len(v) for v in THEMES.values())} search themes)")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
