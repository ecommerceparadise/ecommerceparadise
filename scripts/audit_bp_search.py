"""Read-only audit of the BetterPatio Search campaign, per the audit checklist."""
import sys
from collections import defaultdict
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 23303878302


def rows(ga, cust, q):
    return list(ga.search(customer_id=cust, query=q))


def main():
    client = get_client()
    cust = resolve_account("BetterPatio.com")["id"]
    ga = client.get_service("GoogleAdsService")

    print("=" * 78, "\nCAMPAIGN SETTINGS")
    q = f"""
    SELECT campaign.name, campaign.status, campaign.advertising_channel_type,
           campaign.bidding_strategy_type, campaign.maximize_conversions.target_cpa_micros,
           campaign.network_settings.target_google_search,
           campaign.network_settings.target_search_network,
           campaign.network_settings.target_content_network,
           campaign.optimization_score,
           campaign_budget.amount_micros, campaign_budget.explicitly_shared
    FROM campaign WHERE campaign.id = {CAMPAIGN}
    """
    for r in rows(ga, cust, q):
        c, b = r.campaign, r.campaign_budget
        print(f"  {c.name}  [{c.status.name}]")
        print(f"  bidding={c.bidding_strategy_type.name} tCPA=${c.maximize_conversions.target_cpa_micros/1e6:.2f}")
        print(f"  budget=${b.amount_micros/1e6:.2f}/day shared={b.explicitly_shared}")
        ns = c.network_settings
        print(f"  google_search={ns.target_google_search} search_partners={ns.target_search_network} display={ns.target_content_network}")
        print(f"  optimization_score={c.optimization_score:.2f}")

    print("=" * 78, "\nLAST 30 DAYS — CAMPAIGN")
    q = f"""
    SELECT metrics.impressions, metrics.clicks, metrics.cost_micros,
           metrics.conversions, metrics.all_conversions, metrics.average_cpc,
           metrics.search_impression_share, metrics.search_budget_lost_impression_share,
           metrics.search_rank_lost_impression_share, metrics.search_absolute_top_impression_share
    FROM campaign WHERE campaign.id = {CAMPAIGN} AND segments.date DURING LAST_30_DAYS
    """
    for r in rows(ga, cust, q):
        m = r.metrics
        print(f"  impr={m.impressions}  clicks={m.clicks}  cost=${m.cost_micros/1e6:.2f}  avgCPC=${m.average_cpc/1e6:.2f}")
        print(f"  conv={m.conversions:.1f}  all_conv={m.all_conversions:.1f}")
        print(f"  IS={m.search_impression_share:.1%}  lost_budget={m.search_budget_lost_impression_share:.1%}  lost_rank={m.search_rank_lost_impression_share:.1%}  abs_top={m.search_absolute_top_impression_share:.1%}")

    print("=" * 78, "\nAD GROUPS")
    q = f"""
    SELECT ad_group.id, ad_group.name, ad_group.status, ad_group.type,
           metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.all_conversions
    FROM ad_group WHERE campaign.id = {CAMPAIGN}
      AND ad_group.status != 'REMOVED' AND segments.date DURING LAST_30_DAYS
    """
    for r in rows(ga, cust, q):
        a, m = r.ad_group, r.metrics
        print(f"  {a.id} {a.name[:40]:42} [{a.status.name:8}] impr={m.impressions:6} clicks={m.clicks:4} ${m.cost_micros/1e6:8.2f} conv={m.all_conversions:.1f}")

    print("=" * 78, "\nADS (with strength + final url)")
    q = f"""
    SELECT ad_group.name, ad_group_ad.ad.id, ad_group_ad.status,
           ad_group_ad.ad_strength, ad_group_ad.ad.final_urls,
           ad_group_ad.ad.responsive_search_ad.headlines,
           ad_group_ad.ad.responsive_search_ad.descriptions,
           metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.all_conversions
    FROM ad_group_ad WHERE campaign.id = {CAMPAIGN}
      AND ad_group_ad.status != 'REMOVED' AND segments.date DURING LAST_30_DAYS
    """
    for r in rows(ga, cust, q):
        a, m = r.ad_group_ad, r.metrics
        rsa = a.ad.responsive_search_ad
        print(f"  ad {a.ad.id} [{a.status.name}] strength={a.ad_strength.name} "
              f"H={len(rsa.headlines)} D={len(rsa.descriptions)} impr={m.impressions} clicks={m.clicks} conv={m.all_conversions:.1f}")
        print(f"     url={list(a.ad.final_urls)}")

    print("=" * 78, "\nCAMPAIGN ASSETS (extensions)")
    q = f"""
    SELECT campaign.id, campaign_asset.field_type, campaign_asset.status
    FROM campaign_asset WHERE campaign.id = {CAMPAIGN} AND campaign_asset.status != 'REMOVED'
    """
    counts = defaultdict(int)
    for r in rows(ga, cust, q):
        counts[r.campaign_asset.field_type.name] += 1
    print("  " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "NONE"))

    print("=" * 78, "\nACCOUNT-LEVEL ASSETS (inherited extensions)")
    q = """
    SELECT customer_asset.field_type, customer_asset.status
    FROM customer_asset WHERE customer_asset.status != 'REMOVED'
    """
    counts = defaultdict(int)
    for r in rows(ga, cust, q):
        counts[r.customer_asset.field_type.name] += 1
    print("  " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "NONE"))

    print("=" * 78, "\nGEO / LANGUAGE / DEVICE CRITERIA")
    q = f"""
    SELECT campaign.id, campaign_criterion.type, campaign_criterion.negative,
           campaign_criterion.location.geo_target_constant,
           campaign_criterion.device.type, campaign_criterion.language.language_constant,
           campaign_criterion.bid_modifier
    FROM campaign_criterion WHERE campaign.id = {CAMPAIGN}
      AND campaign_criterion.status != 'REMOVED'
    """
    geo_pos = geo_neg = 0
    for r in rows(ga, cust, q):
        c = r.campaign_criterion
        if c.type_.name == "LOCATION":
            geo_neg += c.negative
            geo_pos += not c.negative
        elif c.type_.name in ("DEVICE", "LANGUAGE"):
            print(f"  {c.type_.name}: {c.device.type_.name or c.language.language_constant} mod={c.bid_modifier}")
    print(f"  LOCATION: {geo_pos} targeted, {geo_neg} excluded")

    q = f"SELECT campaign.geo_target_type_setting.positive_geo_target_type FROM campaign WHERE campaign.id = {CAMPAIGN}"
    for r in rows(ga, cust, q):
        print(f"  positive_geo_target_type={r.campaign.geo_target_type_setting.positive_geo_target_type.name}")

    print("=" * 78, "\nSHARED NEGATIVE LISTS APPLIED")
    q = f"""
    SELECT campaign.id, shared_set.name, shared_set.type, shared_set.member_count
    FROM campaign_shared_set WHERE campaign.id = {CAMPAIGN}
      AND campaign_shared_set.status != 'REMOVED'
    """
    for r in rows(ga, cust, q):
        s = r.shared_set
        print(f"  {s.name[:50]:52} {s.type_.name:22} members={s.member_count}")

    print("=" * 78, "\nKEYWORDS (enabled, last 30d)")
    q = f"""
    SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
           ad_group_criterion.status, ad_group_criterion.quality_info.quality_score,
           ad_group_criterion.quality_info.creative_quality_score,
           ad_group_criterion.quality_info.post_click_quality_score,
           ad_group_criterion.quality_info.search_predicted_ctr,
           metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.all_conversions
    FROM keyword_view WHERE campaign.id = {CAMPAIGN}
      AND ad_group_criterion.status = 'ENABLED' AND segments.date DURING LAST_30_DAYS
    """
    ks = rows(ga, cust, q)
    ks.sort(key=lambda r: -r.metrics.cost_micros)
    print(f"  {'keyword':38} {'match':7} {'QS':3} {'ad_rel':10} {'lp':10} {'impr':>6} {'clk':>4} {'cost':>8} {'conv':>5}")
    for r in ks:
        c, m, qi = r.ad_group_criterion, r.metrics, r.ad_group_criterion.quality_info
        print(f"  {c.keyword.text[:38]:38} {c.keyword.match_type.name[:7]:7} {qi.quality_score or 0:<3} "
              f"{qi.creative_quality_score.name[:10]:10} {qi.post_click_quality_score.name[:10]:10} "
              f"{m.impressions:6} {m.clicks:4} {m.cost_micros/1e6:8.2f} {m.all_conversions:5.1f}")
    print(f"  ({len(ks)} enabled keywords)")

    print("=" * 78, "\nSEARCH TERMS — last 30d, by cost")
    q = f"""
    SELECT search_term_view.search_term, search_term_view.status,
           metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.all_conversions
    FROM search_term_view WHERE campaign.id = {CAMPAIGN} AND segments.date DURING LAST_30_DAYS
    """
    st = rows(ga, cust, q)
    st.sort(key=lambda r: -r.metrics.cost_micros)
    waste = 0.0
    for r in st[:40]:
        m = r.metrics
        print(f"  {r.search_term_view.search_term[:52]:54} impr={m.impressions:5} clk={m.clicks:3} ${m.cost_micros/1e6:7.2f} conv={m.all_conversions:.1f}")
    for r in st:
        if r.metrics.all_conversions == 0:
            waste += r.metrics.cost_micros / 1e6
    print(f"  ({len(st)} terms; ${waste:.2f} spent on terms with zero conversions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
