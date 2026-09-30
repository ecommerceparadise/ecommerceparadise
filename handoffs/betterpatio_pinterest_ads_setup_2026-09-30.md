# BetterPatio — Pinterest Ads setup spec

Advertiser `549762101084`. Budget ceiling $20/day, per Trevor.

**I could not build this directly.** I have no access to Trevor's browser or
Pinterest session, and there is no Pinterest connector in this environment (the
Google Ads work runs on stored API credentials; nothing equivalent exists for
Pinterest). Pinterest's own domains are also blocked by this container's egress
policy, so the research below comes from third-party sources, not
business.pinterest.com. Everything here is either a verified figure with a
source, or flagged as judgement.

There is a way for me to do the build itself — see **Automation** at the end.

---

## The budget problem, first

This is the thing that decides the whole structure, so it goes before the steps.

Two of Pinterest's published budget rules collide with this catalogue:

| rule | source | what it implies here |
|---|---|---|
| Catalog campaigns: budget ~**$1/day per product promoted** | Simple Pin Media | $20/day supports roughly **20 products**, not 8,889 |
| Conversion campaigns: daily budget **4–10× your CPA** | Simple Pin Media | BetterPatio's AOV is $2k–$25k, so purchase CPA is in the hundreds. $20/day cannot sustain a purchase-optimised campaign |

The feed has **8,889 servable products** across 223 product types. Pointing a
$20/day catalog campaign at all of them spends about a fifth of a cent per
product per day. It would do nothing.

So the structure has to be: **one campaign, one ad group, a deliberately tiny
product group.** Not a mirror of the Google PMax setup.

## Which products — from the actual feed

Pinterest's audience is home and outdoor-living browsing, and it converts far
better at lower price points. The catalogue splits usefully:

| product type | servable | median price | under $3k |
|---|---|---|---|
| fire & water bowl | 2,071 | $5,130 | 288 |
| fire bowl | 1,535 | $4,488 | 514 |
| fire pit | 1,115 | $4,675 | 137 |
| water bowl | 369 | $1,902 | 339 |
| planter bowl | 360 | $1,660 | 338 |
| planter & water bowl | 354 | $2,262 | 301 |
| outdoor dining sets | 280 | $2,986 | 164 |
| bbq grill | 160 | $2,536 | 102 |
| **bbq island** | **283** | **$10,999** | 24 |

3,535 products sit under $3,000.

**Recommended product group: fire bowls, water bowls and planter bowls under
$3,000** — the sculptural water and fire features, mostly The Outdoor Plus.
Median $1,650–$2,800. They are the most Pinterest-native thing in the
catalogue: photogenic, aspirational, saveable, and cheap enough that a cold
Pinterest visitor might actually buy. Start with ~20–30 of them.

**Explicitly NOT the BBQ islands.** At a $10,999 median they are the money in
this store, but they are a months-long considered purchase. They belong to
Google Search and PMax, where intent already exists. Pinterest can feed them
later through retargeting, once there is an audience to retarget. (Judgement,
not a Pinterest rule.)

---

## Step 1 — Foundation, before any campaign

BetterPatio is on Shopify, and the official Pinterest app does almost all of
this in one go. Installing it:

- claims the domain on Pinterest (required before catalog ads can run)
- adds the verification meta tag to the theme
- installs the base Pinterest tag plus standard events: **PageVisit,
  ViewCategory, AddToCart, Checkout**
- creates the catalog and ingests the product feed

Shopify admin → **Sales Channels → Add Sales Channel → Pinterest** → authorise
→ configure which products to include and the currency.

Then verify by hand:

1. Pinterest **Settings → Claimed accounts** shows betterpatio.com
2. The catalog has ingested. Shopify collections sync **every 48 hours** and
   arrive in Pinterest as product groups, so allow up to two days before
   expecting product groups to exist.
3. Apply for the **Verified Merchant Program** — free, and it unlocks organic
   shopping surfaces alongside the paid ones.

