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

## Credentials survive a container rebuild only in the environment

The container is rebuilt from a fresh clone, so a local `.env` is lost. It
happened on 1 October 2026: the venv and all five credential vars vanished and
no API call was possible until they were restored.

`google_ads/auth.py` reads real environment variables BEFORE `.env`, so the
durable fix is to store them on the cloud environment (environment settings ->
Edit -> API credentials, or as environment variables) rather than on disk:

    GOOGLE_ADS_DEVELOPER_TOKEN
    GOOGLE_ADS_CLIENT_ID
    GOOGLE_ADS_CLIENT_SECRET
    GOOGLE_ADS_REFRESH_TOKEN
    GOOGLE_ADS_LOGIN_CUSTOMER_ID

A new session then picks them up with nothing to re-paste. Never put them in
the repo or in chat.

`requirements.txt` pins `google-ads==31.4.0`. An unpinned rebuild installed
33.0.0, which changes the default API version out from under scripts written
against v25.

## Performance Max placement and channel exclusions

There is NO generally available channel off-switch in PMax. You cannot turn off
Display or YouTube the way a Search campaign can. Google began alpha-testing a
Partners setting with independent Search Partner and Display checkboxes in
mid-2026; it is limited availability and does not cover YouTube.

What does work, and applies to PMax:

- ACCOUNT level, `customer_negative_criterion`. Since January 2026 these apply
  across Performance Max, Demand Gen, YouTube and Display simultaneously, so
  one list covers every campaign. v25 accepts `placement`, `placement_list`,
  `youtube_video`, `youtube_channel`, `mobile_application`,
  `mobile_app_category`, `content_label`, `negative_keyword_list`, `ip_block`.
- CAMPAIGN level, `campaign_criterion` with `negative = true`, which also
  accepts `topic`, `keyword`, `brand_list`, `webpage` and `device`.

`campaign.network_settings` has `target_content_network` and `target_youtube`
fields, but they are not the PMax lever -- do not expect setting them to work.

Build the exclusion list from evidence, not guesses:
`scripts/audit_pmax_placements.py` (read only) reports the network split per
campaign from `segments.ad_network_type`, the actual placements from
`performance_max_placement_view` (impressions only -- that view has no cost),
and what is already excluded at account and campaign level.

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
  `f._pb.case_value.product_brand.SetInParent()`. For a product_type
  dimension that is not enough: `case_value.product_type.level` is also
  REQUIRED (e.g. `LEVEL1`).
- A listing-filter batch is validated OPERATION BY OPERATION, not at the end.
  Removing a SUBDIVISION's everything-else child while the subdivision still
  has other children fails with
  `SUBDIVISION_MUST_HAVE_EVERYTHING_ELSE_CHILD`. To reshape a subtree, remove
  the whole thing in one atomic mutate — children first, the subdivision last
  — and create the replacement in the same request. That is accepted.
