# BetterPatio — landing page fixes for `/pages/custom-outdoor-kitchens`

**For:** whoever has BetterPatio Shopify access (site owner, or the BP Claude Code session)
**From:** the Google Ads side, 2026-09-03
**Campaign:** Build Your Own Outdoor Kitchen (Search) — $45/day, ~$1,226/30 days

## Important caveat

I have not seen this page. Outbound access to betterpatio.com is blocked from
where I work, and I do not have the store's Shopify. Everything below is
inferred from what Google reports *about* the page in the Quality Score data,
plus the search terms people type before they land on it. Treat it as a list of
things to verify, not a list of confirmed defects.

## The signal

Google scores three things per keyword. Here is the last 30 days for every
keyword in this campaign that got enough traffic to be scored:

| keyword | QS | ad relevance | **landing page exp.** |
|---|---|---|---|
| custom outdoor kitchen design | 8 | Above average | **Average** |
| design your own outdoor kitchen | 7 | Above average | **Below average** |
| custom outdoor kitchen | 7 | Above average | **Below average** |
| outdoor kitchen designers | 7 | Above average | **Average** |
| design my outdoor kitchen | 7 | Above average | **Below average** |
| custom built outdoor kitchen | 7 | Above average | **Below average** |
| custom outdoor grill station | 5 | Above average | **Below average** |
| modular outdoor kitchen | 4 | Average | **Below average** |
| complete outdoor kitchen | 4 | Average | **Below average** |
| outdoor kitchens for sale | 3 | Below average | **Below average** |
| custom outdoor grill | 2 | Average | **Below average** |
| outdoor kitchen contractors near me | 1 | Below average | **Below average** |
| outdoor kitchen island | 1 | Below average | **Below average** |

Read the middle column against the right one. On six keywords the **ad** is
rated Above average while the **page** is rated Below average. That rules out
the ad copy as the cause — the ads were rewritten on 2026-09-03 anyway — and
points at the page.

**What it costs:** average CPC is **$4.58**. Landing page experience is one of
the three inputs to Ad Rank, so a Below average score is being paid for on
every single click. 30.2% of available impressions are currently lost to Ad
Rank. Moving this to Average across the board is the cheapest CPC reduction
available on this campaign — it costs nothing per click, unlike raising bids.

## What people actually typed before landing here

Top search terms by spend, last 30 days:

```
outdoor kitchen                       43 clicks   $199
outdoor kitchens                      13 clicks    $86
modular outdoor kitchen               11 clicks    $40
outdoor kitchen kits                  12 clicks    $28
custom outdoor kitchens                2 clicks    $34
outdoor kitchen designer               3 clicks    $29
prefab outdoor kitchens / prefab outdoor kitchen / outdoor kitchen prefab
ready to assemble outdoor kitchens
outdoor kitchen installers near me
build my own outdoor kitchen / building an outdoor kitchen
outdoor kitchen planner / design outdoor kitchen online
```

Every one of these is a legitimate, on-topic query. There is no junk traffic to
filter here — 483 terms reviewed, and the ones that did not convert are still
the right kind of person. The traffic is good; the page is not converting it.

## What to change, in priority order

### 1. Put the query language above the fold
The single most common query is literally **"outdoor kitchen"** and
**"outdoor kitchens"** (56 clicks, $286 in 30 days). The next cluster is
*modular*, *prefab*, *kits*, *ready to assemble*. If the H1 does not contain
"Custom Outdoor Kitchens" and the visible copy above the fold does not use the
words *modular*, *prefab*, and *built to your specs*, the visitor's first
half-second does not confirm they are in the right place. Google's crawler
reads this the same way a visitor does.

### 2. Form above the fold, and shorter
This page's entire job is the lead form — it is the only conversion action the
campaign bids on (11 lead form submits in the last 30 days). Requirements:
- Visible without scrolling on mobile.
- Name, email, phone, ZIP, and one free-text "what are you building". Nothing else.
- No account creation, no address, no budget dropdown before submit.
- Submit button says what they get: **"Get My Free 3D Rendering"**, not "Submit".

### 3. Make the three claims the ads make
The new ads promise these, so the page must state them plainly or the visit
breaks trust and Google marks it down for relevance:
- **Free 3D rendering** of your kitchen before you commit
- **Free design consultation**, no obligation
- **Free shipping to the lower 48**, financing available on qualifying orders

### 4. Page speed on mobile
Below average landing page experience is very often mobile load time on Shopify
when a page carries large uncompressed renders. Run PageSpeed Insights on
`/pages/custom-outdoor-kitchens`. Target LCP under 2.5s on mobile. The usual
culprits: hero images not served as WebP, no width/height attributes, and
app scripts loading before content.

### 5. Original, substantive content
Google rates "useful, original content" as part of this score. The page should
carry things a category page does not: real project photos with dimensions,
the actual build process and lead time, material options, a price range, and
answers to what people ask before they call.

### 6. Working navigation and transparency
Cheap and frequently missed: visible phone number, a real About/Contact path,
shipping and return policy reachable from the page, and no dead links.

## How to tell it worked

Re-check Quality Score 2–3 weeks after the changes ship. Success is landing
page experience moving from **Below average** to **Average** on the six
keywords where ad relevance is already Above average. Average CPC should fall
from $4.58, and impression share lost to Ad Rank should fall from 30.2%.

Ask the Google Ads side to re-run `scripts/audit_bp_search.py` — it prints this
exact table.
