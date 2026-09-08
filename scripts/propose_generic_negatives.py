"""Find genuinely irrelevant search terms per account and propose negatives.

Writes to each account's OWN generic list, never to 'EP Generic' [11765673294],
which is the SAME shared list in all five accounts (verified: identical id and
member count in every one, attached to 14 enabled campaigns across every
client). Adding there would hit every client at once -- that is how EP's
dropshipping negatives ended up blocking BetterPatio's converting kitchen terms.

Three guards before anything is proposed:
  1. skip if an existing negative already blocks the term (word-boundary match)
  2. skip if the negative would block a term that HAS converted in 90 days
  3. skip if it would block a live enabled keyword in the account

Run with no flags for the proposal. Pass --execute to write.
"""
import argparse
import re
import sys
from collections import defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

WINDOW = ("2026-08-09", "2026-09-08")
CONV_WINDOW = ("2026-06-10", "2026-09-08")

# Target list per account -- each verified account-specific and attached to the
# account's live campaigns.
TARGETS = {
    "BetterPatio.com":      (12052054569, "BP Generic Irrelevants"),
    "Laser Engraver Store": (12165888848, "LES Universal Negatives"),
    "eCommerce Paradise":   (12164101696, "EP Offers Universal Negatives"),
}

# Signals of intent this business can never serve. Deliberately conservative:
# on-catalog product and brand queries are NOT junk just because they have not
# converted yet.
JUNK = {
    "job / career":     r"\b(job|jobs|career|careers|salary|hiring|apprentice)\b",
    "repair / service": r"\b(repair|repairs|fixing|replacement part|parts only|servicing)\b",
    "used / rental":    r"\b(used|second hand|rental|rent|hire|refurbished|craigslist)\b",
    "free / cheap":     r"\b(free|cheapest|under \$?\d+|dollar|clearance only)\b",
    "diy plans":        r"\b(plans|blueprint|blueprints|schematic|pdf|diy kit)\b",
    "big-box retailer": r"\b(home depot|lowes|lowe's|costco|wayfair|amazon|walmart|ikea|"
                        r"sam's club|menards|harbor freight)\b",
    "non-english":      r"[àáâãäçèéêëìíîïñòóôõöùúûüßœ]|"
                        r"\b(para|comprar|precio|barato|maquina|gravadora|portátil)\b",
    "course / how-to":  r"\b(how to build|how to make|tutorial|course|training|"
                        r"youtube|reddit|forum)\b",
}


def blocks(neg_text, neg_mt, term):
    tt, nt = term.split(), neg_text.split()
    if neg_mt == "EXACT":
        return tt == nt
    if neg_mt == "PHRASE":
        return any(tt[i:i + len(nt)] == nt for i in range(len(tt) - len(nt) + 1))
    return all(w in tt for w in nt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    ga = client.get_service("GoogleAdsService")
    total_add = 0

    for account, (sid, label) in TARGETS.items():
        cust = resolve_account(account)["id"]
        print("=" * 70)
        print(f"{account}  ->  {label} [{sid}]")
        print("=" * 70)

        # existing negatives anywhere in the account
        existing = []
        for r in ga.search(customer_id=cust, query="""
            SELECT shared_criterion.keyword.text,
                   shared_criterion.keyword.match_type, shared_set.id
            FROM shared_criterion """):
            k = r.shared_criterion.keyword
            existing.append((k.text, k.match_type.name))
        for r in ga.search(customer_id=cust, query="""
            SELECT campaign_criterion.keyword.text,
                   campaign_criterion.keyword.match_type
            FROM campaign_criterion
            WHERE campaign_criterion.type = 'KEYWORD'
              AND campaign_criterion.negative = TRUE
              AND campaign_criterion.status != 'REMOVED' """):
            k = r.campaign_criterion.keyword
            existing.append((k.text, k.match_type.name))

        # terms that have converted -- never block these
        converters = set()
        for r in ga.search(customer_id=cust, query=f"""
            SELECT search_term_view.search_term, metrics.conversions
            FROM search_term_view
            WHERE segments.date BETWEEN '{CONV_WINDOW[0]}' AND '{CONV_WINDOW[1]}' """):
            if r.metrics.conversions > 0:
                converters.add(r.search_term_view.search_term)

        # live enabled keywords -- never block these either
        live_kw = set()
        for r in ga.search(customer_id=cust, query="""
            SELECT ad_group_criterion.keyword.text
            FROM ad_group_criterion
            WHERE ad_group_criterion.type = 'KEYWORD'
              AND ad_group_criterion.negative = FALSE
              AND ad_group_criterion.status = 'ENABLED' """):
            live_kw.add(r.ad_group_criterion.keyword.text)

        # non-converting spend
        terms = defaultdict(lambda: [0.0, 0, 0.0])
        for r in ga.search(customer_id=cust, query=f"""
            SELECT search_term_view.search_term, metrics.cost_micros,
                   metrics.clicks, metrics.conversions
            FROM search_term_view
            WHERE segments.date BETWEEN '{WINDOW[0]}' AND '{WINDOW[1]}' """):
            a = terms[r.search_term_view.search_term]
            a[0] += r.metrics.cost_micros / 1e6
            a[1] += r.metrics.clicks
            a[2] += r.metrics.conversions

        proposals, skipped = [], []
        for term, (cost, clicks, conv) in sorted(terms.items(), key=lambda kv: -kv[1][0]):
            if conv > 0 or cost <= 0:
                continue
            cat = next((c for c, rx in JUNK.items()
                        if re.search(rx, term, re.I)), None)
            if not cat:
                continue
            if any(blocks(n, m, term) for n, m in existing):
                skipped.append((term, "already blocked"))
                continue
            # propose the term itself as a PHRASE negative
            bad_conv = [c for c in converters if blocks(term, "PHRASE", c)]
            if bad_conv:
                skipped.append((term, f"would block converter {bad_conv[0]!r}"))
                continue
            bad_kw = [k for k in live_kw if blocks(term, "PHRASE", k)]
            if bad_kw:
                skipped.append((term, f"would block live keyword {bad_kw[0]!r}"))
                continue
            proposals.append((cost, clicks, term, cat))

        spend = sum(p[0] for p in proposals)
        print(f"  {len(terms)} terms in window; {len(proposals)} proposed as "
              f"negatives, ${spend:.2f}/30d")
        for cost, clicks, term, cat in proposals:
            print(f"    ${cost:6.2f} {int(clicks):3}c  [{cat:16}] {term}")
        if skipped:
            print(f"  {len(skipped)} candidates skipped by the guards:")
            for term, why in skipped[:8]:
                print(f"    {term!r}: {why}")

        if not proposals:
            print("  nothing to add.\n")
            continue
        total_add += len(proposals)

        if args.execute:
            ops = []
            svc = client.get_service("SharedCriterionService")
            for _, _, term, _ in proposals:
                op = client.get_type("SharedCriterionOperation")
                c = op.create
                c.shared_set = client.get_service("SharedSetService").shared_set_path(
                    cust, sid)
                c.keyword.text = term
                c.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
                ops.append(op)
            svc.mutate_shared_criteria(customer_id=cust, operations=ops)
            print(f"  ADDED {len(ops)} negatives to {label}\n")
        else:
            print()

    print(f"{'ADDED' if args.execute else 'WOULD ADD'} {total_add} negatives total")
    if not args.execute:
        print("Dry run. Re-run with --execute to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
