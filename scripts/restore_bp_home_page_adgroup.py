"""Re-enable the ad group that carried the BetterPatio Search campaign.

'Custom Kitchens | Home Page' (190077137940) was paused on 2026-08-30 22:04 from
Trevor's own login, three days before this session's cutover. It held all 11 of
the campaign's 30-day conversions; the surviving 'Landing Page' ad group has
never converted. Re-enabling restores the structure that was serving.

Note the tension this creates: the restored ads point at betterpatio.com/, which
the account's landing page policy rules out. That policy is why the ad group was
plausibly paused in the first place. Flagged rather than silently changed.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

AD_GROUP = 190077137940
ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]; e = client.enums
op = client.get_type("AdGroupOperation")
op.update.resource_name = f"customers/{CID}/adGroups/{AD_GROUP}"
op.update.status = e.AdGroupStatusEnum.ENABLED
op.update_mask.paths.append("status")
req = client.get_type("MutateAdGroupsRequest")
req.customer_id = CID; req.operations.append(op); req.validate_only = not args.live
try:
    client.get_service("AdGroupService").mutate_ad_groups(request=req)
    print("DONE" if args.live else "VALIDATED - nothing written")
except Exception as ex:
    print("FAILED:", str(ex)[:800]); sys.exit(1)