Conversions API is the modern standard at meaningful spend, but at $20/day the
Shopify app's client-side tag is enough to start. Add CAPI when budget scales.

## Step 2 — Product group

Either use a Shopify collection that already matches (cleanest, since it syncs
automatically), or build the product group inside Pinterest from the catalog.

If creating a Shopify collection for this, a condition set that works:
product type is one of `fire bowl`, `water bowl`, `planter bowl`,
`planter & water bowl`, AND price < $3,000. That collection becomes the
Pinterest product group on the next 48-hour sync.

## Step 3 — Campaign

| setting | value | why |
|---|---|---|
| objective | **Catalog Sales** | the only objective that uses the feed, so creative comes from product images rather than needing designed assets |
| daily budget | **$20** | Trevor's ceiling |
| ad groups | **exactly one** | Pinterest's own guidance puts $25–50 on a campaign with 2+ ad groups; at $20 a single ad group keeps the spend concentrated enough to learn |
| bidding | automatic to start | minimum manual bids in USD are $0.10 CPC and $5.00 CPM, but there is no reason to hand-set bids before there is data |
| optimisation event | the deepest event with real volume — realistically **AddToCart**, not Purchase | purchases at this AOV will not produce enough signal at $20/day. This is the same trap as the Google remarketing campaign: optimising to an event that never fires means no signal at all |
| targeting | start broad, let the catalog signal work | Catalog Sales builds dynamic retargeting and lookalike delivery from the feed and site events |
| geography | US | matches the Google account's targeting |

Leave it running **at least 2–3 weeks** before judging. Pinterest's
consideration cycle for home projects is long; a week of data says nothing.

## Step 4 — Creative

Catalog Sales pulls product images, so there is little to build. Where creative
is needed:

- aspect ratio **2:3**, **1000 × 1500 px**
- PNG or JPEG, max **20 MB**
- title up to **100 characters**
- description up to **500 characters** — it is not shown to users, it feeds
  Pinterest's relevance matching, so write it for the algorithm

## What to expect

Pinterest will not sell a $12,000 outdoor kitchen to a cold audience. What it
can plausibly do at $20/day, in order of likelihood:

1. build a retargetable audience of people who have seen the products
2. sell some sub-$2k fire and water bowls
3. feed the Google remarketing lists, which is where the high-ticket
   conversions actually close

Judged on last-click purchases in month one it will look like a failure. Judged
on audience built and assisted conversions it may not be. Decide which metric
matters before it starts, not after.

---

## Automation — how I could build this instead

Pinterest has a real Ads API with a Python SDK that supports creating and
managing campaigns, ad groups and ads. It needs:

- a Pinterest developer app
- Business Access on the account
- an access token with the **`ads:read`** and **`ads:write`** scopes

If Trevor creates the app and drops a refresh token into `.env` (gitignored,
exactly as the Google Ads credentials are), then this build becomes a script in
`scripts/` with a dry run and `--execute`, the same shape as every Google Ads
change in this repo — reviewable, repeatable, and no clicking. That is a better
outcome than me driving a browser, and it is the only route by which I can
build it rather than specify it.

## Sources

- https://www.simplepinmedia.com/pinterest-ads-cost/ (budget rules, minimum bids)
- https://www.simplepinmedia.com/how-to-set-up-pinterest-catalogs/ (catalogs, Verified Merchant Program)
- https://help.pinterest.com/en/business/article/promote-your-product-groups (product groups)
- https://business.pinterest.com/blog/your-starter-guide-to-pinterest-shopping-ads-june-2026/ (shopping ads objective)
- https://pinterestadvertisingstuff.com/pinterest-ads-shopify (Shopify app: claim, tag, events, catalog)
- https://www.tailwindapp.com/blog/pinterest-ad-formats/ (creative specs)
- https://developers.pinterest.com/docs/ads/targeting/ and https://dev.pinterest.com/docs/work-with-ads/managing-ads (Ads API)