- `CONCURRENT_MODIFICATION` ("Multiple requests were attempting to modify the
  same resource at once") is transient. Retry with backoff; do not treat it as
  a real failure. It can leave a multi-step build half-done, so build scripts
  should be resumable rather than abort-if-exists.
- To judge which products an asset group can serve, WALK THE TREE. Reading
  `UNIT_INCLUDED` nodes in isolation misreads a brand-scoped tree
  (`ROOT -> SUBDIVISION brand=X -> UNIT_INCLUDED type=Y`) as a bare
  product-type filter, which wrongly looks like it is catching every brand.
  Descend from the root, matching each subdivision's dimension and falling
  back to the everything-else sibling.
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
and NO text, image, logo or video assets.

Opting out the five asset automations is NOT the same as being feed only. Those
settings stop Google GENERATING creative; they do nothing about creative a
human uploaded. Check `asset_group_asset` directly -- two BetterPatio groups
carried 34 enabled assets each (10 headlines, 4 descriptions, 11 images, 5
YouTube videos) on a $180/day campaign long after the automations were off, so
PMax could still assemble Display and Video ads for them.

**An asset group that has assets can never become feed only. It must be
replaced.** Two things that look like fixes are not:

* Pausing the asset links leaves them attached. The creative still shows on the
  group in the UI and the group still is not feed only.
* Removing the links is rejected outright. Google validates the group's FINAL
  state and returns all five minimums at once --
  `NOT_ENOUGH_HEADLINE_ASSET`, `NOT_ENOUGH_LONG_HEADLINE_ASSET`,
  `NOT_ENOUGH_DESCRIPTION_ASSET`, `NOT_ENOUGH_MARKETING_IMAGE_ASSET`,
  `NOT_ENOUGH_SQUARE_MARKETING_IMAGE_ASSET`.

A zero-asset asset group is only legal if it is CREATED that way. So retire the
old group (rename with a `ZZ REPLACED (had creative) - ` prefix and PAUSE it)
and create a fresh one, carrying over its search themes, audience and brand
filter. `scripts/replace_bp_legacy_asset_groups.py` does exactly that. The cost
is the retired group's learning history, so weigh it -- but a group carrying
creative is not feed only, whatever else is configured. Ad strength reads POOR and the group
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

## Display dynamic remarketing

A Display dynamic remarketing ad is NOT feed only the way a PMax asset group
is. A responsive display ad REQUIRES headlines, descriptions and images: the
feed supplies the product panel (image, title, price) and the assets supply the
frame around it. A Display ad cannot serve with zero assets, so creative on one
is correct, not a mistake.

How the feed attaches, which is easy to misread:

- For a DISPLAY campaign it is `campaign.shopping_setting.merchant_id`, and
  that is the whole mechanism. An empty `campaign_asset_set` proves nothing.
- The MERCHANT_CENTER_FEED asset sets that every PMax campaign links are
  GOOGLE-MANAGED. Creating such a link by hand returns `MUTATE_NOT_ALLOWED`.
- A business data feed (`DYNAMIC_CUSTOM` asset set) is the other path, linked
  via `campaign_asset_set`. `BP · ATS | Display` uses that one.

Responsive display ad creative is IMMUTABLE. Adding a logo, a headline or an
image to an existing RDA is impossible -- build a new ad with the same text and
image assets plus the addition, then pause the old one.

RDA field caps, worth validating before a mutate: headline 30 chars (5 max),
description 90 chars (5 max), long headline 90, business name 25. Marketing
images must be 1.91:1 and square marketing images and logos 1:1, so check
`asset.image_asset.full_size` dimensions rather than trusting a filename -- a
2000x1040 image looks landscape but is 1.923:1 and will be refused.

When picking images for an account whose catalogue is brand-restricted, take
them from a brand-specific asset group rather than the account's asset library.
HVAC Saver has 227 image assets and only Goodman may be advertised; pulling
"a square image" at random could surface a Daikin unit.

`BP · Dynamic Display Remarketing Ads` [24040677834], fixed 30 September 2026:
its four remarketing lists all sat in one ad group, where 84,000 general
visitors buried 200 cart abandoners, so the high-intent audience never won an
auction. Now one ad group per intent tier (Cart Abandoners, Product Viewers,
General Visitors), each with its own RDA carrying the brand logo.

It bids on PURCHASE only, by Trevor's instruction of 30 September 2026, and the
consequence is worth restating whenever this campaign comes up: it produced 0
purchases in 90 days against $977 of spend, while its 26 lead-form submissions
and 12 add-to-carts are excluded from the `conversions` metric. Maximize
Conversions therefore has no signal to learn from. That is a deliberate choice,
not an oversight.

## Client-requested exclusions

These are the client's instructions, not optimisation choices. Do not "fix"
them by building the coverage back.

### Fountains USA: only the four brands originally set up

The client only wants the brands we initially set up (Trevor, 30 September
2026): `fiore stone`, `giannini garden`, `metropolitan galleries inc.` and
`the outdoor plus`. Everything else in the feed -- 1,934 of 8,324 products
across 11 brands, led by phoenix precast (666), travertine & more (336) and
easy pro pond (261) -- is deliberately unadvertised. Do NOT build groups for
them, however much it looks like a coverage gap on the account with the best
ROAS in the portfolio.

Recorded as `ADVERTISE_ONLY` (an allowlist) rather than a list of excluded
brands in `scripts/prune_pmax_asset_groups.py`, so a brand added to the feed
later is withheld too instead of surfacing as a new gap.

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

**`HS - Display Dynamic Remarketing (HOLD - do not enable, Daikin in feed)`
[24298306452] must stay PAUSED.** Built 30 September 2026 on Trevor's
instruction to build it and hold. A Display dynamic remarketing campaign has NO
brand filter (verified: BetterPatio's ten feed-attached Display campaigns carry
zero `LISTING_GROUP` criteria; Display targets by USER_LIST, KEYWORD, TOPIC,
AGE_RANGE, USER_INTEREST, CUSTOM_INTENT, YOUTUBE_CHANNEL only). The feed has one
label, `US`, holding goodman 453 and daikin 103 together, so enabling this
campaign shows a Daikin browser their Daikin product. Two prerequisites, both
outside Google Ads:

1. Merchant Center needs a GOODMAN-ONLY feed label (supplemental feed or feed
   rule), and the campaign's `shopping_setting.feed_label` must point at it.
2. The retail remarketing tag on hvacsaver.com must pass product IDs. After
   1,205 clicks in September, `Product viewers`, `Shopping cart abandoners` and
   `Past buyers` all read 0 while `General visitors` reads 2,600 -- the
   page-level tag fires, the product-level one does not. Dynamic remarketing has
   nothing to be dynamic about until that is fixed.

## Client data boundaries

- The Shopify connector points at Trevor's own store, not client stores. Do
  not pull client data from it. Use the Google Ads API and Merchant Center
  feed (`shopping_product`) for client catalogues.
- Shared negative keyword lists can be manager-level. `EP Generic`
  [11765673294] is the SAME list in all five accounts — anything added hits
  every client. Use each account's own list instead.
