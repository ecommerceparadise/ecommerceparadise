"""Restore the BetterPatio Search campaign to its exact 2026-08-25 pre-split state.

Reconstructed from change_event, not from assumption. Everything below was
changed on 25 August from Trevor's own login, in one sitting:

  01:06:33  campaign final_url_suffix  ''  ->  'utm_source=google&...byo_kitchen_home_lp'
  01:16:12  ad group renamed  'Build Your Own Outdoor Kitchen' -> 'Custom Kitchens | Home Page'
  01:16:13  new ad group created      'Custom Kitchens | Landing Page' (202444065511)
  01:16:17  ad 786072183293 PAUSED    <- this ad holds all 11 of the 30-day conversions
  01:16:18  four new ads created      2 -> homepage, 2 -> /pages/custom-outdoor-kitchens
  04:30:46  target CPA REMOVED        $233.42 -> none

Ad 798601103407 was already paused before 25 August (no change event, zero
impressions in 30 days), so it stays paused.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 23303878302
AG_ORIGINAL = 190077137940      # renamed to "Custom Kitchens | Home Page" on Aug 25
AG_NEW = 202444065511           # created Aug 25
CONVERTING_AD = 786072183293    # paused Aug 25; 11 conversions
ADS_CREATED_AUG25 = [822053938284, 822053938287, 822053938290, 822053938293]
ORIGINAL_NAME = "Build Your Own Outdoor Kitchen"
ORIGINAL_TARGET_CPA_MICROS = 233_420_000

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]; e = client.enums
ops = []
def op():
    o = client.get_type("MutateOperation"); ops.append(o); return o

# 1. the converting ad back on
a = op().ad_group_ad_operation
a.update.resource_name = f"customers/{CID}/adGroupAds/{AG_ORIGINAL}~{CONVERTING_AD}"
a.update.status = e.AdGroupAdStatusEnum.ENABLED
a.update_mask.paths.append("status")

# 2. the four ads added on Aug 25 back off
for ad_id in ADS_CREATED_AUG25:
    ag = AG_NEW if ad_id in (822053938290, 822053938293) else AG_ORIGINAL
    x = op().ad_group_ad_operation
    x.update.resource_name = f"customers/{CID}/adGroupAds/{ag}~{ad_id}"
    x.update.status = e.AdGroupAdStatusEnum.PAUSED
    x.update_mask.paths.append("status")

# 3. the ad group created on Aug 25 back off (paused, never removed)
g = op().ad_group_operation
g.update.resource_name = f"customers/{CID}/adGroups/{AG_NEW}"
g.update.status = e.AdGroupStatusEnum.PAUSED
g.update_mask.paths.append("status")

# 4. original ad group name and enabled state
n = op().ad_group_operation
n.update.resource_name = f"customers/{CID}/adGroups/{AG_ORIGINAL}"
n.update.name = ORIGINAL_NAME
n.update.status = e.AdGroupStatusEnum.ENABLED
n.update_mask.paths.extend(["name", "status"])

# 5. campaign: clear the tracking suffix, restore the target CPA
c = op().campaign_operation
c.update.resource_name = f"customers/{CID}/campaigns/{CAMPAIGN}"
c.update.final_url_suffix = ""
c.update.maximize_conversions.target_cpa_micros = ORIGINAL_TARGET_CPA_MICROS
c.update_mask.paths.extend(["final_url_suffix",
                            "maximize_conversions.target_cpa_micros"])

print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
print(f"  enable   ad {CONVERTING_AD} (11 conversions) -> homepage")
print(f"  pause    ads {ADS_CREATED_AUG25}")
print(f"  pause    ad group {AG_NEW} 'Custom Kitchens | Landing Page'")
print(f"  rename   ad group {AG_ORIGINAL} -> {ORIGINAL_NAME!r}, ENABLED")
print(f"  campaign final_url_suffix -> ''")
print(f"  campaign target CPA -> ${ORIGINAL_TARGET_CPA_MICROS/1e6:,.2f}")

ga = client.get_service("GoogleAdsService")
req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID; req.mutate_operations.extend(ops); req.validate_only = not args.live
try:
    ga.mutate(request=req)
    print("\n" + ("DONE" if args.live else "VALIDATED - nothing written"))
except Exception as ex:
    print("\nFAILED:"); print(str(ex)[:1500]); sys.exit(1)
