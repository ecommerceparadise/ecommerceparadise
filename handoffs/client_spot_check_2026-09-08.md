# Account spot check — 8 September 2026

Google Ads only. The full weekly-ad-report deliverable also needs Shopify and
Microsoft Advertising exports, which are not reachable from this session — the
store-sales, funnel and Microsoft sections are missing from every client block
below and need to be filled in before sending.

---

## The headline, across all five accounts

| account | 7d spend | 7d clicks | 7d conv | 30d spend | 30d conv | 30d CPA |
|---|---|---|---|---|---|---|
| BetterPatio.com | $1,172.30 | 1,620 | **0** | $4,793.47 | 12 | $399.46 |
| Laser Engraver Store | $112.87 | 116 | **0** | $445.51 | **0** | — |
| eCommerce Paradise | $122.64 | 92 | 1 | $411.87 | 1 | $411.87 |
| Culinary Profis | $20.51 | 140 | **0** | $20.51 | **0** | — |
| Fountains USA | $67.47 | 78 | **0** | $67.47 | **0** | — |
| **total** | **$1,495.79** | **2,046** | **1** | **$5,738.83** | **13** | **$441.45** |

**$1,495 spent in the last seven days for one conversion.** That is the finding.
Culinary Profis and Fountains USA show identical 7d and 30d figures because both
were only enabled this week, so their numbers are launch-week noise rather than a
trend. The other three are not.

---

## On the negative keyword pass: there is almost nothing to add

This is worth stating plainly because it is the opposite of what a spot check
usually turns up. Scanning every non-converting search term across all five
accounts against job/repair/used/free/DIY/big-box/non-English/how-to patterns,
then filtering out anything already blocked, anything that would block a term
that has converted, and anything that would block a live keyword:

| account | non-converting terms | spend | genuinely irrelevant |
|---|---|---|---|
| BetterPatio.com | 746 | $1,869.72 | **0** (12 candidates, all already blocked) |
| Laser Engraver Store | 107 | $167.29 | **1** — `mini gravadora a laser portátil` ($1.30) |
| eCommerce Paradise | 48 | $113.19 | **0** |
| Culinary Profis | 0 | $0.00 | — |
| Fountains USA | 0 | $0.00 | — |

One negative added, worth $1.30 a month. **The existing negative lists are doing
their job.** BetterPatio's top non-converting terms are `outdoor kitchen`,
`bull grills`, `blaze grills`, `custom outdoor kitchens`, `primo grills`,
`mont alpi grill` — all on-catalog, all carried brands, all exactly the traffic
that store wants. The money is not going to irrelevant searches. It is going to
**on-target traffic that does not convert**, which negatives cannot fix.

Culinary Profis and Fountains USA returned no search-term rows at all: both are
PMax-only, and PMax reports category labels rather than terms. Those labels came
back empty for every account, so there is no PMax search data to mine anywhere.

### A shared-list hazard worth knowing about

`EP Generic` [11765673294] is **the same list in all five accounts** — identical
id and member count in every one, attached to **14 enabled campaigns across every
client**. Anything added there hits all five simultaneously. That is how
eCommerce Paradise's dropshipping negatives ended up blocking BetterPatio's
converting kitchen terms. Negatives in this pass went to each account's own list
instead:

- BetterPatio.com → `BP Generic Irrelevants` [12052054569]
- Laser Engraver Store → `LES Universal Negatives` [12165888848]
- eCommerce Paradise → `EP Offers Universal Negatives` [12164101696]

Also found: eCommerce Paradise has a list literally named `Generic` (522 members)
that is attached to **nothing live**. Either attach it or retire it.

---

## BetterPatio.com — client block

**Last 7 days:** $1,172.30 · 1,620 clicks · 103,529 impressions · **0 conversions**
**Last 30 days:** $4,793.47 · 4,401 clicks · 12 conversions · $399.46 CPA

| campaign | 30d spend | clicks | conv | CPA | budget |
|---|---|---|---|---|---|
| BP · PMax — Outdoor Kitchens | $691.91 | 1,142 | **0** | — | $110/day |
| Dynamic Display Remarketing Ads | $358.75 | 632 | **0** | — | $20/day |
| BP RT 2: Static Display Remarketing | $245.07 | 251 | 4 | $61.27 | $20/day |
| BP \| Search \| Custom Kitchens LP | $47.49 | 13 | 0 | — | $65/day |

The rest of the 30-day spend came from the old Build Your Own Outdoor Kitchen
campaign before it was paused.

**What happened this week.** The lead campaign stopped serving on 1 September and
lead flow stopped with it. Root cause: it ran Maximize Conversions with a $233.42
target CPA and had gone 14 days without a conversion, so Google stopped bidding.
It has been rebuilt from scratch as `BP | Search | Custom Kitchens LP` — seven
single-keyword ad groups drawn from the terms that actually converted in the last
90 days, manual bids from each keyword's own historical CPC, every ad pointing at
the custom kitchen landing page. Live as of today.

