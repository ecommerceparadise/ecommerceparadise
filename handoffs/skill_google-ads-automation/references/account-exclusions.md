# Account-level placement and content exclusions

Set these ONCE per account, before the first campaign is enabled. Standard phase
of every new-account build — Trevor's instruction, 2 October 2026, after the
client Performance Max campaigns were found serving heavily and untargeted on
Display and YouTube.

## Why this is the lever

Performance Max has **no generally available channel off-switch**. You cannot
tick "no Display" or "no YouTube" the way a Search campaign can.
`campaign.network_settings` has `target_content_network` and `target_youtube`
fields, but they are not the PMax lever — do not expect setting them to work.
Google began alpha-testing a Partners setting with independent Search Partner
and Display checkboxes in mid-2026; it is limited availability and does not
cover YouTube.

What does work:

- **ACCOUNT level — `customer_negative_criterion`.** Since January 2026 these
  apply across Performance Max, Demand Gen, YouTube and Display
  simultaneously, so one list covers every campaign in the account, including
  ones built later. v25 accepts `placement`, `placement_list`,
  `youtube_video`, `youtube_channel`, `mobile_application`,
  `mobile_app_category`, `content_label`, `negative_keyword_list`, `ip_block`.
- **CAMPAIGN level — `campaign_criterion` with `negative = true`**, which also
  accepts `topic`, `keyword`, `brand_list`, `webpage` and `device`.

Because it is account-wide and retroactive, doing it first costs nothing and
doing it late means paying for parked domains and in-app inventory in the
meantime.

## Evidence first

Build the list from what the account is actually serving on, not from guesses:

    PYTHONPATH=<repo> .venv/bin/python scripts/audit_pmax_placements.py \
        [--days 30] [--account NAME_OR_ID]

Read only. It reports, per enabled PMax campaign: the network split from
`segments.ad_network_type` (how much really goes to Display and YouTube versus
Search), the actual placements from `performance_max_placement_view`
(impressions only — that view carries no cost), and what is already excluded at
account and campaign level.

PMax search terms are NOT in `search_term_view` — only
`campaign_search_term_insight`, filtered to one campaign id.

## Apply

    PYTHONPATH=<repo> .venv/bin/python \
        scripts/apply_account_placement_exclusions.py [--account ID] [--execute]

Dry run by default; sweeps every allowlisted account unless `--account` narrows
it. Idempotent — it reads existing exclusions and skips them — so re-running
after a later campaign build is the easy way to confirm coverage.

Two families, different in kind:

1. **Content labels** — a fixed v25 enum, so the list is explicit and
   auditable. 16 are applied: `PARKED_DOMAIN` and `BELOW_THE_FOLD` (pure
   waste — domain arbitrage and impressions nobody saw); `EMBEDDED_VIDEO` and
   `LIVE_STREAMING_VIDEO` (low-intent video surfaces that inflate
   Display/YouTube volume); then `SEXUALLY_SUGGESTIVE`, `JUVENILE`,
   `PROFANITY`, `TRAGEDY`, `SOCIAL_ISSUES`, the four
   `BRAND_SUITABILITY_GAMES_FIGHTING` / `GAMES_MATURE` / `POLITICS` /
   `RELIGION`, `BRAND_SUITABILITY_NEWS_SENSITIVE`, `VIDEO_RATING_DV_MA` and
   `VIDEO_NOT_YET_RATED` for brand safety.

   Left ON deliberately: `VIDEO` (would remove all video — too blunt), the
   family-safe video ratings `DV_G` / `DV_PG` / `DV_T`,
   `BRAND_SUITABILITY_CONTENT_FOR_FAMILIES`, and the HEALTH and remaining NEWS
   suitability labels — too broad for a home-improvement or equipment niche to
   be worth the reach loss.

2. **Mobile app categories** — in-app inventory, resolved at run time by
   querying `mobile_app_category_constant` rather than hardcoded, since the
   IDs are a Google taxonomy. On a store selling $2k–$25k equipment, app
   traffic is close to pure waste and is usually the bulk of untargeted
   Display volume. `--keep-apps` skips this family for an account that
   genuinely wants it.

Specific sites, apps and YouTube channels are deliberately not defaulted. Feed
them in from the audit with `--placements FILE` — one per line; a bare domain
is treated as a placement, a 24-character `UC...` string as a YouTube channel,
anything else as an app id. Lines starting with `#` are ignored.

## Implementation notes

- Mutate with `partial_failure=True`. Content-label support varies by campaign
  type and one unsupported value must not roll back the batch. A rejected
  operation returns an empty `resource_name` in send order — map that against a
  parallel list of labels to name the rejection, rather than unpacking
  `GoogleAdsFailure`, whose shape differs between library versions (it has no
  `deserialize` in `google-ads` 31.4.0).
- Read existing criteria first and skip duplicates; `type_.name` tells you
  which oneof to read.
- Filtering or reading a field requires it in the SELECT clause.

## Doing it in the UI

Tools → Content suitability → Excluded content for the labels; Tools →
Placement exclusion lists for specific placements. Prefer the API path: it is
repeatable, covers every account in one pass, and leaves a record.
