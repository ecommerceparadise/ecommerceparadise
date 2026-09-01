"""Apply a universal negative keyword list: one shared set per account,
attached to every enabled campaign. Idempotent -- safe to re-run; it skips
terms and links that already exist rather than duplicating them.
"""

import json
from pathlib import Path

from google_ads.auth import get_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NEGATIVES_DIR = PROJECT_ROOT / "negative_keywords"

SHARED_SET_NAME = "Claude Negatives - Universal"

EXISTING_SHARED_SETS_QUERY = """
    SELECT shared_set.id, shared_set.name, shared_set.type, shared_set.status
    FROM shared_set
    WHERE shared_set.type = 'NEGATIVE_KEYWORDS'
      AND shared_set.status != 'REMOVED'
"""

ENABLED_CAMPAIGNS_QUERY = """
    SELECT campaign.id, campaign.name
    FROM campaign
    WHERE campaign.status = 'ENABLED'
"""


def load_list(json_path):
    return json.loads(Path(json_path).read_text())


def _existing_criteria_text(client, customer_id, shared_set_resource_name):
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT shared_criterion.keyword.text, shared_criterion.keyword.match_type
        FROM shared_criterion
        WHERE shared_criterion.shared_set = '{shared_set_resource_name}'
    """
    return {
        row.shared_criterion.keyword.text.lower()
        for row in ga_service.search(customer_id=customer_id, query=query)
    }


def _existing_linked_campaigns(client, customer_id, shared_set_resource_name):
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT campaign_shared_set.campaign
        FROM campaign_shared_set
        WHERE campaign_shared_set.shared_set = '{shared_set_resource_name}'
    """
    return {
        row.campaign_shared_set.campaign
        for row in ga_service.search(customer_id=customer_id, query=query)
    }


def get_or_create_shared_set(client, customer_id):
    ga_service = client.get_service("GoogleAdsService")
    for row in ga_service.search(customer_id=customer_id, query=EXISTING_SHARED_SETS_QUERY):
        if row.shared_set.name == SHARED_SET_NAME:
            return row.shared_set.resource_name, False

    shared_set_service = client.get_service("SharedSetService")
    op = client.get_type("SharedSetOperation")
    op.create.name = SHARED_SET_NAME
    op.create.type_ = client.enums.SharedSetTypeEnum.NEGATIVE_KEYWORDS
    response = shared_set_service.mutate_shared_sets(customer_id=customer_id, operations=[op])
    return response.results[0].resource_name, True


def add_missing_criteria(client, customer_id, shared_set_resource_name, negatives):
    already = _existing_criteria_text(client, customer_id, shared_set_resource_name)
    to_add = [n for n in negatives if n["term"].lower() not in already]
    if not to_add:
        return [], already

    shared_criterion_service = client.get_service("SharedCriterionService")
    ops = []
    for n in to_add:
        op = client.get_type("SharedCriterionOperation")
        op.create.shared_set = shared_set_resource_name
        op.create.keyword.text = n["term"]
        op.create.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
        ops.append(op)
    shared_criterion_service.mutate_shared_criteria(customer_id=customer_id, operations=ops)
    return to_add, already


def link_enabled_campaigns(client, customer_id, shared_set_resource_name):
    ga_service = client.get_service("GoogleAdsService")
    campaigns = list(ga_service.search(customer_id=customer_id, query=ENABLED_CAMPAIGNS_QUERY))
    already_linked = _existing_linked_campaigns(client, customer_id, shared_set_resource_name)

    to_link = [
        row for row in campaigns
        if row.campaign.resource_name not in already_linked
    ]
    if not to_link:
        return [], campaigns

    css_service = client.get_service("CampaignSharedSetService")
    ops = []
    for row in to_link:
        op = client.get_type("CampaignSharedSetOperation")
        op.create.campaign = row.campaign.resource_name
        op.create.shared_set = shared_set_resource_name
        ops.append(op)
    css_service.mutate_campaign_shared_sets(customer_id=customer_id, operations=ops)
    return to_link, campaigns


def apply_negative_list(json_path, client=None):
    """Apply one account's negative list. Returns a summary dict."""
    client = client or get_client()
    data = load_list(json_path)
    customer_id = data["account_id"]

    shared_set_resource_name, set_created = get_or_create_shared_set(client, customer_id)
    added, already_present = add_missing_criteria(
        client, customer_id, shared_set_resource_name, data["negatives"]
    )
    linked, all_enabled_campaigns = link_enabled_campaigns(
        client, customer_id, shared_set_resource_name
    )

    return {
        "account": data["account"],
        "account_id": customer_id,
        "shared_set_created": set_created,
        "shared_set_resource_name": shared_set_resource_name,
        "terms_added": [n["term"] for n in added],
        "terms_already_present": len(already_present),
        "campaigns_linked": [row.campaign.name for row in linked],
        "campaigns_enabled_total": len(all_enabled_campaigns),
    }
