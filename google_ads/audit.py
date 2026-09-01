"""Read-only account audit per the google-ads-automation skill's checklist.

Pulls campaign performance, ad status (to explain zero-activity accounts —
paused vs. disapproved vs. no campaigns at all), wasted search-term spend,
and the two settings-drift checks the skill calls out by name: location
targeting must be Presence (not Presence-or-interest), and campaign network
settings must not have silently opted into Display/search-partner traffic.

Nothing here writes. It only reads and reports.
"""

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN_QUERY = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.status,
      campaign.advertising_channel_type,
      campaign.geo_target_type_setting.positive_geo_target_type,
      campaign.network_settings.target_content_network,
      campaign.network_settings.target_search_network,
      campaign.network_settings.target_partner_search_network,
      campaign_budget.amount_micros,
      metrics.cost_micros,
      metrics.clicks,
      metrics.impressions,
      metrics.conversions,
      metrics.conversions_value,
      metrics.ctr,
      metrics.average_cpc
    FROM campaign
    WHERE segments.date DURING LAST_30_DAYS
    ORDER BY metrics.cost_micros DESC
"""

# Campaigns with zero rows in the metrics-scoped query above (e.g. never
# served) still need to show up, so status/count comes from a second,
# metrics-free query.
CAMPAIGN_STATUS_QUERY = """
    SELECT campaign.id, campaign.name, campaign.status
    FROM campaign
"""

AD_STATUS_QUERY = """
    SELECT
      campaign.id,
      ad_group_ad.status,
      ad_group_ad.ad.id,
      ad_group_ad.policy_summary.approval_status
    FROM ad_group_ad
"""

SEARCH_TERM_QUERY = """
    SELECT
      campaign.name,
      ad_group.name,
      search_term_view.search_term,
      metrics.cost_micros,
      metrics.clicks,
      metrics.conversions
    FROM search_term_view
    WHERE segments.date DURING LAST_30_DAYS
      AND metrics.clicks > 0
    ORDER BY metrics.cost_micros DESC
"""


def _micros(v):
    return v / 1_000_000


def audit_account(name_or_id, client=None, days=30):
    """Return a read-only audit dict for one managed account."""
    client = client or get_client()
    account = resolve_account(name_or_id, client=client)
    customer_id = account["id"]
    ga_service = client.get_service("GoogleAdsService")

    campaigns = {}
    for row in ga_service.search(customer_id=customer_id, query=CAMPAIGN_STATUS_QUERY):
        c = row.campaign
        campaigns[c.id] = {
            "id": c.id,
            "name": c.name,
            "status": c.status.name,
            "channel_type": None,
            "geo_target_type": None,
            "network_display": None,
            "network_partner_search": None,
            "budget": 0.0,
            "spend": 0.0,
            "clicks": 0,
            "impressions": 0,
            "conversions": 0.0,
            "conv_value": 0.0,
        }

    for row in ga_service.search(customer_id=customer_id, query=CAMPAIGN_QUERY):
        c = row.campaign
        entry = campaigns.setdefault(c.id, {"id": c.id, "name": c.name})
        entry.update(
            {
                "status": c.status.name,
                "channel_type": c.advertising_channel_type.name,
                "geo_target_type": c.geo_target_type_setting.positive_geo_target_type.name,
                "network_display": c.network_settings.target_content_network,
                "network_partner_search": c.network_settings.target_partner_search_network,
                "budget": _micros(row.campaign_budget.amount_micros),
                "spend": _micros(row.metrics.cost_micros),
                "clicks": row.metrics.clicks,
                "impressions": row.metrics.impressions,
                "conversions": row.metrics.conversions,
                "conv_value": row.metrics.conversions_value,
            }
        )

    ad_status_counts = {}
    for row in ga_service.search(customer_id=customer_id, query=AD_STATUS_QUERY):
        cid = row.campaign.id
        counts = ad_status_counts.setdefault(
            cid, {"ENABLED": 0, "PAUSED": 0, "REMOVED": 0}
        )
        counts[row.ad_group_ad.status.name] = counts.get(row.ad_group_ad.status.name, 0) + 1
        approval = row.ad_group_ad.policy_summary.approval_status.name
        if approval not in ("APPROVED", "APPROVAL_STATUS_UNSPECIFIED", "UNKNOWN"):
            counts[f"approval:{approval}"] = counts.get(f"approval:{approval}", 0) + 1

    for cid, counts in ad_status_counts.items():
        if cid in campaigns:
            campaigns[cid]["ad_status"] = counts

    search_terms = []
    for row in ga_service.search(customer_id=customer_id, query=SEARCH_TERM_QUERY):
        search_terms.append(
            {
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "term": row.search_term_view.search_term,
                "spend": _micros(row.metrics.cost_micros),
                "clicks": row.metrics.clicks,
                "conversions": row.metrics.conversions,
            }
        )

    wasted_terms = sorted(
        (t for t in search_terms if t["conversions"] == 0 and t["spend"] > 0),
        key=lambda t: -t["spend"],
    )

    campaign_list = sorted(campaigns.values(), key=lambda c: -c.get("spend", 0))
    total_spend = sum(c.get("spend", 0) for c in campaign_list)
    total_conv = sum(c.get("conversions", 0) for c in campaign_list)
    total_conv_value = sum(c.get("conv_value", 0) for c in campaign_list)

    settings_flags = []
    for c in campaign_list:
        if c.get("channel_type") == "SEARCH":
            if c.get("geo_target_type") not in (None, "PRESENCE"):
                settings_flags.append(
                    f"{c['name']}: location targeting is {c['geo_target_type']}, "
                    "should be PRESENCE"
                )
            if c.get("network_display"):
                settings_flags.append(f"{c['name']}: Display Network expansion is ON")
            if c.get("network_partner_search"):
                settings_flags.append(f"{c['name']}: Search Partners expansion is ON")

    return {
        "account_id": customer_id,
        "account_name": account["name"],
        "campaigns": campaign_list,
        "total_spend": total_spend,
        "total_conversions": total_conv,
        "total_conv_value": total_conv_value,
        "wasted_search_terms": wasted_terms,
        "settings_flags": settings_flags,
    }
