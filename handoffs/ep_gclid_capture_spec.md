# Spec — carrying lead value back to Google Ads (eCommerce Paradise)

The web tag now tells Google *an opt-in happened*. It cannot tell Google *which
opt-ins became clients*. That second signal is the one worth money: a niches-list
opt-in is worth cents, a coaching or DFY client is worth thousands, and Smart
Bidding currently treats every opt-in as identical.

This spec covers the join key that makes the difference reportable.

---

## Verified preconditions (checked 2026-09-05, account 7871916737)

| | |
|---|---|
| `auto_tagging_enabled` | **True** — `gclid` is being appended to ad clicks |
| `conversion_tracking_status` | `CONVERSION_TRACKING_MANAGED_BY_SELF` |
| `accepted_customer_data_terms` | **True** |
| `enhanced_conversions_for_leads_enabled` | **True** |
| Existing `UPLOAD_CLICKS` actions | **none** |
| Klaviyo profile attribution properties | **none** — profiles carry only `lead_magnet`, `EP Lead Source`, `EP Bucket`, `$source` |

**The important one: Enhanced Conversions for Leads is already switched on and the
customer data terms are already accepted.** That was the expensive prerequisite
and it is already done.

---

## Recommendation: do this in two phases, not one

You asked for the `gclid` capture. It is specced in full below — but it should be
phase 2, not phase 1, and here is the honest reasoning.

**Phase 1 — hashed email (no site changes at all).** Because Enhanced Conversions
for Leads is already enabled, offline conversions can be keyed on a SHA-256 of the
lead's email instead of a click id. Google matches that hash back to the original
ad click on its side. Klaviyo already holds every lead's email, so **the join key
already exists and costs nothing to obtain**. This can run this week with zero
changes to the website.

**Phase 2 — `gclid` capture (the site work below).** Adds a deterministic second
key that lifts match rate where email matching fails: visitors not signed in to a
Google account, or using an email that differs from their Google account.

Phase 1 gets most of the value for a fraction of the work and carries none of the
site-breakage risk. Phase 2 is worth doing, just not first.

---

## A gap in the tag already shipped

There are **three** opt-in paths, not two. The snippet in
`handoffs/ep_niches_conversion_tracking.md` listens for the `klaviyoForms` event,
which only Klaviyo-hosted forms emit:

| Path | Form / source | Emits `klaviyoForms`? | Covered by current tag? |
|---|---|---|---|
| Embed on `/niches/` | `TngeTU` | yes | **yes** |
| Site-wide popup | `VJCEJJ` | yes | **yes** |
| **Homepage Hero** | custom form → Klaviyo API (`Requested Niches List`, `$source: "Homepage Hero"`) | **no** | **no** |

The Homepage Hero form posts server-side to the Klaviyo API and emits no browser
event, so those opt-ins are **currently invisible to Google Ads even with the new
tag installed**. It is a genuine third path — I found it in the event stream after
handing over the first snippet.

I have not been able to locate that form's source: it is not in WPCode (only three
snippets exist there, none of them it), so it is most likely an Elementor HTML
widget on the homepage or theme code. **Say the word and I'll find it and patch
it** — it needs either a `klaviyo.track`/`gtag` call on success, or the same
treatment as the hidden field below.

---

## Design decisions, and why

**The click id cookie is written server-side by PHP and marked `HttpOnly`.**
Safari's ITP caps JavaScript-written cookies and `localStorage` to 7 days — and to
24 hours when the visit arrives from a classified domain with a decorated URL,
which is precisely the shape of a Google Ads click. Cookies set by PHP as
`HttpOnly` are not script-writable and escape that cap. Writing this from JS would
mean silently losing most Safari attribution inside a day.

**Because the cookie is `HttpOnly`, JavaScript reads the value from a REST
endpoint, not from the cookie.** Inlining the click id into page HTML would be
simpler, but if any full-page cache is active — plugin or host-level — one
visitor's click id would be served to the next visitor. That is both a broken
attribution and a privacy leak. The endpoint is only called at submit time, so it
costs one request per conversion, not one per pageview.

**Last touch wins.** If a visitor arrives on a second ad click, the new id
overwrites the old. That matches how Google Ads attributes by default.

**Property naming follows the existing convention** on the profiles (`EP Lead
Source`, `EP Bucket`), so new fields read as native.

---

## Component 1 — capture (WPCode, PHP Snippet, Run Everywhere)

