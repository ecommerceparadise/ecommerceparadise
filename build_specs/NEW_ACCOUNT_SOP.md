# New account build — standard operating procedure

Internal. The ordered phases for standing up a managed Google Ads account, with
the repo script that does each one. `_ACCOUNT_TEMPLATE.json` describes the
campaign model; this file is the order of operations and the gates.

Run everything through the venv:

    PYTHONPATH=/home/user/ecommerceparadise .venv/bin/python scripts/X.py

Every phase is dry-run-first. Campaigns are created PAUSED and stay paused until
Trevor says otherwise in the conversation.

---

## 0. Allowlist the account

Add it to `managed_accounts.json` — `{ "id": "...", "name": "..." }`, the live
account name from the API. Nothing in `scripts/` will touch an account that is
not in that file, and the sweeps derive their account list from it, so this one
edit is what puts the account into every account-wide job below.

## 1. Credentials and connectivity

The five vars must be on the cloud environment, not in a local `.env` — the
container is rebuilt from a fresh clone and a local file does not survive it
(see CLAUDE.md). Confirm the API answers for the new customer id before
building anything.

## 2. Account-level exclusions  ← REQUIRED, BEFORE ANY CAMPAIGN IS ENABLED

    scripts/audit_pmax_placements.py --account "<name or id>"      # read only
    scripts/apply_account_placement_exclusions.py --account "<id>" # dry run
    scripts/apply_account_placement_exclusions.py --account "<id>" --execute

Added as a standard phase 2 October 2026, on Trevor's instruction after the
client PMax campaigns were found serving heavily and untargeted on Display and
YouTube.

Why it is this early: these are the only lever that reaches PMax. Performance
Max has no generally available channel off-switch — `network_settings` is not
it — but since January 2026 account-level `customer_negative_criterion` applies
across Performance Max, Demand Gen, YouTube and Display simultaneously, so ONE
list covers every campaign in the account, including ones built later. Doing it
before the first campaign is enabled means no budget is spent on parked domains
and in-app inventory while the list is still a to-do.

What the apply script sets, in two families:

- **16 content labels** (a fixed v25 enum, so the list is explicit and
  auditable): `PARKED_DOMAIN` and `BELOW_THE_FOLD` are the pure-waste pair;
  `EMBEDDED_VIDEO` and `LIVE_STREAMING_VIDEO` are the low-intent video
  surfaces that inflate Display and YouTube volume; the rest are brand
  suitability for a home-improvement / equipment retailer.
- **Every mobile app category**, resolved at run time from
  `mobile_app_category_constant` rather than hardcoded. On a store selling
  $2k–$25k equipment, in-app inventory is close to pure waste and is usually
  the bulk of untargeted Display volume. `--keep-apps` skips this family if an
  account genuinely wants app traffic.

Left ON deliberately: `VIDEO` (removing all video is too blunt), the
family-safe video ratings, `BRAND_SUITABILITY_CONTENT_FOR_FAMILIES`, and the
HEALTH and remaining NEWS suitability labels — too broad in this niche to be
worth the reach loss.

Specific sites, apps and YouTube channels are NOT in the script's defaults on
purpose. Those come from evidence: run the audit, then feed its output back in
with `--placements FILE` (one per line — a bare domain, an app id, or a
`UC...` channel id).

The script is idempotent — it reads what is already excluded and skips it — so
re-running it after any later campaign build is safe and is the easy way to
confirm the account is still covered. Mutates use `partial_failure`, because
content-label support varies by campaign type and one unsupported value must
not roll back the batch; rejections are printed, not swallowed.

Doing this in the UI instead: Tools → Content suitability → Excluded content,
plus Tools → Placement exclusion lists for specific placements. The API path
above is preferred because it is repeatable and leaves a record.

## 3. Asset automation opt-outs

Set the opt-outs on each campaign AT CREATION TIME, then sweep:

    scripts/disable_asset_automation_everywhere.py --execute

Standing rule (CLAUDE.md): automatically-created assets stay OFF in every
campaign, always. The sweep covers every account in `managed_accounts.json`, so
phase 0 is what enrols the new account. Only PERFORMANCE_MAX and SEARCH expose
the setting.

## 4. Feed and funnel prerequisites

Merchant Center linked with an eligible feed; a lead-gen funnel page if the
account is to run anything other than product ads. `_ACCOUNT_TEMPLATE.json`
has the detail and the failure modes.

## 5. Conversion goals

Leave `campaign_conversion_goal` UNSET so the campaign inherits the account
goal. Setting it at campaign level has silently blinded campaigns in this
portfolio. Check for duplicate primary conversion actions before launch.

## 6. Build the campaigns

Feed-only PMax per the house pattern: one asset group per brand, ONLY for
brands with servable products, no catch-all group, and every group carries
search themes AND an audience signal — built in the same script that creates
the group. Geo targeting is PRESENCE, never PRESENCE_OR_INTEREST.

Record any client-requested brand restriction as an allowlist
(`ADVERTISE_ONLY`) or a withheld set (`WITHHELD_BRANDS`) in
`scripts/prune_pmax_asset_groups.py` at the same time, so a brand added to the
feed later is withheld too instead of resurfacing as a coverage gap.

## 7. Verify before handing over

    scripts/prune_pmax_asset_groups.py                              # dry run
    scripts/apply_account_placement_exclusions.py --account "<id>"  # expect "nothing to add"
    scripts/disable_asset_automation_everywhere.py                  # expect 5/5 off

Then report the unreachable-product count, which the prune script prints — with
no catch-all group, a brand without a group of its own cannot serve, and that
trade-off is to be stated, not glossed.
