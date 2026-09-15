# BetterPatio — feed coverage in the ads, 15 September 2026

## The number

The only enabled feed campaign, `BP · PMax — Outdoor Kitchens` [24209664922]
at $110/day, can serve **222 of 10,771 eligible products — 2.1%**.

| | products |
|---|---|
| reachable by the live PMax | 222 |
| right brand, product type still excluded | 63 |
| brand has no asset group at all | 10,486 |

Feed health is good: 10,771 eligible, 438 blocked (303 out of stock,
115 landing page errors, the rest image issues). The catalogue is fine.
The ads just never grew with it.

## Why

The PMax has three asset groups — Mont Alpi, Cal Flame, BetterPatio House
Brands. Each filters brand -> product_type and originally admitted only
`bbq island`, `bbq island accessories` and `outdoor kitchens`.

On 15 Sept the in-theme excluded types were added back (grills, refrigerators,
doors & drawers, griddles, pizza ovens, kegerators, bar islands, modular
cabinets, grill carts, power burners): +64 products, 158 -> 222. Fireplaces,
fire pits, spas, entertainment centres and patio furniture were deliberately
left out — wrong campaign.

That is the ceiling for this campaign. The remaining 10,486 products are in
45 brands with no asset group, and most are **not outdoor kitchen products**:

| brand | eligible | what it is |
|---|---|---|
| The Outdoor Plus | 5,583 | fire & water bowls, fire pits |
| Panama Jack Outdoor | 1,369 | dining / living / sectional sets |
| Hospitality Rattan Patio | 1,245 | outdoor dining sets, sectionals |
| Anderson Teak | 614 | benches, deep seating |
| Chicago Brick Oven | 212 | pizza ovens |
| Skyline Design | 194 | club chairs, daybeds, sofas |
| Fire Pit Art | 161 | fire pits |
| RCS | 99 | grills, doors & drawers |
| Bull | 83 | bbq islands and grills |
| Summerset | 76 | grills |
| Fire Magic | 66 | grills |
| Blaze | 49 | grills |
| Coyote | 44 | grills |

Pushing furniture and fire bowls into an outdoor-kitchens PMax would wreck its
focus. They need their own home.

## What already exists, and why it does not work

**14 paused per-brand PMax campaigns** (`Pmax - blaze`, `Pmax - coyote outdoor
living`, `Pmax - fire pit art`, `all other brands`, …) are **empty shells**:
one asset group each, **0 headlines, 0 descriptions, 0 images, 0 logos**,
ad strength POOR, final URL the homepage. Enabling them spends budget and
serves nothing. Each needs a full creative build before it is worth anything.

**4 paused Shopping campaigns are fully built** — product ads present, brand
product groups in place. Shopping needs no creative; it serves from the feed.
But the bids tell the story:

`BP 2: Brands - All Brands` [24040800434], $90/day, 38 product groups:

| | brands | eligible products |
|---|---|---|
| bid > $0 | 25 | 1,022 |
| **bid = $0.00** | **13** | **9,291** |

Every big expansion brand is bid at zero: The Outdoor Plus (5,583), Panama
Jack Outdoor (1,369), Hospitality Rattan Patio (1,245), Anderson Teak (614),
Skyline Design (194), Fire Pit Art (161), Dimplex (70), MirageVision (27),
Douglas Nance (20). A $0 bid cannot enter an auction. On top of that,
**19 more feed brands have no product group at all** (458 products), including
Big Ridge Outdoor Kitchens (53), Napoleon (49), Panama Jack Sunroom (90),
Hospitality Rattan Home (60).

So the expanded catalogue has never been advertised: zero-bid where it is
represented, absent where it is not, and the whole campaign paused regardless.

## Recommended path

1. **Shopping, not PMax, for the long tail.** One Shopping campaign covering
   the whole catalogue needs no creative and is the natural fit for 10,771
   products. Set real bids on the 13 zero-bid brands, add product groups for
   the 19 missing ones, then enable.
