# eCommerce Paradise — Klaviyo niches opt-in → Google Ads conversion tracking

## The problem

Klaviyo has **no conversion feed to Google Ads**. It integrates with Meta and
TikTok via their CAPI, but there is no Google Ads equivalent. So the `/niches/`
landing page was converting well while Google Ads reported zero, and Smart
Bidding had nothing to optimise toward.

Evidence (pulled 2026-09-05):

| | last 30 days |
|---|---|
| Niches List – Embed (`/niches/`, form `TngeTU`) | 697 unique viewers → **118 submits, 12.07%** |
| Niches List – Popup (site-wide, form `VJCEJJ`) | 6,684 unique viewers → 69 submits, 0.95% |
| `Niches List Leads` opt-ins | **137 in August, 29 in Sept 1–5** |
| EP 5: Niches List Funnel conversions in Google Ads | **0, nineteen straight days** |

The submit events carry `page_url`, `form_id`, `device_type` and Klaviyo's own
`cid` — but **no `gclid` / `wbraid` / `gbraid`**. Klaviyo does capture UTM
parameters when present (one recent signup carries `utm_source: perplexity`),
but Google auto-tagging appends `gclid`, which is not a UTM parameter and which
Klaviyo's onsite script does not store. So the offline-import route was closed
too, and no `UPLOAD_CLICKS` conversion action existed.

## What is already done (Google Ads side — live)

Created in eCommerce Paradise (`7871916737`) by
`scripts/create_ep_niches_conversion.py`:

```
[7748493747] Niches List Opt-In (Klaviyo)
  type     WEBPAGE
  category SUBMIT_LEAD_FORM
  counting ONE_PER_CLICK
  window   30 days click-through
  primary  True  (counts in "Conversions", biddable)
  send_to  AW-11096777331/6SdbCLPD4u4cEPPErasp
```

Why this was safe to mark primary:

- `SUBMIT_LEAD_FORM/WEBSITE` was **already** a biddable goal at account level
  and on every enabled campaign, so this joins an existing goal rather than
  creating a new one.
- **EP 5: Niches List Funnel** is `MANUAL_CPC` — no bidding effect today, it is
  purely reporting until the strategy changes.
- **EP RT 2: Demand Gen Warm** is `MAXIMIZE_CONVERSIONS` with
  `SUBMIT_LEAD_FORM` biddable, so it **will** begin optimising toward these
  opt-ins once they start arriving. That is the intended outcome, but it is a
  real behavioural change worth watching for the first week.

No conversion value is set. If a niches-list lead is later found to be worth a
consistent amount, add a default value and value-based bidding becomes possible.

## What is left (site side — needs to be pasted by hand)

The snippet below could not be installed automatically: writing executable PHP
into the live site was blocked by the session's permission classifier. It takes
about two minutes to add manually.

### Prerequisite already satisfied

Site Kit's Google tag `GT-MKPF9XJ` already routes to **both** destinations:

```
googleTagContainerDestinationIDs: ["G-N8ESK51P34", "AW-11096777331"]
```

So `AW-11096777331` is already loaded on every page and **no extra gtag config
is needed**. The snippet only has to fire the event.

Note: Site Kit has `trackingDisabled: ["loggedinUsers"]`, so **test while logged
out** — logged in, `gtag` is absent and the snippet correctly no-ops.

### Install

WordPress admin → **Code Snippets (WPCode) → Add Snippet → Add Your Custom Code**

- **Title:** `Google Ads Conversion - Klaviyo Niches Opt-In`
- **Code Type:** `PHP Snippet`
- **Location:** `Run Everywhere`
- **Priority:** `10`
- Paste the code below, toggle **Active**, Save.