```php
// Capture the Google Ads click id into a first-party HttpOnly cookie, and
// expose it to the browser through a REST endpoint.
//
// Written server-side deliberately: Safari's ITP caps JavaScript-written
// cookies and localStorage to 7 days, and to 24 hours when the visit arrives
// from a classified domain with a decorated URL -- exactly what a Google Ads
// click is. A PHP-set HttpOnly cookie is not subject to that cap.

if ( is_admin() ) {
    return;
}

// --- write on landing -------------------------------------------------------
add_action( 'init', function () {
    if ( headers_sent() ) {
        return;
    }

    // gclid first: wbraid/gbraid are only present when gclid is not.
    foreach ( array( 'gclid', 'wbraid', 'gbraid' ) as $param ) {
        if ( empty( $_GET[ $param ] ) ) {
            continue;
        }

        $raw = wp_unslash( $_GET[ $param ] );

        // Click ids are URL-safe base64. Reject anything else rather than
        // storing arbitrary user input and shipping it to an API later.
        if ( ! preg_match( '/^[A-Za-z0-9._-]{10,255}$/', $raw ) ) {
            continue;
        }

        setcookie( '_ep_click', wp_json_encode( array(
            'id'   => $raw,
            'type' => $param,
            'ts'   => gmdate( 'c' ),   // ISO 8601, needed for the upload later
        ) ), array(
            'expires'  => time() + ( 90 * DAY_IN_SECONDS ),  // Google's import window
            'path'     => '/',
            'secure'   => is_ssl(),
            'httponly' => true,
            'samesite' => 'Lax',
        ) );
        break;  // last touch wins; only one id is stored
    }
}, 1 );

// --- read back at submit time ----------------------------------------------
add_action( 'rest_api_init', function () {
    register_rest_route( 'ep/v1', '/click', array(
        'methods'             => 'GET',
        'permission_callback' => '__return_true',
        'callback'            => function () {
            $raw = isset( $_COOKIE[ '_ep_click' ] )
                ? json_decode( wp_unslash( $_COOKIE[ '_ep_click' ] ), true )
                : null;

            if ( ! is_array( $raw ) || empty( $raw['id'] ) ) {
                return new WP_REST_Response( array( 'click' => null ), 200 );
            }

            return new WP_REST_Response( array(
                'click' => array(
                    'id'   => (string) $raw['id'],
                    'type' => (string) ( $raw['type'] ?? 'gclid' ),
                    'ts'   => (string) ( $raw['ts'] ?? '' ),
                ),
            ), 200 );
        },
    ) );
} );
```

**Cache note:** the REST route must not be full-page cached. WordPress REST
responses are normally excluded by default in every common cache plugin, but
confirm it after install — the verification step below catches it.

---

## Component 2 — attach to the Klaviyo profile

Extend the conversion snippet already specced in
`handoffs/ep_niches_conversion_tracking.md`. Two changes: attach the click id to
the Klaviyo profile, and add `user_data` to the gtag conversion so the **web**
conversion also benefits from enhanced conversions.

Replace the body of the `klaviyoForms` listener with:

```js
window.addEventListener('klaviyoForms', function (e) {
  if (!e || !e.detail || e.detail.type !== 'submit') { return; }

  var id = e.detail.formId;
  if (!FORMS[id]) { return; }
  if (fired[id])  { return; }
  fired[id] = true;

  // Klaviyo puts the submitted fields on the event.
  var f     = (e.detail.metaData || e.detail.submittedFields || {});
  var email = f.$email || f.email || '';

  fetch('/wp-json/ep/v1/click', { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .catch(function ()  { return { click: null }; })
    .then(function (data) {
      var c = (data && data.click) || null;

      // 1. Stamp the click id onto the Klaviyo profile.
      if (c && email && typeof window.klaviyo !== 'undefined') {
        window.klaviyo.identify({
          email: email,
          'EP Click Id':      c.id,
          'EP Click Id Type': c.type,
          'EP Click Time':    c.ts,
          'EP Landing Page':  window.location.pathname
        });
      }

      if (typeof window.gtag !== 'function') { return; }

      // 2. Enhanced conversions for the web conversion itself.
      if (email) {
        window.gtag('set', 'user_data', { email: email });
      }

      window.gtag('event', 'conversion', { send_to: SEND_TO });
      window.gtag('event', 'generate_lead', {
        lead_source: 'klaviyo_niches_list',
        form_placement: FORMS[id]
      });
    });
});
```

`gtag` hashes `user_data` in the browser before it leaves the page; the raw email
is never sent to Google.

**Homepage Hero form:** same properties, set server-side in whatever builds the
Klaviyo profile payload — read `$_COOKIE['_ep_click']` and add `EP Click Id`,
`EP Click Id Type`, `EP Click Time` alongside the existing `EP Lead Source`.

---

## Component 3 — Google Ads conversion actions to create

Neither exists yet. Both `UPLOAD_CLICKS`.

