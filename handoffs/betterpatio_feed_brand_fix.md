# Task: fix the brand attribute in the BetterPatio.com product feed

You have access to the BetterPatio.com Shopify store. I'm handing you a
diagnosis made from the Google Ads side (Merchant Center feed 101451631,
Google Ads account 652-667-4673). I could read the feed but never saw the
store, so **treat everything below as a hypothesis to verify, not fact.**

## The problem

447 products / 904 variants in the feed. **27 products / 95 variants carry no
`brand` attribute at all.** Anything without a brand cannot be reached by a
brand-based listing filter, so it's invisible to brand-segmented Performance
Max and Shopping campaigns. We're rebuilding the account around brand-level
asset groups, so these products are currently unsellable through paid.

It is NOT a broken field mapping. The same manufacturers appear on both
sides — Cal Flame has 45 products with a brand and 13 without, Bull has 32
and 9. If the channel mapping were wrong, nothing would carry a brand.

## The key clue — please confirm or refute this first

Two products have variants that **disagree with each other on brand**:

    product 8762322911473 → variant brand values are:
        ''  (blank)
        'betterpatio unfinished outdoor kitchens'
        'ufinish by betterpatio outdoor kitchens'

    product 8769816756465 → variant brand values are:
        ''  (blank)
        'ufinish by betterpatio outdoor kitchens'

Shopify's **Vendor field is product-level**, so Vendor alone cannot produce
three different brand values within one product. Something **variant-level**
is supplying brand and has only been populated on some variants.

**Your first job is to find out what that something is.** Likely candidates:

1. Google Shopping metafields on variants (legacy `mm-google-shopping.brand`,
   or whatever namespace the current Google & YouTube channel uses)
2. A third-party feed app (Feed for Google Shopping, Simprosys, DataFeedWatch,
   etc.) with per-variant rules or overrides
3. A supplemental feed already configured in Merchant Center, partially applied

Check in this order: what the Google & YouTube channel is configured to map
`brand` from; then whether variant metafields exist; then the installed app
list. **Report what you find before making any changes** — the right fix
depends on the answer, and if brand is coming from a metafield or a feed app,
setting the Vendor field will do nothing.

These two products alone are 67 of the 95 blanks, so fixing them clears ~70%
of the problem.

## Job 1 — fill the 27 blanks

Set brand to the value in the middle column. These values were chosen to match
the spelling already dominant in the feed, so don't "improve" them — matching
the existing spelling is the whole point.