2. **Keep the PMax focused** on outdoor kitchens. It is now correct for what
   it is meant to sell.
3. **Build creative before enabling any per-brand PMax.** The 14 shells are
   traps — they will spend and not serve.
4. Separately: the PMax still bids to PURCHASE only (5 fires/90d) while
   Submit Lead Form fires 48. Unresolved.

## Blocked on a decision

Setting bids and enabling campaigns both change spend, so neither was done.
`BP 2: Brands` is $90/day, `BP 1: Generic` $90/day, `BP 3: Products` $90/day.
Needs a budget and a starting bid per brand tier.

---

# Update — feed-only PMax built, 15 September 2026

## Correction to the note above

The claim that the 14 paused per-brand PMax shells "will spend and not serve"
was **wrong**. Zero-asset PMax is exactly how feed-only campaigns work, and it
is the pattern already running in the other three accounts. `FUSA - PMax -
Fountains (feed only)` has four asset groups with **0 assets and POOR ad
strength**, primary status **ELIGIBLE**, and delivered 16,768 impressions /
169 clicks / $215.15 over 30 days. With no creative, PMax has no display or
video ad to assemble, so it serves Shopping inventory from the feed.

Those 14 shells still are not the right vehicle — they cover 14 brands, not 54,
at $10/day each — but the reason is coverage and budget, not inability to serve.

## What was built

`BP · PMax — All Brands (feed only)` [24258810910], **PAUSED**, $50/day.

| | |
|---|---|
| asset groups | 25 (24 named brands + 1 catch-all), no assets |
| products reachable | **10,486 of 10,771** |
| bidding | Maximize Conversions, no target CPA |
| conversion goal | Purchase / Website (inherited from the account) |
| geo | same 48 locations as the kitchens campaign, PRESENCE |
| Merchant Center | 101451631, brand guidelines on |

Brands with 20+ eligible products get their own asset group: The Outdoor Plus
(5,583), Panama Jack Outdoor (1,369), Hospitality Rattan Patio (1,245),
Anderson Teak (614), Chicago Brick Oven (212), Skyline Design (194), Fire Pit
Art (161), RCS (99), Panama Jack Sunroom (90), Bull (83), Summerset (76),
Dimplex (70), Fire Magic (66), Hospitality Rattan Home (60), Big Ridge (53),
Napoleon (49), Blaze (49), Coyote (44), Le Griddle (29), MirageVision (27),
Primo Ceramic Grills (22), Mayne (21), Douglas Nance (20), American Outdoor
Grill (20).

`BP · All Other Brands` holds the remaining 22 brands / 230 products via an
"everything else" include, with explicit excludes for the 24 named brands and
the 9 kitchens brands. **New brands added to the feed are advertised
automatically** — no rebuild needed.

The nine brands served by `BP · PMax — Outdoor Kitchens` (285 products) are
deliberately excluded so the two campaigns never bid against each other.
That campaign keeps its creative, search themes and video.

## Two API rules learned the hard way

The first build attempt created the campaign, budget, geo and all 25 asset
groups, then failed on the listing trees and left them empty.

1. A SUBDIVISION and its children must be created in **one** mutate using
   temporary resource names (negative ids). A bare subdivision is rejected
   with "SUBDIVISION node must have everything else child", and because the
   request is atomic, one bad operation rolls back all 25.
2. The "everything else" sibling must declare its dimension. Touching an
   empty proto3 message does not set the oneof, so it needs an explicit
   `SetInParent()` with no value.

Tree building now lives in `complete_bp_feedonly_listing_groups.py`, which is
idempotent and skips asset groups that already have a tree.

## Before enabling — needs a decision

- **Budget.** $50/day is a placeholder. The kitchens PMax is $110/day.
- **Purchase is the only conversion goal and it fires ~5 times per 90 days.**
  Maximize Conversions has very little to learn from. This campaign will be
  slow to leave learning, and that is the same underlying problem flagged
  three times already in this account.
