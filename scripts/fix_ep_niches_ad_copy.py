"""Rewrite the EP niches-funnel ads to clear the MISLEADING_CONTENT block.

All six ads in `EP 5: Niches List Funnel` were disapproved on 13 September
with MISLEADING_CONTENT (PROHIBITED), which took the campaign to zero
servable ads and the account to ~5 impressions a day.

PROHIBITED is the strict tier: no exemption request, and the API has no
appeal. The only route back is copy Google will pass on re-review.

Every headline and description that made a claim about money or results is
gone. Removed across the shared block:

    "1,000+ Profitable Niches"        earnings claim
    "Proven High-Ticket Niches"       unsubstantiated
    "Vetted High-Ticket Niches"       implied quality guarantee
    "Niches With Real Margins"        margin claim
    "Real niches with real margins and real suppliers."
    "Built from 10 years running high-ticket stores."   also inconsistent
                                      with "Since 2015" -- that is 11 years

What replaces them describes what the list IS -- a count, a sort order, a
delivery method, a start date -- all verifiable from ecommerceparadise.com.
Two lines are lifted from the landing page itself, including the
"will not pick for you" disclaimer, so ad and destination agree.

Also fixed: the `high ticket dropshipping products` ad had H1 truncated
mid-word as "High Ticket Dropshipping Produ" because the root keyword is 33
characters against a 30-character limit.

The `profitable dropshipping niches` ad group keeps its keyword but no
longer pins "Profitable" in H1, since that is the one word in the set most
likely to have triggered the policy.

RSAs are updated in place, which sends them back through review. Run with no
flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "eCommerce Paradise"
CAMPAIGN = 24150758369

# Pinned H1 per ad group: the SKAG root keyword, within 30 chars.
PINNED = {
    198082037903: "High Ticket Dropship Products",
    198082038703: "High Ticket Niches",
    200372412458: "Dropshipping Niches",
    202064207649: "High Ticket Dropship Niches",
    205059137411: "Dropshipping Niches List",
    206141716984: "Best Dropshipping Niches",
}

SHARED_HEADLINES = [
    "1,000+ High-Ticket Niches",
    "Free High-Ticket Niche List",
    "Niches Sorted By Category",
    "Get The Free Niche List",
    "Free Niche List By Email",
    "Built For High-Ticket",
    "Skip The Niche Research",
    "High-Ticket Product Ideas",
    "Ecommerce Paradise Since 2015",
    "Sent Straight To Your Inbox",
    "Browse Niches By Vertical",
    "Not The Same 5 YouTube Ideas",
    "A Thousand Options, Not Ten",
    "Lands In Your Inbox Fast",
]

DESCRIPTIONS = [
    "1,000+ high-ticket dropshipping niches, sorted by category. Free, sent to your inbox.",
    "Not commodity junk, and not the same five ideas every YouTube video recycles.",
    "The list will not pick for you. What it does is kill the blank page.",
    "Drawn from stores I have run and stores I have built for clients since 2015.",
]

BANNED = ["profit", "proven", "margin", "guarantee", "vetted", "earn",
          "income", "rich", "make money", "roi", "returns"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    # Validate before touching anything.
    problems = []
    for h in SHARED_HEADLINES + list(PINNED.values()):
        if len(h) > 30:
            problems.append(f"headline {len(h)} chars (max 30): {h!r}")
        for b in BANNED:
            if b in h.lower():
                problems.append(f"headline contains {b!r}: {h!r}")
    for d in DESCRIPTIONS:
        if len(d) > 90:
            problems.append(f"description {len(d)} chars (max 90): {d!r}")
        for b in BANNED:
            if b in d.lower():
                problems.append(f"description contains {b!r}: {d!r}")
    if len(SHARED_HEADLINES) != 14:
        problems.append(f"need 14 shared headlines, have {len(SHARED_HEADLINES)}")
    if problems:
        print("ABORT: copy failed validation")
        for p in problems:
            print(f"   {p}")
        return 1

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    ads = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.id, ad_group.name, ad_group_ad.ad.id,
               ad_group_ad.ad.type, ad_group_ad.status,
               ad_group_ad.policy_summary.approval_status,
               ad_group_ad.ad.final_urls
        FROM ad_group_ad WHERE campaign.id = {CAMPAIGN}
          AND ad_group_ad.status = 'ENABLED' """):
        if r.ad_group_ad.ad.type_.name != "RESPONSIVE_SEARCH_AD":
            continue
        ads[r.ad_group.id] = (r.ad_group_ad.ad.id, r.ad_group.name,
                              r.ad_group_ad.policy_summary.approval_status.name,
                              list(r.ad_group_ad.ad.final_urls))

    missing = set(PINNED) - set(ads)
    if missing:
        print(f"ABORT: no enabled RSA in ad group(s) {missing}")
        return 1

    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}\n")
    print(f"{len(ads)} ads in campaign {CAMPAIGN}\n")
    print("SHARED HEADLINES (positions 2-15):")
    for h in SHARED_HEADLINES:
        print(f"   ({len(h):2}) {h}")
    print("\nDESCRIPTIONS:")
    for d in DESCRIPTIONS:
        print(f"   ({len(d):2}) {d}")
    print("\nPINNED H1 PER AD GROUP:")
    for agid, (adid, agname, status, urls) in sorted(ads.items()):
        print(f"   {agname[:38]:40} ad {adid} [{status}]")
        print(f"       H1 -> ({len(PINNED[agid]):2}) {PINNED[agid]}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to push.")
        return 0

    ops = []
    for agid, (adid, agname, status, urls) in ads.items():
        op = client.get_type("AdOperation")
        ad = op.update
        ad.resource_name = client.get_service("AdService").ad_path(cust, adid)
        h1 = client.get_type("AdTextAsset")
        h1.text = PINNED[agid]
        h1.pinned_field = e.ServedAssetFieldTypeEnum.HEADLINE_1
        ad.responsive_search_ad.headlines.append(h1)
        for t in SHARED_HEADLINES:
            a = client.get_type("AdTextAsset")
            a.text = t
            ad.responsive_search_ad.headlines.append(a)
        for t in DESCRIPTIONS:
            a = client.get_type("AdTextAsset")
            a.text = t
            ad.responsive_search_ad.descriptions.append(a)
        op.update_mask.paths.append("responsive_search_ad.headlines")
        op.update_mask.paths.append("responsive_search_ad.descriptions")
        ops.append(op)

    client.get_service("AdService").mutate_ads(customer_id=cust, operations=ops)
    print(f"\n  updated {len(ops)} ads -- they re-enter review now")

    print("\n-- verification --")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.name, ad_group_ad.ad.id,
               ad_group_ad.policy_summary.approval_status,
               ad_group_ad.policy_summary.review_status,
               ad_group_ad.ad.responsive_search_ad.headlines
        FROM ad_group_ad WHERE campaign.id = {CAMPAIGN}
          AND ad_group_ad.status = 'ENABLED' """):
        a = r.ad_group_ad
        if a.ad.responsive_search_ad.headlines:
            h1 = a.ad.responsive_search_ad.headlines[0].text
            print(f"   {r.ad_group.name[:34]:36} "
                  f"{a.policy_summary.approval_status.name:18} "
                  f"{a.policy_summary.review_status.name:18} H1={h1!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
