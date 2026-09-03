"""Split the BetterPatio Search campaign into four intent themes, each with a
full 15-headline responsive search ad.

Why: ad group 190077137940 held all 36 keywords and served ONE ad with three
headlines (POOR strength). Quality Score data showed ad relevance BELOW AVERAGE
on exactly the keywords whose intent did not match that ad's copy, while the
core "custom outdoor kitchen" terms scored ABOVE AVERAGE. The fix is Trevor's
own rule: search term = ad headline = landing page headline.

What this does:
  * Leaves the proven ad group and its 12 core keywords alone, and ADDS a
    15-headline RSA next to the existing 3-headline ad so the two split-test.
    The old ad keeps running -- no serving gap, no lost history.
  * Creates three new ad groups, moves the off-theme keywords into them
    (paused in the old group, added to the new one), and gives each its own
    15-headline RSA written to that theme.

Every headline and description reuses a claim already live in this account's
existing ads. Nothing here invents an offer.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 23303878302
CORE_AD_GROUP = 190077137940
LANDING = "https://betterpatio.com/pages/custom-outdoor-kitchens"

HEADLINE_MAX, DESCRIPTION_MAX, PATH_MAX = 30, 90, 15

# Descriptions shared across themes -- all four are claims already in use.
COMMON_DESCRIPTIONS = [
    "Built to your exact specifications with premium materials and expert craftsmanship.",
    "Free design consultation with a real outdoor kitchen specialist. No obligation.",
    "Financing available on qualifying orders. Ships free to the lower 48.",
    "Tell us what you want to build and we will price it out at no cost.",
]

# theme key -> (ad group name, path1, path2, pinned root headline, other headlines,
#               descriptions, keywords as (text, match_type))
THEMES = {
    "core": {
        "ad_group_id": CORE_AD_GROUP,
        "name": "Build Your Own Outdoor Kitchen",
        "path1": "Outdoor", "path2": "Kitchens",
        "root": "Custom Outdoor Kitchens",
        "headlines": [
            "Build Your Outdoor Kitchen",
            "Made To Your Exact Specs",
            "Free 3D Kitchen Rendering",
            "Free Design Consultation",
            "Complete Outdoor Kitchens",
            "Ships Pre-Assembled",
            "Free Shipping Lower 48",
            "Authorized Dealer",
            "Financing Available",
            "Industry-Leading Warranty",
            "Talk To A Kitchen Expert",
            "Made In The USA",
            "No Cost, No Obligation",
            "Get Your Free Quote Today",
        ],
        "keywords": [],  # keeps what it has
    },
    "design": {
        "ad_group_id": None,
        "name": "Design Your Own | 3D Rendering",
        "path1": "Design", "path2": "Your-Kitchen",
        "root": "Design Your Own Kitchen",
        "headlines": [
            "Free 3D Kitchen Rendering",
            "See It Before You Build",
            "Outdoor Kitchen Designers",
            "Design Your Outdoor Kitchen",
            "Free Design Consultation",
            "Your Layout, Your Grill",
            "No Cost, No Obligation",
            "Backyard Designers On Call",
            "Get Your Free Rendering",
            "Built To Your Exact Specs",
            "Talk To A Kitchen Expert",
            "Financing Available",
            "Free Shipping Lower 48",
            "Start Your Design Today",
        ],
        "keywords": [
            ("design my kitchen", "EXACT"),
            ("design my outdoor kitchen", "EXACT"),
            ("design your own kitchen", "EXACT"),
            ("design your own outdoor kitchen", "EXACT"),
            ("3d kitchen design", "EXACT"),
            ("outdoor kitchen designers", "EXACT"),
            ("outdoor spaces design", "EXACT"),
            ("outdoor kitchen design", "PHRASE"),
            ("outdoor kitchen designs", "PHRASE"),
            ("backyard kitchen ideas", "PHRASE"),
        ],
    },
    "islands": {
        "ad_group_id": None,
        "name": "BBQ & Grill Islands",
        "path1": "BBQ", "path2": "Grill-Islands",
        "root": "Custom BBQ Grill Islands",
        "headlines": [
            "Built-In Grills & Islands",
            "Modular Outdoor Kitchens",
            "Design Your Grill Island",
            "Ships Pre-Assembled",
            "Customizable Grill Islands",
            "Blaze, Bull & Cal Flame",
            "Coyote, RCS & Summerset",
            "Free Shipping Lower 48",
            "Authorized Dealer",
            "Made To Your Exact Specs",
            "Financing Available",
            "Industry-Leading Warranty",
            "Free 3D Kitchen Rendering",
            "Get Your Free Quote Today",
        ],
        "keywords": [
            ("custom bbq island", "EXACT"),
            ("custom bbq islands near me", "EXACT"),
            ("custom grill island", "EXACT"),
            ("custom outdoor bbq grills", "EXACT"),
            ("custom outdoor grill", "EXACT"),
            ("custom outdoor grill islands", "EXACT"),
            ("custom outdoor grill station", "EXACT"),
            ("custom outdoor kitchen islands", "EXACT"),
            ("modular outdoor kitchen", "EXACT"),
            ("outdoor grill island", "PHRASE"),
            ("pre built outdoor kitchen islands", "PHRASE"),
        ],
    },
    "builders": {
        "ad_group_id": None,
        "name": "Builders & Contractors",
        "path1": "Outdoor", "path2": "Kitchen-Build",
        "root": "Outdoor Kitchen Builders",
        "headlines": [
            "Built To Your Exact Specs",
            "Free Quote In 1 Day",
            "Talk To A Kitchen Expert",
            "Speak To A Real Person",
            "PO-Friendly For Pros",
            "Made To Order Kitchens",
            "Free Design Consultation",
            "Ships Pre-Assembled",
            "Free Shipping Lower 48",
            "Authorized Dealer",
            "Financing Available",
            "Made In The USA",
            "Start Your Project Today",
            "Get Your Free Quote Today",
        ],
        "keywords": [
            ("outdoor kitchen builders near me", "EXACT"),
            ("outdoor kitchen contractors near me", "EXACT"),
            ("outdoor kitchen companies near me", "PHRASE"),
        ],
    },
}


def validate():
    """Fail before touching the API if any asset would be rejected on length."""
    problems = []
    for key, t in THEMES.items():
        heads = [t["root"]] + t["headlines"]
        if len(heads) != 15:
            problems.append(f"{key}: {len(heads)} headlines, want 15")
        for h in heads:
            if len(h) > HEADLINE_MAX:
                problems.append(f"{key}: headline {len(h)}>{HEADLINE_MAX}: {h!r}")
        for p in (t["path1"], t["path2"]):
            if len(p) > PATH_MAX:
                problems.append(f"{key}: path {len(p)}>{PATH_MAX}: {p!r}")
    for d in COMMON_DESCRIPTIONS:
        if len(d) > DESCRIPTION_MAX:
            problems.append(f"description {len(d)}>{DESCRIPTION_MAX}: {d!r}")
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print("  " + p)
        sys.exit(1)


def build_rsa(client, ad_group_rn, theme):
    """An RSA with the theme's root keyword pinned to headline position 1."""
    op = client.get_type("AdGroupAdOperation")
    ada = op.create
    ada.ad_group = ad_group_rn
    ada.status = client.enums.AdGroupAdStatusEnum.ENABLED
    ad = ada.ad
    ad.final_urls.append(LANDING)
    rsa = ad.responsive_search_ad
    rsa.path1, rsa.path2 = theme["path1"], theme["path2"]

    root = client.get_type("AdTextAsset")
    root.text = theme["root"]
    root.pinned_field = client.enums.ServedAssetFieldTypeEnum.HEADLINE_1
    rsa.headlines.append(root)
    for h in theme["headlines"]:
        a = client.get_type("AdTextAsset")
        a.text = h
        rsa.headlines.append(a)
    for d in COMMON_DESCRIPTIONS:
        a = client.get_type("AdTextAsset")
        a.text = d
        rsa.descriptions.append(a)
    return op


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    validate()
    client = get_client()
    cust = resolve_account("BetterPatio.com")["id"]
    ga = client.get_service("GoogleAdsService")

    # Map the live keywords so we only pause what actually exists and is enabled.
    q = f"""
      SELECT ad_group_criterion.resource_name, ad_group_criterion.keyword.text,
             ad_group_criterion.keyword.match_type
      FROM ad_group_criterion
      WHERE ad_group.id = {CORE_AD_GROUP}
        AND ad_group_criterion.type = 'KEYWORD'
        AND ad_group_criterion.negative = FALSE
        AND ad_group_criterion.status = 'ENABLED'
    """
    live = {}
    for r in ga.search(customer_id=cust, query=q):
        c = r.ad_group_criterion
        live[(c.keyword.text, c.keyword.match_type.name)] = c.resource_name

    moving = [(k, THEMES[t]["name"]) for t in ("design", "islands", "builders")
              for k in THEMES[t]["keywords"]]
    missing = [k for k, _ in moving if k not in live]

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\nAd group {CORE_AD_GROUP} 'Build Your Own Outdoor Kitchen' (existing)")
    print(f"  + 1 new RSA (15 headlines, 4 descriptions), root pinned to H1")
    print(f"    existing 3-headline ad 786072183293 stays ENABLED as the control")
    print(f"  - pause {len([k for k, _ in moving if k in live])} keywords moving to new groups")
    print(f"  = keeps {len(live) - len([k for k, _ in moving if k in live])} core keywords")
    for t in ("design", "islands", "builders"):
        th = THEMES[t]
        print(f"\nNEW ad group '{th['name']}'  [ENABLED]")
        print(f"  + 1 RSA, root pinned: {th['root']!r} -> {LANDING}")
        print(f"  + {len(th['keywords'])} keywords:")
        for text, mt in th["keywords"]:
            mark = " " if (text, mt) in live else "  (NOT in core group -- will be added fresh)"
            print(f"      {text} [{mt}]{mark}")
    if missing:
        print(f"\nNOTE: {len(missing)} keyword(s) not found enabled in the core group; "
              f"they will simply be created in the new group.")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    # ---- 1. create the three new ad groups -------------------------------
    ag_svc = client.get_service("AdGroupService")
    ag_ops = []
    order = ["design", "islands", "builders"]
    for t in order:
        op = client.get_type("AdGroupOperation")
        ag = op.create
        ag.name = THEMES[t]["name"]
        ag.campaign = client.get_service("CampaignService").campaign_path(cust, CAMPAIGN)
        ag.status = client.enums.AdGroupStatusEnum.ENABLED
        ag.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
        ag_ops.append(op)
    res = ag_svc.mutate_ad_groups(customer_id=cust, operations=ag_ops)
    for t, r in zip(order, res.results):
        THEMES[t]["ad_group_rn"] = r.resource_name
        print(f"  created ad group {THEMES[t]['name']!r}: {r.resource_name}")

    # ---- 2. add keywords to the new ad groups ----------------------------
    crit_svc = client.get_service("AdGroupCriterionService")
    kw_ops = []
    for t in order:
        for text, mt in THEMES[t]["keywords"]:
            op = client.get_type("AdGroupCriterionOperation")
            c = op.create
            c.ad_group = THEMES[t]["ad_group_rn"]
            c.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
            c.keyword.text = text
            c.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, mt)
            kw_ops.append(op)
    crit_svc.mutate_ad_group_criteria(customer_id=cust, operations=kw_ops)
    print(f"  added {len(kw_ops)} keywords to the new ad groups")

    # ---- 3. pause the moved keywords in the core ad group ----------------
    pause_ops = []
    for k, _ in moving:
        rn = live.get(k)
        if not rn:
            continue
        op = client.get_type("AdGroupCriterionOperation")
        op.update.resource_name = rn
        op.update.status = client.enums.AdGroupCriterionStatusEnum.PAUSED
        op.update_mask.paths.append("status")
        pause_ops.append(op)
    if pause_ops:
        crit_svc.mutate_ad_group_criteria(customer_id=cust, operations=pause_ops)
    print(f"  paused {len(pause_ops)} moved keywords in the core ad group")

    # ---- 4. one RSA per ad group (core included) -------------------------
    ad_svc = client.get_service("AdGroupAdService")
    ad_ops = [build_rsa(
        client,
        client.get_service("AdGroupService").ad_group_path(cust, CORE_AD_GROUP),
        THEMES["core"])]
    for t in order:
        ad_ops.append(build_rsa(client, THEMES[t]["ad_group_rn"], THEMES[t]))
    res = ad_svc.mutate_ad_group_ads(customer_id=cust, operations=ad_ops)
    for r in res.results:
        print(f"  created ad {r.resource_name}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
