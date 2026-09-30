# ecommerceparadise — working notes for Claude

## Standing rules

### Automatically-created assets stay OFF, in every campaign, always

Trevor's instruction, 15 September 2026. Google's asset automations are opted
out everywhere and must stay that way. After building or importing any
campaign, run:

    PYTHONPATH=/home/user/ecommerceparadise .venv/bin/python \
        scripts/disable_asset_automation_everywhere.py --execute

It is idempotent and safe to re-run, and it sweeps every account in
`managed_accounts.json` -- so adding an account there is enough; do not
hardcode a second list. Only these channels expose the setting:

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
- Only the accounts in `managed_accounts.json` may be touched (six as of
  2026-09-29). `resolve_account` matches the LIVE account name from the API, so
  an allowlist entry whose name differs from the live one resolves only by id.
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
`LES - PMax - Lasers (feed only)`, `CP - PMax - Culinary (feed only)`,
`HS - PMax - HVAC (feed only)`.

Every asset group needs search themes AND an audience signal, not just a
listing filter. A group with a brand filter and no signals is the one failure
mode that looks finished in the UI: it will serve, but PMax has no query intent
to work from. Four LES groups shipped that way on 28 Sept (backfilled 29 Sept)
and 24 of BetterPatio's 26 groups were like it on a $180/day campaign
(backfilled 30 Sept). Build signals in the same script that builds the group.

ONE shared audience per account only works when the catalogue is one thing
(LES is all lasers, HVAC Saver all HVAC). Where a store spans product families,
build one audience per family and assign it per group -- BetterPatio sells
grills, sofas and fire pits, so blending "Garden & Outdoor Furniture" into the
Blaze grill group would tell Google a sofa shopper is a grill prospect.

Before writing themes for an asset group, check the brand still has servable
products. Asset groups outlive the brands they filter on: seven BetterPatio
groups read ELIGIBLE with zero products in the feed, because those brands left
the catalogue after the groups were built. Themes there buy traffic the store
cannot fulfil.

### No catch-all asset groups

Trevor's instruction, 30 September 2026: "we should only have asset groups for
specific brands that have products in the feed. we should not have an all other
brands asset group either" -- "we need to hyper focus these asset groups one per
brand." This REPLACES the earlier catch-all pattern; the one built into
`HS - PMax - HVAC (feed only)` on 29 Sept was wrong and is paused.

Three rules, enforced by `scripts/prune_pmax_asset_groups.py` (dry run by
default, `--execute` to apply, safe to re-run):

1. one asset group per brand, and only for brands with servable products
2. no "all other brands" / everything-else group
3. every enabled group carries search themes AND an audience signal

The trade-off is real and must be reported, not glossed: with no catch-all, a
brand with no group of its own cannot serve at all, and a brand added to the
feed later stays dark until someone builds it a group. The script prints the
unreachable count per account. Reachability is judged PER PRODUCT, not per
brand, because some groups filter on product_type -- counting by brand alone
wrongly reports type-covered brands as orphans.

Asset groups are PAUSED, never REMOVED. Both paused and removed groups keep
returning their listing filters from the API, so coverage queries must join on
`asset_group.status` either way.

### Per-account conventions worth not rediscovering

| account | geo | notes |
|---|---|---|
| HVAC Saver | US minus Alaska, Hawaii, Puerto Rico | freight on AC/furnace equipment; 21 of 24 campaigns already did this |
| BetterPatio | — | asset group names use a MIDDLE DOT: `BP · Cal Flame`, not `BP - `. Cal Flame and Mont Alpi filter on product_type, every other group on product_brand. |

## Client-requested exclusions

These are the client's instructions, not optimisation choices. Do not "fix"
them by building the coverage back.

### HVAC Saver: Goodman only, never Daikin

The client asked to advertise Goodman and NOT Daikin (Trevor, 30 September
2026). Daikin is 101 servable products, roughly a fifth of the feed, and it
will keep showing up as an apparent coverage gap. It is not one.

- `HS - Daikin` [6753068326] is PAUSED and stays paused.
- The 13 paused Daikin-named campaigns must not be enabled: `Daikin Campaign
  | High/Medium/Low`, `Daikin Max Clicks | High/Medium/Low`, `Daikin Shopping
  | High/Medium/Low`, `Daikin | High/Medium/Low`, `Daikin Search`.
- Verified safe on 30 Sept: the only enabled campaign is
  `HS - PMax - HVAC (feed only)`, whose one enabled asset group includes
  `brand=goodman` with everything-else excluded. The nine Goodman-named
  Shopping campaigns each exclude non-Goodman at the ROOT of the listing tree
  (`UNIT negative=true` on everything-else), so Daikin would stay out even if
  one of them were switched on.
- `WITHHELD_BRANDS` in `scripts/prune_pmax_asset_groups.py` carries this, so
  the audit reports Daikin as withheld rather than as a gap.

## Client data boundaries

- The Shopify connector points at Trevor's own store, not client stores. Do
  not pull client data from it. Use the Google Ads API and Merchant Center
  feed (`shopping_product`) for client catalogues.
- Shared negative keyword lists can be manager-level. `EP Generic`
  [11765673294] is the SAME list in all five accounts — anything added hits
  every client. Use each account's own list instead.
