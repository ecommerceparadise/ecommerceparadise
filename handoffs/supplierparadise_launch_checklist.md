# supplierparadise.com — pre-launch checklist

High-ticket dropshipping supplier directory. Funnel, email, outreach and tracking
all land **before** paid traffic. Sequenced so nothing blocks on something built
later.

---

## Phase 0 — decisions that block other work

- [ ] **Price and model for the directory** — one-time, subscription, or free tier
      into paid. Everything downstream (funnel shape, bid targets, whether cold
      Search is even viable) depends on this number.
- [ ] **Which Google Ads account** — new account, or a campaign inside
      eCommerce Paradise (7871916737). If new, add the ID to
      `managed_accounts.json` or my tooling refuses to touch it.
- [ ] **What platform supplierparadise.com runs on** — WordPress / Shopify /
      custom. Changes how Google login and gclid capture get implemented.
- [ ] **Pick one home for supplier intent.** EP already sells the High Ticket
      Supplier Brand Distributor Directory on shop.ecommerceparadise.com. Two of
      your properties bidding the same keywords is a double-serving exposure and
      inflates your own CPCs on a term that already costs ~$10.

---

## Phase 1 — funnel

- [ ] Squeeze page — lead magnet only, no navigation, single call to action
- [ ] Lead magnet itself (free slice of the directory, e.g. "50 verified
      high-ticket suppliers")
- [ ] Site-wide pop-up offering the same lead magnet
- [ ] Delivery + sales page — directory buy button
- [ ] Upsell 1 — coaching (DWY)
- [ ] Upsell 2 — DFY
- [ ] Email sequences: delivery → nurture → directory pitch → coaching → DFY
- [ ] Additional site features

**Note:** the squeeze page will out-convert the home page substantially. Plan for
it to take most of the ad budget, not the home page.

---

## Phase 2 — accounts and Google login

- [ ] Google Sign-In for member accounts
- [ ] **Separate OAuth client — do NOT reuse the Google Ads API client.** Different
      consent screen, different audience, and mixing a public consumer login with
      a client that has write access to your and your clients' ad accounts is a
      bad blast radius.
- [ ] **Rotate the Google Ads API client secret and refresh token.** Outstanding
      since early in this project; they have been sitting in a chat transcript.
      Standing up the new public OAuth client is the natural moment.
- [ ] Store `gclid` on the user record at signup — permanent, and removes the
      Safari cookie-durability problem entirely
- [ ] A/B test gated vs ungated lead magnet. Google login is low friction but
      "sign in to get the free list" still converts worse than an email field. At
      a $10 CPC that delta matters — don't assume, measure.

**Why this is worth more than it looks:** Google Sign-In gives you the user's
actual Google account email, which is exactly the key Enhanced Conversions
matches on. It turns attribution from "hopefully they used their Gmail" into
near-deterministic matching.

---

## Phase 3 — tracking (the gate — no ads before this is verified)

- [ ] Google tag on supplierparadise.com, routed to the right `AW-` ID
- [ ] Conversion actions created, **each carrying a real value**:
      `sign_up` → `directory_purchase` → `coaching_close` → `dfy_close`
- [ ] PayPal **Auto Return** enabled (Account Settings → Website payments →
      Website preferences) pointing at a thank-you URL
- [ ] PayPal **Payment Data Transfer (PDT)** enabled so transaction ID and amount
      come back with the redirect — fire the purchase conversion with real value
- [ ] PayPal webhook/IPN → Zapier → sheet → **daily offline upload job** as the
      reliable backfill (Auto Return is leaky: closed tabs, guest checkout)
- [ ] **Dedupe on the PayPal transaction ID as `order_id`** so a sale caught by
      both layers counts once
- [ ] Authorize the PayPal connector in claude.ai connector settings — currently
      unauthorized, so I can't inspect the setup
- [ ] Customer Match audience from the member list (remarket free members, exclude
      existing buyers from acquisition, seed lookalikes)
- [ ] Plan for **Maximize Conversion Value**, not Maximize Conversions — the funnel
      spans ~$97 to $5,000+, and equal-weighted conversions will optimise toward
      the cheapest one

**The offline upload job is a shared dependency.** It serves EP's niches funnel,
supplierparadise's PayPal sales, and the coaching/DFY closes that happen on calls
days later. Build once, point at three sources. Spec:
`handoffs/ep_gclid_capture_spec.md`.

---

## Phase 4 — outreach (Gmail / GMass to HTDS stores)

- [ ] **Send from a separate domain — not `ecommerceparadise.com`.** Klaviyo sends
      your marketing from `send.ecommerceparadise.com`; cold outreach from the
      root domain can drag the organisational reputation that subdomain partly
      inherits. Sending from `@supplierparadise.com` is natural here and isolates
      the risk completely.
- [ ] Warm the new domain before volume — 2–4 weeks ramping. You've done this
      before (`Warm-up Batch 1` in Klaviyo).
- [ ] SPF / DKIM / DMARC on the new sending domain
- [ ] **Consider Apollo.io instead of GMass** — already connected and paid for,
      with native sequences, a B2B contact database, and better deliverability
      handling than a Gmail bolt-on. GMass is fine if you prefer it; just don't
      pay for both.
- [ ] **One prospect tracker, not three.** `client-prospecting` and
      `htds-affiliate-first-prospecting` already target the same HTDS store
      universe. Hitting the same inbox with a services pitch and a supplier-directory
      pitch from two systems burns the relationship and your domain.
- [ ] CAN-SPAM basics: real physical address, working opt-out, accurate headers.
      Stricter rules if you're mailing UK/EU (GDPR) or Canada (CASL) stores.
- [ ] **Log every objection and reply verbatim.** This is free market research —
      the objections you hear become your ad headlines and squeeze page copy
      before you pay $10/click to learn the same thing.
- [ ] Never send cold outreach through Klaviyo — wrecks the sending domain and
      breaches their terms.

---

## Phase 5 — ads (only once Phase 3 is verified working)

- [ ] **Search only at launch.** No PMax, Display or Demand Gen for cold traffic —
      a new domain has no conversion history, so PMax will spend the budget
      discovering that cheap junk placements are cheap.
- [ ] Campaign 1 — **Competitor conquest** (launch first, cheapest, sharp intent):
      `salehoo alternative`, `worldwide brands alternative`, `wholesale2b alternative`,
      `high ticket supplier hq`, `salehoo review`
- [ ] Campaign 2 — **Niche supplier long tail** (launch first, $1–2 CPCs):
      `sauna dropshipping suppliers`, `furniture dropshipping suppliers`, one SKAG
      per niche the directory covers well
- [ ] Campaign 3 — **Core directory intent** (launch last, ~$10 CPC):
      `high ticket dropshipping suppliers`, `dropshipping supplier directory`,
      `high end dropshipping suppliers`, `luxury dropshipping suppliers`
- [ ] Matched landing pages per theme — home page for the core term only. Sending
      everything to the home page breaks *search term = ad headline = landing page
      headline*, and at $10/click that rule is the difference between profit and a
      hobby.
- [ ] **Do NOT attach EP's negative lists.** Verified they're campaign-scoped
      (10 campaigns each, zero account-level negatives) so nothing inherits
      automatically — but `EP Offers Universal Negatives` contains `salehoo`,
      `doba`, `worldwide brands`, `wholesale2b`, `inventory source`,
      `spark shipping`, `modalyst`, `syncee`. Those are waste for a niches funnel
      and **exactly your conquest keywords** here.
- [ ] Location targeting = **Presence**, never Presence-or-interest
- [ ] Campaigns created **paused**; confirm daily budget and target cost-per-lead
      before enabling
- [ ] Ad copy: you may bid on competitor brand terms, but **cannot use their
      trademarks in the ad text**
- [ ] Graphics and video assets — build them, but point them at *remarketing*
      once there's an audience, not cold PMax on day one
- [ ] Revisit PMax only after 30+ verified conversions/month

### Real CPC data from your own account (all time, 23 supplier queries, $42.68)

| query | cost | clicks | CPC |
|---|---|---|---|
| dropshipping suppliers | $19.71 | 2 | **$9.86** |
| high ticket dropshipping suppliers usa | $9.72 | 2 | $4.86 |
| luxury dropshipping suppliers usa | $3.65 | 1 | $3.65 |
| high end dropshipping suppliers | $3.00 | 2 | $1.50 |
| high ticket dropshipping suppliers | $5.01 | 4 | $1.25 |

Zero conversions across those 12 clicks — but that traffic hit niches-list and DFY
pages, and EP's tracking was blind at the time. Landing-page mismatch, not a
verdict on the intent.

---

## Carry-over, not part of this build

- [ ] **EP 5 is at $22/day** into a funnel whose tracking only just went live.
      Give it a few days of real conversion data before touching budget or bidding.
- [ ] **EP Homepage Hero form** still invisible to tracking — posts server-side to
      the Klaviyo API, emits no `klaviyoForms` event. Not in WPCode; likely an
      Elementor widget. Needs locating and patching.
- [ ] Worth eyeballing: Klaviyo reports `send.ecommerceparadise.com` as **active**
      but its DNS records show `verified: false`. Probably a reporting artifact of
      dynamic sending-domain delegation — but cheap to confirm in the Klaviyo UI
      before you lean harder on email.

---

## The one risk in this plan

The list ahead of "run ads" has grown to five workstreams: funnel, email, Google
login, site features, and outreach. Each is justified on its own, and the
sequencing logic is sound. But that's plausibly months, and the failure mode for
this shape of plan is that the ads never launch.

If you want a forcing function: **Phase 3 (tracking) plus a squeeze page and one
email sequence is enough to run Campaign 1 profitably.** Google login, site
features and the full upsell ladder can land while traffic is already flowing and
teaching you things. The outreach in Phase 4 doesn't block ads at all — it runs in
parallel and makes the ad copy better.
