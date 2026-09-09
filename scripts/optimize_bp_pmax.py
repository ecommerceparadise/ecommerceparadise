"""Steer the BetterPatio PMax toward branded, commercial intent.

Two changes, both reversible:

1. BRANDED SEARCH THEMES. Each asset group carries 15 signals of a possible 25,
   and the brand coverage is thin -- Mont Alpi has 3 brand themes, Cal Flame 3,
   House Brands none at all. This tops each group up with brand-led themes so
   Google has an explicit branded signal to match rather than inferring one.

2. INFORMATIONAL NEGATIVES at campaign level. The campaign currently has ZERO
   campaign-level negative keywords -- only two shared lists, one of which
   ('EP Generic') is the cross-account list. These block the how-to / plans /
   pictures / cost-to-build intent that PMax otherwise drifts into.

Guards: a negative is skipped if an existing negative already blocks it, if it
would block one of the search themes being kept, or if it would block a search
term that has converted in the last 90 days.

NOT changed here, and deliberately so -- see the notes in the handoff:
  - the conversion goal (PURCHASE only, and purchases fire 5x/90d against 48
    lead forms) -- that is the campaign's actual problem and needs a decision
  - Final URL expansion, which is not settable in Google Ads API v25 and has to
    be switched off in the UI
  - new asset groups for the ~97% of the catalogue not covered

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys
from collections import defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
PMAX = 24209664922
MAX_SIGNALS = 25

BRAND_THEMES = {
    "BP · Mont Alpi": [
        "mont alpi", "mont alpi bbq", "mont alpi grill", "mont alpi island",
        "mont alpi outdoor kitchen island", "buy mont alpi",
        "mont alpi dealer", "mont alpi 6 burner", "mont alpi 44",
        "mont alpi grill for sale",
    ],
    "BP · Cal Flame": [
        "cal flame", "cal flame bbq", "cal flame grill",
        "cal flame outdoor kitchen island", "cal flame bbq kitchen",
        "buy cal flame", "cal flame dealer", "cal flame 4 burner",
        "cal flame island for sale", "cal flame bbq island for sale",
    ],
    "BP · BetterPatio House Brands": [
        "betterpatio", "betterpatio outdoor kitchen",
        "betterpatio designer series", "betterpatio mountain series",
        "ufinish outdoor kitchen", "unfinished bbq island",
        "bbq island kit", "outdoor kitchen frame kit",
        "unfinished outdoor kitchen frame", "diy bbq island kit",
    ],
}

# Informational / non-commercial intent. Phrase match.
INFORMATIONAL = [
    "how to build", "how to make", "how to install", "how much does it cost",
    "cost to build", "average cost", "diy plans", "free plans", "blueprints",
    "floor plans", "pictures of", "photos of", "youtube", "reddit",
    "step by step", "for beginners", "what is the best",
]


def blocks(neg_text, neg_mt, phrase):
    pt, nt = phrase.split(), neg_text.split()
    if neg_mt == "EXACT":
        return pt == nt
    if neg_mt == "PHRASE":
        return any(pt[i:i + len(nt)] == nt for i in range(len(pt) - len(nt) + 1))
    return all(w in pt for w in nt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    # --- current signals ----------------------------------------------------
    groups, current = {}, defaultdict(list)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.id, asset_group.name
        FROM asset_group WHERE campaign.id = {PMAX}
          AND asset_group.status != 'REMOVED' """):
        groups[r.asset_group.name] = r.asset_group.id
    for r in ga.search(customer_id=cust, query=f"""
        SELECT asset_group.name, asset_group_signal.search_theme.text
        FROM asset_group_signal WHERE campaign.id = {PMAX} """):
        t = r.asset_group_signal.search_theme.text
        if t:
            current[r.asset_group.name].append(t)

    unknown = set(BRAND_THEMES) - set(groups)
    if unknown:
        print(f"ABORT: asset groups not found: {unknown}")
        return 1

    # --- existing negatives + converting terms ------------------------------
    # Only sets ATTACHED to this campaign count. The account has ~20k shared
    # negatives across 20 sets, but the PMax sees just two of them -- reading
    # them all makes every term look already-blocked when it is not.
    attached = set()
    for r in ga.search(customer_id=cust, query=f"""
        SELECT shared_set.id FROM campaign_shared_set
        WHERE campaign.id = {PMAX} """):
        attached.add(r.shared_set.id)
    if not attached:
        print("ABORT: no shared negative lists attached to the PMax; "
              "expected EP Generic and BP Generic Irrelevants.")
        return 1

    existing = []
    for r in ga.search(customer_id=cust, query="""
        SELECT shared_set.id, shared_criterion.keyword.text,
               shared_criterion.keyword.match_type FROM shared_criterion """):
        if r.shared_set.id not in attached:
            continue
        k = r.shared_criterion.keyword
        existing.append((k.text, k.match_type.name))
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign_criterion.keyword.text,
               campaign_criterion.keyword.match_type
        FROM campaign_criterion WHERE campaign.id = {PMAX}
          AND campaign_criterion.type = 'KEYWORD'
          AND campaign_criterion.negative = TRUE
          AND campaign_criterion.status != 'REMOVED' """):
        k = r.campaign_criterion.keyword
        existing.append((k.text, k.match_type.name))

    converters = set()
    for r in ga.search(customer_id=cust, query="""
        SELECT search_term_view.search_term, metrics.conversions
        FROM search_term_view
        WHERE segments.date BETWEEN '2026-06-11' AND '2026-09-09' """):
        if r.metrics.conversions > 0:
            converters.add(r.search_term_view.search_term)

    keep_themes = set()
    for g in current.values():
        keep_themes.update(g)
    for v in BRAND_THEMES.values():
        keep_themes.update(v)

    # --- plan signals -------------------------------------------------------
    sig_ops, sig_plan = [], []
    svc_ag = client.get_service("AssetGroupService")
    for name, wanted in BRAND_THEMES.items():
        have = set(current.get(name, []))
        room = MAX_SIGNALS - len(have)
        add = [t for t in wanted if t not in have][:max(room, 0)]
        sig_plan.append((name, len(have), room, add))
        for t in add:
            op = client.get_type("AssetGroupSignalOperation")
            s = op.create
            s.asset_group = svc_ag.asset_group_path(cust, groups[name])
            s.search_theme.text = t
            sig_ops.append(op)

    # --- plan negatives -----------------------------------------------------
    neg_ops, neg_plan, neg_skip = [], [], []
    svc_c = client.get_service("CampaignService")
    for term in INFORMATIONAL:
        if any(blocks(n, m, term) for n, m in existing):
            neg_skip.append((term, "already blocked"))
            continue
        hit_theme = [t for t in keep_themes if blocks(term, "PHRASE", t)]
        if hit_theme:
            neg_skip.append((term, f"would block theme {hit_theme[0]!r}"))
            continue
        hit_conv = [c for c in converters if blocks(term, "PHRASE", c)]
        if hit_conv:
            neg_skip.append((term, f"would block converter {hit_conv[0]!r}"))
            continue
        op = client.get_type("CampaignCriterionOperation")
        c = op.create
        c.campaign = svc_c.campaign_path(cust, PMAX)
        c.negative = True
        c.keyword.text = term
        c.keyword.match_type = e.KeywordMatchTypeEnum.PHRASE
        neg_ops.append(op)
        neg_plan.append(term)

    # --- report -------------------------------------------------------------
    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print("BRANDED SEARCH THEMES")
    for name, have, room, add in sig_plan:
        print(f"  {name}: {have} signals now, room for {room}, adding {len(add)}")
        for t in add:
            print(f"      + {t}")
    print(f"\nINFORMATIONAL NEGATIVES (campaign level, phrase): {len(neg_plan)}")
    for t in neg_plan:
        print(f"      + {t}")
    if neg_skip:
        print(f"  skipped {len(neg_skip)}:")
        for t, why in neg_skip:
            print(f"      {t!r}: {why}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to push.")
        return 0

    if sig_ops:
        client.get_service("AssetGroupSignalService").mutate_asset_group_signals(
            customer_id=cust, operations=sig_ops)
        print(f"\n  added {len(sig_ops)} search themes")
    if neg_ops:
        client.get_service("CampaignCriterionService").mutate_campaign_criteria(
            customer_id=cust, operations=neg_ops)
        print(f"  added {len(neg_ops)} campaign-level negatives")
    return 0


if __name__ == "__main__":
    sys.exit(main())