| Shopify product ID | Set brand to | Variants | Top price | Title |
|---|---|---|---|---|
| 8769816756465 | Ufinish by BetterPatio Outdoor Kitchens | 24 | $17,600 | Ufinish … Build Your Own Unfinished L-Shaped Outdoor Kitchen |
| 8762322911473 | Ufinish by BetterPatio Outdoor Kitchens | 43 | $15,822 | Ufinish … Build Your Own Unfinished Linear Outdoor Kitchen |
| 9370738589937 | BetterPatio.com | 1 | $10,515 | BetterPatio.com SUMMERSET PEACHTREE ISLAND COPI8-1 (C,R,L) |
| 9370756677873 | BetterPatio.com | 1 | $10,515 | BetterPatio SUMMERSET PEACHTREE ISLAND COPI8-1 |
| 463532363 | Cal Flame | 1 | $9,999 | Cal Flame Malibu Q 8 Ft. BBQ Island L-Shaped - BBK830 |
| 463420367 | Cal Flame | 1 | $8,499 | Cal Flame Bel Air Q 8 ft. BBQ Island - BBK810 |
| 5507221848232 | Cal Flame | 1 | $8,499 | Cal Flame 8 Foot L-shaped Design Your Own BBQ Island Carmel |
| 463421807 | Cal Flame | 1 | $8,299 | Cal Flame Avalon Q 8 Ft. BBQ Island L-Shaped - BBK820 |
| 463417007 | Cal Flame | 1 | $7,999 | Cal Flame Atlantic Q 8 ft. BBQ Island - BBK801 |
| 463416551 | Cal Flame | 1 | $6,999 | Cal Flame 7 foot BBQ Grill Island with 4-Burner Gas Grill |
| 6254752858280 | Cal Flame | 1 | $6,499 | Cal Flame 7 foot Wood Panel Grill Island with Tile Top |
| 7993950208241 | Cal Flame | 1 | $6,499 | Cal Flame 7 foot BBQ Island with Four Burner Grill, Fridge |
| 463534043 | Cal Flame | 1 | $6,299 | Cal Flame Maui Q 4 Ft. L-Shaped BBQ Island |
| 461348999 | Cal Flame | 1 | $5,999 | Cal Flame Pacifica Q 7 ft. BBQ Island - BBK701 |
| 461348715 | Cal Flame | 1 | $5,199 | Cal Flame Kona 6 Ft. BBQ Island |
| 910127555 | Bull | 1 | $5,039 | Bull Brahma Grill and Cart with Lights |
| 1310717378631 | Cal Flame | 1 | $4,999 | Cal Flame Kauai Q 4 Ft. L-Shaped BBQ Island |
| 7492053074161 | Cal Flame | 1 | $4,999 | Cal Flame 7 foot Cultured Stone Grill Island |
| 910161731 | Bull | 1 | $4,685 | Bull Extra Large Pizza Oven (oven only) 66040 |
| 910160707 | Bull | 1 | $4,500 | Bull Large Pizza Oven Cart (cart only) 66039 |
| 910051971 | Bull | 1 | $3,299 | Bull Lonestar Select Gas Grill and Cart |
| 910050755 | Bull | 2 | $2,919 | Bull Outdoor Outlaw 30 Inch Grill with Cart |
| 911837507 | Bull | 2 | $2,439 | Bull Bull Steer Premium Grill and Cart |
| 4965723242636 | Bull | 1 | $2,349 | Bull Steer Premium Grill and Cart 69102 |
| **7539388154097** | **STOP — ask Trevor** | 1 | $2,099 | **"New Combo"** |
| 5763910959272 | Bull | 2 | $1,609 | Bull Steer Premium 24-Inch Drop In Gas Grill |
| 910159491 | Bull | 1 | $729 | Bull Insulated Grill Jacket for 38" Brahma Grills 47018 |

Product **7539388154097** is titled only "New Combo" with no manufacturer
anywhere in it. Do not guess a brand for it. Look at the product, and if you
can't identify it confidently, ask Trevor — it may be a placeholder that
should be archived rather than fixed.

Note products 9370738589937 and 9370756677873 look like **duplicates of each
other** (same Summerset Peachtree island, same $10,515). Flag that; one may
need archiving rather than branding.

## Job 2 — consolidate the fragmented brand values

Separate problem, arguably worse, because these products *look* fine in the
feed. The same manufacturer is split across multiple brand strings:

| Manufacturer | Products | Current strings |
|---|---|---|
| BetterPatio house | 43 | `betterpatio.com` (25), `betterpatio mountain series` (6), `betterpatio designer series` (4), `ufinish by betterpatio outdoor kitchens` (4), `betterpatio` (3), `betterpatio solace series` (1) |
| Bull | 32 | `bull` (29), `bull bbq` (3) |

Every brand filter has to enumerate all six spellings to reach the house
catalogue, and any new spelling silently drops out of targeting.

Consolidate Bull to a single `Bull`. For the house catalogue, consolidate to a
single brand — **but do not lose the series names.** Mountain / Designer /
Solace / Ufinish are real product lines and we want them for segmentation.
Move them into `product_type` or a custom label before flattening `brand`, and
tell me which field you used so the campaign side can target on it.

Confirm the consolidation plan with Trevor before running it. It touches 75
products that are currently serving fine, so it carries more risk than Job 1.

## Rules

- **Do Job 1 first, verify it in Merchant Center, then do Job 2.** Don't batch
  them — if something breaks we need to know which change did it.
- Make no other catalogue edits. Not titles, prices, descriptions, images,
  inventory, or status. Brand/vendor and (for Job 2) the series field only.
- Changed products go back through Merchant Center review. Expect a lag before
  they're eligible again; that's normal, not a failure.
- If the store is the client's rather than Trevor's, confirm you're authorised
  to write to it before the first edit.
- Report what you changed and what you found about the brand source. The Google
  Ads side needs both: the campaign build is currently written to enumerate all
  six house spellings, and that has to be rewritten once this is clean.

## Verify when done

Query the feed and confirm zero products with a blank brand, and that the house
catalogue and Bull each resolve to one value. Merchant Center's diagnostics
will lag; the authoritative check is the feed contents, not the campaign side.
