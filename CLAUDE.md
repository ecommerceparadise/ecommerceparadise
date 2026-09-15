# ecommerceparadise — working notes for Claude

## Standing rules

### Automatically-created assets stay OFF, in every campaign, always

Trevor's instruction, 15 September 2026. Google's asset automations are opted
out everywhere and must stay that way. After building or importing any
campaign, run:

    PYTHONPATH=/home/user/ecommerceparadise .venv/bin/python \
        scripts/disable_asset_automation_everywhere.py --execute

It is idempotent and safe to re-run. Only these channels expose the setting:

| channel | types to opt out |
|---|---|
| PERFORMANCE_MAX | `FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION`, `TEXT_ASSET_AUTOMATION`, `GENERATE_IMAGE_EXTRACTION`, `GENERATE_IMAGE_ENHANCEMENT`, `GENERATE_ENHANCED_YOUTUBE_VIDEOS` |
| SEARCH | `FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION`, `TEXT_ASSET_AUTOMATION` |

Display, Shopping, Demand Gen and Local Services do not expose it.

**Set these on every new campaign at creation time**, not just via the sweep.

Why: with them on, PMax assembles display and video creative from the feed and
landing pages even when an asset group carries no assets, and Search campaigns
get headlines nobody wrote. Culinary Profis ran 34,829 Display impressions and
$96 against 1,544 Search impressions and $23 with three of five opted out;
Fountains USA, with all five off, ran 15,843 Search against 16 Display.

## Google Ads API

- v25 via `google-ads` 31.4.0 in `.venv`. System pip raises
  `pyo3_runtime.PanicException` — always use the venv:
  `PYTHONPATH=/home/user/ecommerceparadise .venv/bin/python scripts/X.py`
- Only the five accounts in `managed_accounts.json` may be touched.
- Campaigns are created PAUSED. Never enable a campaign, raise a budget or
  change a bid strategy without explicit confirmation in the conversation.
- Never delete campaigns, ad groups or conversion actions — pause instead.
- Location targeting is always PRESENCE, never PRESENCE_OR_INTEREST.
- Bulk operations get a dry-run summary before `--execute`.

### v25 gotchas worth remembering

- `campaign.url_expansion_opt_out` does not exist. Final URL expansion is
  controlled by `FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION` above.
- `contains_eu_political_advertising` is REQUIRED when creating a campaign.
- `Campaign.AssetAutomationSetting` is a nested type — `client.get_type()`
  cannot resolve it. Append plain dicts to `asset_automation_settings`. The
  field is replaced wholesale, so always write the full target set.
- Listing group filters: a SUBDIVISION and its children must be created in
  ONE mutate using temporary resource names (negative ids). A bare
  subdivision is rejected, and the request is atomic so one bad operation
  rolls back the batch.
- An "everything else" listing node must declare its dimension. Touching an
  empty proto3 message does not set the oneof — use
  `f._pb.case_value.product_brand.SetInParent()`.
- `campaign_conversion_goal` OVERRIDES `customer_conversion_goal`. Leaving it
  unset lets a campaign inherit the account goal. Setting it at campaign level
  has silently blinded three campaigns in these accounts.
- `bid_modifier=0.0` reads identically whether set to -100% or never set.
  Use `criterion._pb.HasField("bid_modifier")` to tell them apart.
- Date ranges: `BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'`. `DURING LAST_30_DAYS`
  is invalid. `change_event` needs a LIMIT and caps at 30 days.
- Filtering on a field requires it in the SELECT clause.
- PMax search terms are not in `search_term_view` — only
  `campaign_search_term_insight`, filtered to one campaign id.

## Feed-only PMax

The house pattern: one asset group per brand, each with a brand listing filter
and NO text, image, logo or video assets. Ad strength reads POOR and the group
is still ELIGIBLE — zero-asset asset groups DO serve, from the feed. Reference
implementations: `FUSA - PMax - Fountains (feed only)`,
`LES - PMax - Lasers (feed only)`, `CP - PMax - Culinary (feed only)`.

## Client data boundaries

- The Shopify connector points at Trevor's own store, not client stores. Do
  not pull client data from it. Use the Google Ads API and Merchant Center
  feed (`shopping_product`) for client catalogues.
- Shared negative keyword lists can be manager-level. `EP Generic`
  [11765673294] is the SAME list in all five accounts — anything added hits
  every client. Use each account's own list instead.
