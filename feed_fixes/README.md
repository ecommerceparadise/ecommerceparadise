# Feed fixes

Merchant Center data problems found while building campaigns. These are fixed
at the source (the store, or a Merchant Center supplemental feed) — the Google
Ads API cannot write product data, `shopping_product` is a read-only reporting
resource.

## BetterPatio.com — missing brand attribute

`betterpatio_missing_brand.csv` — 27 products, 95 variants, out of 447 products
and 904 variants in feed 101451631.

**Not a systemic mapping failure.** The same manufacturers appear both with and
without a brand: Cal Flame 45 products branded / 13 not, Bull 32 / 9. If the
channel's field mapping were broken, nothing would carry a brand.

**Brand is being set per variant, not per product.** Two products
(8762322911473, 8769816756465 — the Ufinish build-your-own configurators) have
variants that disagree with each other, one of them carrying three different
values including blank:

    8762322911473  ->  '', 'betterpatio unfinished outdoor kitchens',
                       'ufinish by betterpatio outdoor kitchens'

Shopify's Vendor field is product-level, so it cannot produce that. Something
variant-level is supplying brand — Google Shopping metafields, a feed app, or a
partial supplemental feed — and it has only been filled in on some variants.
Those two products alone account for 67 of the 95 blanks.

Confirming which of those it is requires access to the store or to Merchant
Center; it was inferred here from the Google Ads read side only.

`set_brand_to` is the canonical value for each product, chosen to match the
spelling already dominant in the feed. 26 of 27 are inferable from the product
title. One is not: product 7539388154097, titled only "New Combo" ($2,099) —
that one needs a human to identify, and looks like a placeholder worth checking.

## BetterPatio.com — brand values fragmented across spellings

Separate from the blanks, and arguably worse for targeting, since these
products *look* fine in the feed:

| Manufacturer | Products | Distinct brand strings |
|---|---|---|
| BetterPatio house | 43 | 6 — `betterpatio.com` 25, `betterpatio mountain series` 6, `betterpatio designer series` 4, `ufinish by betterpatio outdoor kitchens` 4, `betterpatio` 3, `betterpatio solace series` 1 |
| Bull | 32 | 2 — `bull` 29, `bull bbq` 3 |

Every brand-based listing filter has to enumerate all six strings to reach the
house catalogue, and any spelling added later silently falls out of targeting.
Series names belong in `product_type` or a custom label, not in `brand`.
