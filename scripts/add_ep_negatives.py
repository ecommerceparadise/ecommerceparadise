"""Add negatives to eCommerce Paradise for the traffic still leaking through.

Context. EP 5: Niches List Funnel is the only Search campaign spending: $5/day,
fully consumed, ~4 clicks a day, and ZERO conversions for 19 straight days.
The funnel sells a HIGH-TICKET niche list. The search terms it buys are
overwhelmingly low-ticket product research -- people hunting individual winning
products to dropship, which is the AliExpress end of the market, not someone
choosing a high-ticket niche to build a store around.

Not re-added: sellvia, spocket, salehoo, oberlo, zendrop, autods and the rest
are already PHRASE negatives in EP Offers Universal Negatives. Their spend
($10.00 and $7.85) dates from 8-9 August, before that list was applied to the
campaign on 27 August. Those negatives are working.

Every candidate below is checked twice: against the negatives already in force,
and against the campaign's 12 enabled keywords using word-boundary matching, so
nothing added here can switch off a keyword Trevor is deliberately buying.
Notably 'high ticket dropshipping products' is a live keyword, so no bare
'products' negative is possible.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys
from collections import defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

TARGET_LIST = 12164101696       # EP Offers Universal Negatives
CAMPAIGN = 24150758369

# (text, match type, why)
CANDIDATES = [
    # Low-ticket product hunting -- wrong end of the market for a high-ticket list
    ("winning products",             "PHRASE", "AliExpress-style product hunting"),
    ("trending",                     "PHRASE", "trend-chasing, not niche selection"),
    ("top 10",                       "PHRASE", "listicle browsing"),
    ("top selling",                  "PHRASE", "listicle browsing"),
    ("best products to dropship",    "PHRASE", "product research, not niche research"),
    ("best products for dropshipping","PHRASE", "product research"),
    ("best dropshipping products",   "PHRASE", "product research"),
    ("products to dropship",         "PHRASE", "product research"),
    ("items to dropship",            "PHRASE", "product research"),
    ("best items to drop",           "PHRASE", "product research"),
    ("product ideas",                "PHRASE", "idea browsing"),
    ("dropship ideas",               "PHRASE", "idea browsing"),
    ("business ideas",               "PHRASE", "idea browsing"),
    ("good ideas for",               "PHRASE", "idea browsing"),
    ("most profitable dropshipping products", "PHRASE", "product research"),
    # Wrong product category -- EP is high ticket, not apparel
    ("fashion",                      "PHRASE", "low-ticket apparel"),
    # Supplier platforms not already blocked
    ("doba",                         "PHRASE", "competitor platform"),
    ("cjdropshipping",               "PHRASE", "competitor platform"),
    ("cj dropshipping",              "PHRASE", "competitor platform"),
    ("printful",                     "PHRASE", "print on demand, wrong model"),
    ("printify",                     "PHRASE", "print on demand, wrong model"),
    ("dhgate",                       "PHRASE", "low-ticket marketplace"),
    ("wholesale2b",                  "PHRASE", "competitor platform"),
    ("inventory source",             "PHRASE", "competitor platform"),
    ("modalyst",                     "PHRASE", "competitor platform"),
    ("syncee",                       "PHRASE", "competitor platform"),
    ("trendsi",                      "PHRASE", "competitor platform"),
    ("spark shipping",               "PHRASE", "competitor platform"),
    ("dropified",                    "PHRASE", "competitor platform"),
    ("importify",                    "PHRASE", "competitor platform"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("eCommerce Paradise")["id"]
    ga = client.get_service("GoogleAdsService")

    # Negatives already in force on this campaign.
    lists = [r.shared_set.id for r in ga.search(customer_id=cust, query=f"""
        SELECT shared_set.id FROM campaign_shared_set
        WHERE campaign.id = {CAMPAIGN} AND campaign_shared_set.status != 'REMOVED'""")]
    existing = set()
    for sid in lists:
        for r in ga.search(customer_id=cust, query=f"""
            SELECT shared_criterion.keyword.text, shared_criterion.keyword.match_type
            FROM shared_criterion WHERE shared_set.id = {sid}"""):
            k = r.shared_criterion.keyword
            existing.add((k.text.lower(), k.match_type.name))
    in_target = {t for t, _ in existing}

    # Keywords the campaign is deliberately buying -- must survive.
    keywords = [(r.ad_group_criterion.keyword.text.lower(),
                 r.ad_group_criterion.keyword.match_type.name)
                for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type
        FROM ad_group_criterion WHERE campaign.id = {CAMPAIGN}
          AND ad_group_criterion.type = 'KEYWORD'
          AND ad_group_criterion.negative = FALSE
          AND ad_group_criterion.status = 'ENABLED'""")]

    def blocks(neg_text, neg_mt, kw_text):
        """Word-boundary match: would this negative switch off that keyword?"""
        kt, nt = kw_text.split(), neg_text.split()
        if neg_mt == "EXACT":
            return kt == nt
        if neg_mt == "PHRASE":
            return any(kt[i:i+len(nt)] == nt for i in range(len(kt)-len(nt)+1))
        return all(w in kt for w in nt)

    # 30-day search term spend, to price what each negative would have saved.
    terms = [(r.search_term_view.search_term.lower(), r.metrics.cost_micros/1e6,
              r.metrics.clicks, r.metrics.all_conversions)
             for r in ga.search(customer_id=cust, query="""
        SELECT search_term_view.search_term, metrics.cost_micros, metrics.clicks,
               metrics.all_conversions
        FROM search_term_view WHERE segments.date DURING LAST_30_DAYS""")]

    add, skipped = [], []
    for text, mt, why in CANDIDATES:
        if text in in_target:
            skipped.append((text, "already blocked"))
            continue
        clash = next((k for k, _ in keywords if blocks(text, mt, k)), None)
        if clash:
            skipped.append((text, f"would block live keyword {clash!r}"))
            continue
        saved = sum(c for t, c, _, _ in terms if blocks(text, mt, t))
        hits = [t for t, _, _, _ in terms if blocks(text, mt, t)]
        conv = sum(cv for t, _, _, cv in terms if blocks(text, mt, t))
        if conv > 0:
            skipped.append((text, f"blocks {conv:.0f} converting term(s) -- kept"))
            continue
        add.append((text, mt, why, saved, len(hits)))

    print("=" * 78)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 78)
    print(f"\nTarget list: EP Offers Universal Negatives ({TARGET_LIST})")
    print(f"Negatives already in force on the campaign: {len(existing)}")
    print(f"\nADD {len(add)}:")
    print(f"  {'term':40} {'mt':7} {'30d saved':>10} {'terms':>6}  why")
    total = 0.0
    for t, mt, why, saved, n in sorted(add, key=lambda x: -x[3]):
        total += saved
        print(f"  {t:40} {mt:7} {saved:>10.2f} {n:>6}  {why}")
    print(f"  {'':40} {'':7} {total:>10.2f}  <- would have prevented in the last 30 days")
    print(f"\nSKIPPED {len(skipped)}:")
    for t, why in skipped:
        print(f"  {t:40} {why}")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    svc = client.get_service("SharedCriterionService")
    ops = []
    for text, mt, _why, _s, _n in add:
        op = client.get_type("SharedCriterionOperation")
        c = op.create
        c.shared_set = client.get_service("SharedSetService").shared_set_path(
            cust, TARGET_LIST)
        c.keyword.text = text
        c.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, mt)
        ops.append(op)
    if ops:
        svc.mutate_shared_criteria(customer_id=cust, operations=ops)
    print(f"\n  added {len(ops)} negatives")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT shared_set.name, shared_set.member_count FROM shared_set
        WHERE shared_set.id = {TARGET_LIST}"""):
        print(f"  {r.shared_set.name} now has {r.shared_set.member_count} members")
    return 0


if __name__ == "__main__":
    sys.exit(main())
