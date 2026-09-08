"""Read-only spot check across every managed account.

Produces the numbers behind a client update -- 7-day and 30-day spend, clicks,
conversions and CPA per account and per active campaign -- plus the search terms
that are burning money without converting, which is the input to the negative
keyword pass.

Google Ads only. The full weekly-ad-report deliverable also needs Shopify and
Microsoft Advertising exports, which are not reachable from here.
"""
import json
import sys
from collections import defaultdict

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

D7 = ("2026-09-01", "2026-09-08")
D30 = ("2026-08-09", "2026-09-08")


def totals(ga, cust, start, end):
    t = defaultdict(float)
    for r in ga.search(customer_id=cust, query=f"""
        SELECT metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.conversions_value
        FROM customer
        WHERE segments.date BETWEEN '{start}' AND '{end}' """):
        m = r.metrics
        t["imp"] += m.impressions
        t["clicks"] += m.clicks
        t["cost"] += m.cost_micros / 1e6
        t["conv"] += m.conversions
        t["value"] += m.conversions_value
    return t


def main():
    accounts = json.load(open("managed_accounts.json"))["accounts"]
    client = get_client()
    ga = client.get_service("GoogleAdsService")

    for acct in accounts:
        name, cust = acct["name"], acct["id"]
        print("=" * 72)
        print(f"{name}  ({cust})")
        print("=" * 72)

        for label, (s, e) in (("7d ", D7), ("30d", D30)):
            t = totals(ga, cust, s, e)
            cpa = t["cost"] / t["conv"] if t["conv"] else 0
            cpc = t["cost"] / t["clicks"] if t["clicks"] else 0
            roas = t["value"] / t["cost"] if t["cost"] else 0
            print(f"  {label}  ${t['cost']:9,.2f}  {int(t['clicks']):5} clicks  "
                  f"{int(t['imp']):7,} imp  {t['conv']:6.1f} conv  "
                  f"CPA ${cpa:7.2f}  CPC ${cpc:5.2f}  "
                  f"value ${t['value']:,.2f}  ROAS {roas:.2f}")

        print("\n  active campaigns (30d):")
        rows = []
        for r in ga.search(customer_id=cust, query=f"""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.advertising_channel_type,
                   campaign.bidding_strategy_type,
                   campaign_budget.amount_micros,
                   metrics.cost_micros, metrics.clicks, metrics.conversions
            FROM campaign
            WHERE campaign.status = 'ENABLED'
              AND segments.date BETWEEN '{D30[0]}' AND '{D30[1]}' """):
            c, m = r.campaign, r.metrics
            rows.append((m.cost_micros / 1e6, c.name, c.id,
                         c.advertising_channel_type.name,
                         c.bidding_strategy_type.name,
                         r.campaign_budget.amount_micros / 1e6,
                         m.clicks, m.conversions))
        if not rows:
            print("    (no enabled campaigns with data)")
        for cost, cname, cid, chan, bid, bud, clicks, conv in sorted(
                rows, reverse=True):
            cpa = cost / conv if conv else 0
            print(f"    ${cost:8,.2f}  {int(clicks):4} clk  {conv:5.1f} conv  "
                  f"CPA ${cpa:7.2f}  ${bud:6.2f}/day  {chan[:12]:12} {bid[:22]:22} {cname}")

        # --- money going to non-converting search terms ---------------------
        print("\n  top non-converting search terms (30d):")
        terms = defaultdict(lambda: [0.0, 0, 0.0])
        for r in ga.search(customer_id=cust, query=f"""
            SELECT search_term_view.search_term, metrics.cost_micros,
                   metrics.clicks, metrics.conversions
            FROM search_term_view
            WHERE segments.date BETWEEN '{D30[0]}' AND '{D30[1]}' """):
            a = terms[r.search_term_view.search_term]
            a[0] += r.metrics.cost_micros / 1e6
            a[1] += r.metrics.clicks
            a[2] += r.metrics.conversions
        dead = {t: v for t, v in terms.items() if v[2] == 0 and v[0] > 0}
        waste = sum(v[0] for v in dead.values())
        print(f"    {len(terms)} terms, {len(dead)} with spend and no conversion, "
              f"${waste:,.2f} total")
        for t, (cost, clicks, _) in sorted(dead.items(), key=lambda kv: -kv[1][0])[:20]:
            print(f"    ${cost:7.2f}  {int(clicks):3} clk  {t}")

        # --- the account's negative lists ------------------------------------
        print("\n  negative keyword lists:")
        for r in ga.search(customer_id=cust, query="""
            SELECT shared_set.id, shared_set.name, shared_set.member_count
            FROM shared_set
            WHERE shared_set.type = 'NEGATIVE_KEYWORDS'
              AND shared_set.status != 'REMOVED'
            ORDER BY shared_set.member_count DESC """):
            s = r.shared_set
            print(f"    [{s.id}] {s.name}  ({s.member_count} members)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
