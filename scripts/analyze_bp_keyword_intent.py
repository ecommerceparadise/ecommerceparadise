"""Read-only: split BetterPatio Search keyword conversions by conversion ACTION.

The question this answers: the keywords we call "proven" were proven against
Zoho CRM Leads/Contacts -- a raw lead upload. That measures form fills, not
buying. Zoho CRM Lead Qualification and Zoho CRM Sales are the actions that
say a lead was worth something. Splitting by action shows which keywords ever
produced a QUALIFIED lead, and which only ever produced form fills.
"""
import sys
from collections import defaultdict
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 23303878302

Q = """
SELECT
  ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type,
  segments.conversion_action_name,
  metrics.all_conversions,
  metrics.conversions
FROM keyword_view
WHERE campaign.id = {cid}
  AND segments.date BETWEEN '2019-01-01' AND '2026-09-03'
  AND metrics.all_conversions > 0
"""

def main():
    client = get_client()
    cust = resolve_account("BetterPatio.com")["id"]
    ga = client.get_service("GoogleAdsService")
    rows = ga.search(customer_id=cust, query=Q.format(cid=CAMPAIGN))

    by_kw = defaultdict(lambda: defaultdict(float))
    for r in rows:
        kw = r.ad_group_criterion.keyword.text
        act = r.segments.conversion_action_name
        by_kw[kw][act] += r.metrics.all_conversions

    actions = sorted({a for d in by_kw.values() for a in d})
    print("Conversion actions seen:", actions, "\n")

    # rank by total
    ranked = sorted(by_kw.items(), key=lambda kv: -sum(kv[1].values()))
    print(f"{'keyword':40} {'total':>8}  breakdown")
    for kw, d in ranked:
        tot = sum(d.values())
        parts = ", ".join(f"{a}={v:.0f}" for a, v in sorted(d.items(), key=lambda x: -x[1]))
        print(f"{kw[:40]:40} {tot:8.0f}  {parts}")

if __name__ == "__main__":
    sys.exit(main())