```php
// Google Ads conversion tracking for the Klaviyo niches-list opt-in.
//
// Klaviyo has no conversion feed to Google Ads, so the /niches/ landing page
// was converting (12% submit rate) while Google Ads recorded zero. This fires
// the "Niches List Opt-In (Klaviyo)" conversion action when a Klaviyo form is
// submitted, plus a GA4 generate_lead event.
//
// The Site Kit Google tag (GT-MKPF9XJ) already routes to AW-11096777331, so
// no additional gtag config is needed here. If Site Kit is ever disconnected,
// gtag will be absent and this snippet simply no-ops.

if ( is_admin() ) {
    return;
}

$ep_niches_ads_tag = function () {
    ?>
<script>
(function () {
  // Klaviyo form ids for the niches list: embed (on /niches/) and site-wide popup.
  var FORMS   = { TngeTU: 'embed', VJCEJJ: 'popup' };
  var SEND_TO = 'AW-11096777331/6SdbCLPD4u4cEPPErasp';
  var fired   = {};

  window.addEventListener('klaviyoForms', function (e) {
    if (!e || !e.detail || e.detail.type !== 'submit') { return; }

    var id = e.detail.formId;
    if (!FORMS[id]) { return; }   // not a niches-list form
    if (fired[id])  { return; }   // Klaviyo can emit submit twice per page
    fired[id] = true;

    if (typeof window.gtag !== 'function') { return; }

    window.gtag('event', 'conversion', { send_to: SEND_TO });
    window.gtag('event', 'generate_lead', {
      lead_source: 'klaviyo_niches_list',
      form_placement: FORMS[id]
    });
  });
})();
</script>
    <?php
};

// Normally this snippet runs well before the footer; the direct call is a
// fallback in case it is ever executed after wp_footer has already fired.
if ( did_action( 'wp_footer' ) ) {
    $ep_niches_ads_tag();
} else {
    add_action( 'wp_footer', $ep_niches_ads_tag, 20 );
}
```

### Design notes

- **Only the two niches-list forms fire.** Any other Klaviyo form on the site is
  ignored, so this will not start double-counting if more forms are added.
- **Duplicate submits are suppressed per page load.** Klaviyo genuinely emits
  `submit` twice for some visitors — two signups in the sampled event data are
  the same person seconds apart — and without the `fired` guard those would be
  double-counted at the tag level.
- **Fails closed.** If `gtag` is missing for any reason the snippet does
  nothing rather than erroring.
- **Two signals, deliberately.** The direct `AW-` conversion is fast and
  reliable. The GA4 `generate_lead` event is redundant insurance — GA4 is
  already linked to Ads (`adsLinked: true`) with `generate_lead` a detected
  conversion event — but it arrives with GA4's processing latency, so the
  direct conversion is the one to trust.

### Verify

1. Log out (or use a private window) and submit the form on `/niches/`.
2. Google Ads → Goals → Conversions → **Niches List Opt-In (Klaviyo)**. Status
   moves from "No recent conversions" to "Recording conversions" within a few
   hours; the count itself can take up to ~24h to surface.
3. Cross-check the count against Klaviyo's form report for the same window.
   Google will always show **fewer** — it only counts opt-ins it can attribute
   to an ad click, which is the point.

## Next: capture `gclid` (not yet done)

The client-side tag closes the immediate hole, but the higher-value fix is
carrying lead *quality* back. Add a hidden `gclid` field to both Klaviyo forms,
populated from the query string, so it lands on the profile. That unlocks
offline conversion import: a niches-list opt-in that becomes a coaching client
is worth far more than the opt-in, and only offline import can tell Google
which clicks produced those.

## Caveat on the negatives added earlier

The 29 negatives added to `EP Offers Universal Negatives` on this branch were
justified partly on "zero conversions" — a signal now known to have been blind.
Re-checked: **`best dropshipping niches` was never blocked**, which is the term
that matters most for this funnel. What was blocked (`winning products`,
`best dropshipping products`, `products to dropship`, `top 10`, `trending`, and
the AliExpress-app brand terms) stands on search-intent grounds independent of
conversion data, so none of it is being walked back. But no keyword decision on
EP 5 should lean on Google's conversion column until the tag has been live for
a couple of weeks.
