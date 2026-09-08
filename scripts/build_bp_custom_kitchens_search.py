"""Build a clean SKAG Search campaign for the BetterPatio custom-kitchen LP.

The existing 'Build Your Own Outdoor Kitchen Campaign' [23303878302] stopped
serving: Maximize Conversions carrying a $233.42 target CPA with zero
conversions in 14 days, so Google will not bid. It also carries years of
accumulated cruft -- 224 ad-group negatives on each of 5 ad groups, 7
campaign-level user lists, a 24-row ad schedule, a 321-member shared negative
list from another funnel, and 29 paused keywords.

Rather than untangle that, this builds fresh, on evidence. Keyword selection is
taken from the last 90 days of that campaign's own keyword_view data:

     conv  clicks     CPA  keyword
      5.0      55     $61  custom outdoor kitchen
      3.0      15     $21  custom outdoor kitchen design
      3.0      13     $19  design my outdoor kitchen        (currently paused)
      2.0      31     $54  complete outdoor kitchen
      2.0       9     $32  outdoor kitchen designers        (currently paused)
      1.0       4     $27  custom built outdoor kitchen
      1.0       3     $21  outdoor kitchen builders near me (currently paused)

Deliberately excluded: 'outdoor kitchens for sale' ($350 CPA), 'modular outdoor
kitchen' ($280) and 'design your own outdoor kitchen' ($275) all converted but
above any sane target, and 'build your own outdoor kitchen' spent $570 across
broad and phrase for zero conversions.

Three deliberate departures from the old campaign:

  - MANUAL CPC, not Maximize Conversions. A new campaign has no conversion
    history, and an auto-bidder with nothing to learn from is exactly what
    stopped the last one. Bids come from each keyword's own historical CPC.
  - Google Search only. No search partners, no display expansion.
  - No sitelinks, and the EP Generic shared list is NOT attached. Every click
    goes to the landing page and nowhere else.

Geo and language are copied from the old campaign so targeting is unchanged.

Created PAUSED. Run with no flags for a dry run (validate_only); --execute to
push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
SOURCE_CAMPAIGN = 23303878302
LANDING = "https://betterpatio.com/pages/custom-outdoor-kitchens"
CAMPAIGN_NAME = "BP | Search | Custom Kitchens LP"
DAILY_BUDGET = 65.00

# (root keyword, max cpc, pinned headline) -- cpc from that keyword's own
# 90-day average, rounded and capped at $5.00 so no single term runs away on
# manual bidding. The pinned headline is the root keyword unless it exceeds the
# 30-character headline limit, in which case it is shortened by hand rather
# than truncated mid-word.
SKAGS = [
    ("custom outdoor kitchen",           5.00, None),
    ("custom outdoor kitchen design",    4.25, None),
    ("design my outdoor kitchen",        4.25, None),
    ("complete outdoor kitchen",         3.50, None),
    ("outdoor kitchen designers",        5.00, None),
    ("custom built outdoor kitchen",     5.00, None),
    ("outdoor kitchen builders near me", 5.00, "Outdoor Kitchen Builders"),
]

# Non-keyword headlines, all <= 30 chars. Deliberately free of claims that
# cannot be verified from here (financing, tax, guarantees) -- Trevor should
# swap in real offer specifics before enabling.
HEADLINES = [
    "Designed For Your Space",
    "Build Your Dream Kitchen",
    "Outdoor Kitchens, Your Way",
    "Custom Built To Order",
    "Get A Free Quote",
    "Request Your Design",
    "Shop Custom Kitchens",
    "Your Backyard, Upgraded",
    "Premium Outdoor Kitchens",
    "Made To Your Space",
    "Start Your Custom Build",
    "Talk To A Designer",
    "See Options & Pricing",
    "Design Yours Online",
]
DESCRIPTIONS = [
    "Custom outdoor kitchens built to fit your space. Request a free quote today.",
    "Choose your layout, appliances and finish. We build it and ship it to you.",
    "Work with a designer to plan your outdoor kitchen from start to finish.",
    "Tell us your space and budget. Get a custom outdoor kitchen plan back.",
]


def blocks(neg_text, neg_mt, kw_text):
    """Word-boundary check: would this negative switch off this keyword?"""
    kt, nt = kw_text.split(), neg_text.split()
    if neg_mt == "EXACT":
        return kt == nt
    if neg_mt == "PHRASE":
        return any(kt[i:i + len(nt)] == nt for i in range(len(kt) - len(nt) + 1))
    return all(w in kt for w in nt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    for h in HEADLINES:
        assert len(h) <= 30, f"headline too long ({len(h)}): {h}"
    for d in DESCRIPTIONS:
        assert len(d) <= 90, f"description too long ({len(d)}): {d}"
    for kw, _, pin in SKAGS:
        head = pin or kw.title()
        assert len(head) <= 30, (
            f"pinned headline too long ({len(head)}): {head!r} -- "
            f"give '{kw}' an explicit shorter headline in SKAGS")

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    # --- copy targeting from the source campaign ----------------------------
    geos, langs, negs = [], [], []
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign_criterion.type, campaign_criterion.negative,
               campaign_criterion.location.geo_target_constant,
               campaign_criterion.language.language_constant,
               campaign_criterion.keyword.text,
               campaign_criterion.keyword.match_type
        FROM campaign_criterion
        WHERE campaign.id = {SOURCE_CAMPAIGN}
          AND campaign_criterion.status != 'REMOVED' """):
        c = r.campaign_criterion
        t = c.type_.name
        if t == "LOCATION" and not c.negative:
            geos.append(c.location.geo_target_constant)
        elif t == "LANGUAGE":
            langs.append(c.language.language_constant)
        elif t == "KEYWORD" and c.negative:
            negs.append((c.keyword.text, c.keyword.match_type.name))

    # Guard: a copied negative must not switch off a keyword we are buying.
    conflicts = [(n, m, kw) for n, m in negs for kw, _, _ in SKAGS
                 if blocks(n, m, kw)]
    if conflicts:
        print("ABORT: campaign negatives would block keywords we are buying:")
        for n, m, kw in conflicts:
            print(f"  negative [{m}] '{n}'  blocks  '{kw}'")
        return 1

    print(f"copied from {SOURCE_CAMPAIGN}: {len(geos)} locations, "
          f"{len(langs)} language(s), {len(negs)} campaign negatives")
    print(f"  negatives: {[f'[{m[:2]}] {n}' for n, m in negs]}")
    print(f"  no conflicts with the {len(SKAGS)} keywords being bought")

    ops = []

    def op():
        o = client.get_type("MutateOperation")
        ops.append(o)
        return o

    budget_tmp = f"customers/{cust}/campaignBudgets/-1"
    camp_tmp = f"customers/{cust}/campaigns/-2"

    b = op().campaign_budget_operation.create
    b.resource_name = budget_tmp
    b.name = f"{CAMPAIGN_NAME} budget"
    b.amount_micros = int(DAILY_BUDGET * 1e6)
    b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False

    c = op().campaign_operation.create
    c.resource_name = camp_tmp
    c.name = CAMPAIGN_NAME
    c.status = e.CampaignStatusEnum.PAUSED
    c.advertising_channel_type = e.AdvertisingChannelTypeEnum.SEARCH
    c.campaign_budget = budget_tmp
    c.manual_cpc.enhanced_cpc_enabled = False
    c.network_settings.target_google_search = True
    c.network_settings.target_search_network = False
    c.network_settings.target_content_network = False
    c.network_settings.target_partner_search_network = False
    c.geo_target_type_setting.positive_geo_target_type = (
        e.PositiveGeoTargetTypeEnum.PRESENCE)
    c.geo_target_type_setting.negative_geo_target_type = (
        e.NegativeGeoTargetTypeEnum.PRESENCE)
    # Required on create in v25. This is an outdoor-kitchen retailer targeting
    # the US only, so the declaration is unambiguous.
    c.contains_eu_political_advertising = (
        e.EuPoliticalAdvertisingStatusEnum
        .DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)

    for g in geos:
        x = op().campaign_criterion_operation.create
        x.campaign = camp_tmp
        x.location.geo_target_constant = g
    for l in langs:
        x = op().campaign_criterion_operation.create
        x.campaign = camp_tmp
        x.language.language_constant = l
    for text, mt in negs:
        x = op().campaign_criterion_operation.create
        x.campaign = camp_tmp
        x.negative = True
        x.keyword.text = text
        x.keyword.match_type = getattr(e.KeywordMatchTypeEnum, mt)

    for i, (root, cpc, pinned) in enumerate(SKAGS):
        ag_tmp = f"customers/{cust}/adGroups/-{100 + i}"
        g = op().ad_group_operation.create
        g.resource_name = ag_tmp
        g.campaign = camp_tmp
        g.name = root.title()
        g.status = e.AdGroupStatusEnum.ENABLED
        g.type_ = e.AdGroupTypeEnum.SEARCH_STANDARD
        g.cpc_bid_micros = int(cpc * 1e6)

        for mt in ("PHRASE", "EXACT"):
            k = op().ad_group_criterion_operation.create
            k.ad_group = ag_tmp
            k.status = e.AdGroupCriterionStatusEnum.ENABLED
            k.keyword.text = root
            k.keyword.match_type = getattr(e.KeywordMatchTypeEnum, mt)

        a = op().ad_group_ad_operation.create
        a.ad_group = ag_tmp
        a.status = e.AdGroupAdStatusEnum.ENABLED
        a.ad.final_urls.append(LANDING)
        a.ad.responsive_search_ad.path1 = "custom-kitchens"
        a.ad.responsive_search_ad.path2 = "design"
        # Root keyword pinned to headline 1, per the SKAG method: search term
        # = ad headline = landing page headline.
        pin = client.get_type("AdTextAsset")
        pin.text = pinned or root.title()
        pin.pinned_field = e.ServedAssetFieldTypeEnum.HEADLINE_1
        a.ad.responsive_search_ad.headlines.append(pin)
        for h in HEADLINES:
            t = client.get_type("AdTextAsset")
            t.text = h
            a.ad.responsive_search_ad.headlines.append(t)
        for d in DESCRIPTIONS:
            t = client.get_type("AdTextAsset")
            t.text = d
            a.ad.responsive_search_ad.descriptions.append(t)

    print(f"\n{'EXECUTING' if args.execute else 'DRY RUN'}: {len(ops)} operations")
    print(f"  campaign  '{CAMPAIGN_NAME}'  PAUSED  ${DAILY_BUDGET:.2f}/day")
    print(f"  bidding   MANUAL_CPC (enhanced off)")
    print(f"  network   Google Search only")
    print(f"  geo       {len(geos)} locations, PRESENCE")
    print(f"  landing   {LANDING}")
    print(f"  ad groups {len(SKAGS)} SKAGs, phrase + exact, 15 headlines each")
    for root, cpc, pinned in SKAGS:
        head = pinned or root.title()
        print(f"      {root:34} max CPC ${cpc:.2f}   H1: {head!r}")

    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = cust
    req.mutate_operations.extend(ops)
    req.validate_only = not args.execute
    try:
        res = ga.mutate(request=req)
    except Exception as ex:
        print("\nFAILED:")
        print(str(ex)[:2000])
        return 1

    if not args.execute:
        print("\nVALIDATED - nothing written. Re-run with --execute to build.")
        return 0

    for r in res.mutate_operation_responses:
        if r._pb.HasField("campaign_result"):
            print(f"\n  created {r.campaign_result.resource_name}")
    print("  campaign is PAUSED -- confirm budget and bids before enabling")
    return 0


if __name__ == "__main__":
    sys.exit(main())