| Name | Category | Fires when | Value |
|---|---|---|---|
| `Niches Lead — Call Booked (Offline)` | `QUALIFIED_LEAD` | Calendly booking from a niches lead | none |
| `Niches Lead — Client Won (Offline)` | `CONVERTED_LEAD` | lead becomes a paying client | real contract value, USD |

Calendly is already connected to this session, so the qualified-lead milestone is
available without new tooling.

**Create both as secondary, not primary.** A `CONVERTED_LEAD` carrying a $2,000
value sitting alongside a $0 opt-in in the same "Conversions" column would make
Maximize Conversions treat one client and one opt-in as equally valuable — worse
than the status quo. Run them in observation for ~30 days, then the right move is
to switch the funnel to **Maximize Conversion Value** with the opt-in valued near
zero and the client conversion carrying real value. That is the endgame this whole
exercise is for.

---

## Component 4 — the upload job

Daily batch. `scripts/upload_ep_offline_conversions.py`, following the existing
house pattern (dry run by default, `--execute` to push).

```python
def click_conversion(client, action_rn, lead):
    cc = client.get_type("ClickConversion")
    cc.conversion_action   = action_rn
    cc.conversion_date_time = lead["converted_at"]   # 'YYYY-MM-DD HH:MM:SS+HH:MM'
    cc.conversion_value    = lead["value"]
    cc.currency_code       = "USD"
    cc.order_id            = lead["profile_id"]      # dedupe key across re-runs

    if lead.get("gclid"):
        cc.gclid = lead["gclid"]                     # deterministic, preferred
    else:
        ui = client.get_type("UserIdentifier")       # enhanced-conversions fallback
        ui.hashed_email = hashlib.sha256(
            lead["email"].strip().lower().encode()
        ).hexdigest()
        ui.user_identifier_source = (
            client.enums.UserIdentifierSourceEnum.FIRST_PARTY)
        cc.user_identifiers.append(ui)

    return cc


svc = client.get_service("ConversionUploadService")
resp = svc.upload_click_conversions(
    customer_id=CID, conversions=batch, partial_failure=True)
```

Notes that matter:

- **`partial_failure=True` is required.** Unmatched click ids are normal and must
  not fail the whole batch. Log `resp.partial_failure_error` every run — it is the
  only place match failures surface.
- **`order_id` set to the Klaviyo profile id** makes re-running the job idempotent.
- **`conversion_date_time` needs a UTC offset** (`2026-09-05 14:03:00-07:00`).
  A naive timestamp is rejected.
- **90-day ceiling.** A `gclid` older than 90 days will not match. Leads that
  convert slowly fall back to the hashed-email path, which is not bound the same
  way — another argument for having both keys.
- **EEA traffic** needs `cc.consent.ad_user_data` / `ad_personalization` set.
  Worth a look at where these signups actually come from before going live.

Source of truth for "became a client" is the open question — Klaviyo list
membership, a Zoho CRM stage, or a Stripe/PayPal payment. Whichever it is, the job
reads it, joins to the Klaviyo profile for `EP Click Id` and email, and uploads.

---

## Rollout order

1. **Install the conversion snippet** from `ep_niches_conversion_tracking.md`. Confirm
   `Niches List Opt-In (Klaviyo)` starts recording. *(Nothing below matters until
   this works.)*
2. **Phase 1 — hashed-email offline upload.** Create the two `UPLOAD_CLICKS`
   actions, define "became a client", build the upload job. **No site changes.**
3. **Patch the Homepage Hero form** so its opt-ins are counted at all.
4. **Phase 2 — Component 1 + 2** for `gclid` capture, to lift match rate.
5. **After ~30 days of client-won data**, revisit bidding: Maximize Conversion
   Value on real client value.

## How to verify each piece

- **Capture:** visit `ecommerceparadise.com/niches/?gclid=TEST123456` logged out,
  then `curl -b` the REST route — or simply load `/wp-json/ep/v1/click` in the same
  browser session. Expect `{"click":{"id":"TEST123456","type":"gclid",...}}`. If it
  returns `null`, the cookie is not being set; if it returns a *stale* id for a
  fresh browser, the route is being cached.
- **Attach:** submit the form, then check the profile in Klaviyo for `EP Click Id`.
- **Upload:** run the job with `--execute` on one known lead, then check the
  conversion action in Google Ads moves off "No recent conversions". Expect a lag
  of up to ~24h before the count appears.

## Consent

Storing a click id for 90 days is advertising-purpose processing. The signups in
the event stream are visibly international, and I did not find a consent
management platform among the active plugins. That is a pre-existing question
rather than one this spec creates, but it becomes more pointed once a durable
click id is being stored — worth a decision before phase 2 rather than after.
