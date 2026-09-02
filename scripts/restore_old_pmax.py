"""Restore the converting legacy PMax and de-conflict it from the new build.

"all other brands" (23955965189) covers 29 brands the new PMax deliberately
does not touch -- Bull, Blaze, Summerset, Chicago Brick Oven, Coyote, Fire
Magic and the rest of the catalogue. The two are complementary, with exactly
one brand overlapping: 'ufinish by betterpatio outdoor kitchens', which the new
House Brands asset group is purpose-built for. Removing it here leaves each
brand owned by exactly one campaign.

Also repoints its asset group off the homepage, per the account's landing page
rule that nothing paid points at betterpatio.com/.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

OLD_PMAX = 23955965189
FUNNEL = "https://betterpatio.com/pages/custom-outdoor-kitchens"
OVERLAP_BRAND = "ufinish by betterpatio outdoor kitchens"

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]; e = client.enums
ga = client.get_service("GoogleAdsService")
ops = []
def op():
    o = client.get_type("MutateOperation"); ops.append(o); return o

# drop the one overlapping brand so the two PMax campaigns never bid on the same SKU
for r in ga.search(customer_id=CID, query=f"""
SELECT asset_group_listing_group_filter.resource_name,
       asset_group_listing_group_filter.case_value.product_brand.value
FROM asset_group_listing_group_filter WHERE campaign.id = {OLD_PMAX}"""):
    if r.asset_group_listing_group_filter.case_value.product_brand.value == OVERLAP_BRAND:
        op().asset_group_listing_group_filter_operation.remove = (
            r.asset_group_listing_group_filter.resource_name)
        print(f"  removing overlap: {OVERLAP_BRAND}")

# homepage -> funnel on the asset group
for r in ga.search(customer_id=CID, query=f"""
SELECT asset_group.id, asset_group.final_urls FROM asset_group
WHERE campaign.id = {OLD_PMAX}"""):
    if any("pages/" not in u for u in r.asset_group.final_urls):
        g = op().asset_group_operation
        g.update.resource_name = f"customers/{CID}/assetGroups/{r.asset_group.id}"
        g.update.final_urls.append(FUNNEL)
        g.update_mask.paths.append("final_urls")
        print(f"  final URL {list(r.asset_group.final_urls)} -> {FUNNEL}")

# match the new build's settings: no final URL expansion, no auto image extraction
c = op().campaign_operation
c.update.resource_name = f"customers/{CID}/campaigns/{OLD_PMAX}"
for t in [e.AssetAutomationTypeEnum.FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION,
          e.AssetAutomationTypeEnum.GENERATE_IMAGE_EXTRACTION]:
    a = client.get_type("Campaign").AssetAutomationSetting()
    a.asset_automation_type = t
    a.asset_automation_status = e.AssetAutomationStatusEnum.OPTED_OUT
    c.update.asset_automation_settings.append(a)
c.update.status = e.CampaignStatusEnum.ENABLED
c.update.geo_target_type_setting.positive_geo_target_type = e.PositiveGeoTargetTypeEnum.PRESENCE
c.update.geo_target_type_setting.negative_geo_target_type = e.NegativeGeoTargetTypeEnum.PRESENCE
c.update_mask.paths.extend(["asset_automation_settings", "status",
                            "geo_target_type_setting.positive_geo_target_type",
                            "geo_target_type_setting.negative_geo_target_type"])

# lower-48 geo, copied from the remarketing campaigns, if it has none
existing = len(list(ga.search(customer_id=CID, query=f"""
SELECT campaign_criterion.criterion_id FROM campaign_criterion
WHERE campaign.id = {OLD_PMAX} AND campaign_criterion.type = 'LOCATION'
  AND campaign_criterion.negative = FALSE""")))
if existing == 0:
    for r in ga.search(customer_id=CID, query="""
    SELECT campaign_criterion.location.geo_target_constant FROM campaign_criterion
    WHERE campaign.id = 24064549810 AND campaign_criterion.type = 'LOCATION'
      AND campaign_criterion.negative = FALSE"""):
        cc = op().campaign_criterion_operation.create
        cc.campaign = f"customers/{CID}/campaigns/{OLD_PMAX}"
        cc.location.geo_target_constant = r.campaign_criterion.location.geo_target_constant
        cc.negative = False
print(f"  geo: {'already set' if existing else 'adding 48 states'}, PRESENCE")

req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID; req.mutate_operations.extend(ops); req.validate_only = not args.live
print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
try:
    ga.mutate(request=req)
    print("DONE" if args.live else "VALIDATED — nothing written")
except Exception as ex:
    print("FAILED:"); print(str(ex)[:1500]); sys.exit(1)
