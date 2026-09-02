"""Keyword research via the Google Ads Keyword Planner API (read-only).

The methodology is explicit that keywords must come from real volume data,
never from model guesswork -- AI-invented keywords routinely have zero
monthly searches. This pulls live Keyword Planner ideas with average monthly
searches, competition, and top-of-page bid ranges so SKAG selection is
grounded in what people actually search.
"""

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

# Keyword Planner constants.
LANG_ENGLISH = "languageConstants/1000"
GEO_UNITED_STATES = "geoTargetConstants/2840"

# Loser patterns from the methodology -- these get rejected and seed the
# negative keyword list rather than becoming SKAGs.
LOSER_PATTERNS = [
    "job", "jobs", "hiring", "salary", "career", "apprentice", "resume",
    "course", "school", "training", "certification", "class",
    "how to", "diy", "do it yourself", "definition", "meaning", "wiki",
    "coupon", "free ", "cheap", "promo code", "discount code",
    "used", "craigslist", "for rent", "rental", "repair", "parts",
    "reddit", "forum", "youtube",
]


def _micros(v):
    return (v or 0) / 1_000_000


def is_loser(term):
    """True if the term matches a reject pattern from the methodology."""
    t = term.lower()
    return any(p in t for p in LOSER_PATTERNS)


def keyword_ideas(
    account,
    seeds,
    client=None,
    geo=GEO_UNITED_STATES,
    language=LANG_ENGLISH,
    page_url=None,
):
    """Return Keyword Planner ideas for the given seed terms.

    Each result carries the metrics needed to decide whether a term is worth
    a SKAG: average monthly searches, competition level, and the top-of-page
    bid range that sets cost expectations.
    """
    client = client or get_client()
    acct = resolve_account(account, client=client)
    service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = acct["id"]
    request.language = language
    request.geo_target_constants = [geo]
    request.keyword_plan_network = (
        client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    )
    request.include_adult_keywords = False

    if page_url and seeds:
        request.keyword_and_url_seed.url = page_url
        request.keyword_and_url_seed.keywords.extend(seeds)
    elif page_url:
        request.url_seed.url = page_url
    else:
        request.keyword_seed.keywords.extend(seeds)

    ideas = []
    for idea in service.generate_keyword_ideas(request=request):
        m = idea.keyword_idea_metrics
        ideas.append(
            {
                "term": idea.text,
                "monthly_searches": m.avg_monthly_searches or 0,
                "competition": m.competition.name if m.competition else "UNKNOWN",
                "bid_low": _micros(m.low_top_of_page_bid_micros),
                "bid_high": _micros(m.high_top_of_page_bid_micros),
                "loser": is_loser(idea.text),
            }
        )

    ideas.sort(key=lambda k: -k["monthly_searches"])
    return ideas


def filter_winners(ideas, min_searches=100):
    """Split ideas into SKAG candidates and rejects.

    Rejects are as useful as winners -- they seed the negative keyword list.
    """
    winners, rejects = [], []
    for idea in ideas:
        if idea["loser"]:
            rejects.append({**idea, "reason": "loser pattern"})
        elif idea["monthly_searches"] < min_searches:
            rejects.append({**idea, "reason": f"under {min_searches}/mo"})
        else:
            winners.append(idea)
    return winners, rejects
