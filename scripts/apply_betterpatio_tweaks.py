"""Two follow-up changes to the BetterPatio build. Dry run unless --live.

1. Opt the new PMax campaign out of GENERATE_IMAGE_EXTRACTION. Google turns it
   on by default; it auto-generates imagery from the landing page, which the
   account's ad standards rule out in favour of real product photography.
2. Repoint the static remarketing ad from the homepage to the kitchen funnel.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

FUNNEL = "https://betterpatio.com/pages/custom-outdoor-kitchens"
PMAX_CAMPAIGN = 24209664922
STATIC_RT_AD = 818015332228

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()

client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]; e = client.enums
ops = []
def op():
    o = client.get_type("MutateOperation"); ops.append(o); return o

# 1. keep every asset automation Google already set, flipping only image extraction.
ga = client.get_service("GoogleAdsService")
cur = list(ga.search(customer_id=CID, query=f"""
SELECT campaign.asset_automation_settings FROM campaign
WHERE campaign.id = {PMAX_CAMPAIGN}"""))[0].campaign.asset_automation_settings

c = op().campaign_operation
c.update.resource_name = f"customers/{CID}/campaigns/{PMAX_CAMPAIGN}"
for setting in cur:
    a = client.get_type("Campaign").AssetAutomationSetting()
    a.asset_automation_type = setting.asset_automation_type
    a.asset_automation_status = (
        e.AssetAutomationStatusEnum.OPTED_OUT
        if setting.asset_automation_type == e.AssetAutomationTypeEnum.GENERATE_IMAGE_EXTRACTION
        else setting.asset_automation_status)
    c.update.asset_automation_settings.append(a)
c.update_mask.paths.append("asset_automation_settings")

# 2. static remarketing -> funnel, not the homepage
a = op().ad_operation
a.update.resource_name = f"customers/{CID}/ads/{STATIC_RT_AD}"
a.update.final_urls.append(FUNNEL)
a.update_mask.paths.append("final_urls")

req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID
req.mutate_operations.extend(ops)
req.validate_only = not args.live
print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
try:
    ga.mutate(request=req)
    print("OK" if args.live else "VALIDATED — nothing written")
except Exception as ex:
    print("FAILED:"); print(str(ex)[:1500]); sys.exit(1)