**Do this next**
1. **PMax is the biggest line item and has produced nothing** — $691.91 over 30
   days, 1,142 clicks, zero conversions, at $110/day. This needs a decision, not
   another week.
2. **Dynamic Display Remarketing: $358.75, zero conversions.** The other display
   campaign converted 4 at $61. Pause the one that does not work.
3. Watch the new Search campaign for 48 hours. If impressions are flowing and
   lead-form conversions register, it is working; if it sits at zero impressions
   with everything eligible, the bids are too low for a ~$5 CPC market.
4. Replace the placeholder ad copy with real offer specifics — the headlines
   currently avoid any claim that could not be verified from the account.
5. `Mont Alpi` appears in the search terms with no campaign of its own, and is a
   top-selling brand. Worth a dedicated campaign.

---

## Laser Engraver Store — client block

**Last 7 days:** $112.87 · 116 clicks · **0 conversions**
**Last 30 days:** $445.51 · 511 clicks · **0 conversions**

| campaign | 30d spend | clicks | conv | budget |
|---|---|---|---|---|
| LES - PMax - Lasers (feed only) | $65.28 | 69 | 0 | $15/day |
| LES - Shopping - Retargeting Only | $1.76 | 1 | 0 | $5/day |
| LES - Display Remarketing | $0.00 | 0 | 0 | $5/day |

Most of the 30-day spend predates this week's rebuild, from the seven campaigns
that were paused.

**The thing to resolve first.** The purchase tag has never recorded a
conversion in this account. Until a test order proves it fires, every number here
is unverifiable and Smart Bidding has nothing to learn from. That is the blocker,
ahead of any optimisation.

**Do this next**
1. **Place a test order** and confirm the purchase conversion registers.
2. The search terms are dominated by **FlashForge** and Adventurer 5M queries —
   3D printers. Those products are not in Merchant Center, so the traffic has
   nowhere to land. Either get them into the feed or stop buying the terms.
3. Remarketing lists are still small; the retargeting pair will stay near zero
   until site traffic builds.

---

## Culinary Profis — client block

**Since launch (this week):** $20.51 · 140 clicks · 9,334 impressions · 0 conversions

| campaign | spend | clicks | budget |
|---|---|---|---|
| CP - PMax - Culinary (feed only) | $20.51 | 140 | $15/day |
| CP - Shopping - Retargeting Only | $0.00 | 0 | $5/day |
| CP - Display Remarketing | $0.00 | 0 | $5/day |

All three went live this week, so this is launch-week data. A $0.15 CPC on 140
clicks is a healthy start on cost; conversions are the open question.

**Do this next**
1. **No purchase has been recorded in this account in 90 days.** Same test-order
   check as LES before trusting any conversion number.
2. **Add To Cart is currently a primary conversion goal alongside Purchase.**
   Maximize Conversions weights them equally, so it will chase cheap
   add-to-carts. Purchase should be the only primary goal.
3. The Google Shopping App conversion tag appears to be installed twice —
   duplicate actions suffixed `(1)`, each recording the same events. Remove one set.
4. Three near-duplicate `Pmax feed only` campaigns are still sitting in the
   account paused. Clean them up before one gets switched on by accident.

---

## Fountains USA — client block

**Since launch (this week):** $67.47 · 78 clicks · 6,127 impressions · 0 conversions

| campaign | spend | clicks | budget |
|---|---|---|---|
| FUSA - PMax - Fountains (feed only) | $64.85 | 76 | $15/day |
| FUSA - Shopping - Retargeting Only | $2.62 | 2 | $5/day |
| FUSA - Dynamic Display Remarketing | $0.00 | 0 | $5/day |

**Do this next**
1. Launch-week data only — hold and let it run.
2. **11 active brands still have no asset group** (~2,000 products), so a large
   part of the catalogue is unadvertised. Biggest available upside in this account.
3. Display remarketing has spent nothing. Check the audience is large enough to
   serve before assuming the campaign is broken.

---

## eCommerce Paradise — internal, not a client

**Last 7 days:** $122.64 · 92 clicks · 1 conversion
**Last 30 days:** $411.87 · 228 clicks · 1 conversion · $411.87 CPA

| campaign | 30d spend | clicks | conv | budget |
|---|---|---|---|---|
| EP 5: Niches List Funnel | $195.95 | 151 | 0 | $22/day |
| EP RT 2: Demand Gen Warm | $103.23 | 64 | 1 | $5/day |
| EP RT 3: Display Remarketing | $0.00 | 0 | 0 | $5/day |

EP 5's conversion tracking only went live a few days ago, so the zero is not yet
meaningful — the Klaviyo opt-ins were real, Google just could not see them. Give
it a week of clean data before judging it. The budget is at $22/day, up from $5.

---

## The pattern across all of this

Four of five accounts have recorded zero conversions in the last seven days, and
in at least two of them the conversion tag itself is unproven. Before any further
budget or bidding work, the question worth answering is not "which keywords should
we cut" — the negatives are already clean — but **"can each account actually see a
conversion when one happens."** That is the same problem that took EP's niches
funnel 19 days to surface and stopped BetterPatio's lead campaign serving at all.
