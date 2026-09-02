"""Replace the dynamic remarketing ad. Dry run unless --live.

The existing ad carries one image, one headline, no logo, a homepage final URL,
and a long headline lifted from a blog post about pergolas -- on a remarketing
ad for outdoor kitchens. Responsive display ads are largely immutable, so this
builds a properly stocked replacement and PAUSES the old one (never deletes).

Products themselves come from the linked Merchant Center feed; these assets are
the frame around them and the fallback for non-dynamic impressions.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

AD_GROUP = 199114685912
OLD_AD = 817410863199
FUNNEL = "https://betterpatio.com/pages/custom-outdoor-kitchens"

HEADLINES = ["Still Thinking It Over?", "Your Outdoor Kitchen Awaits",
             "No Tax & Free Shipping", "Authorized Dealer", "Speak To An Expert 24/7"]
LONG_HEADLINE = "Come Back And Finish Your Outdoor Kitchen Build - No Tax & Free Shipping"
DESCRIPTIONS = ["Pick up where you left off.",
                "Free shipping and no sales tax on every outdoor kitchen island.",
                "Authorized dealer with expert design help seven days a week.",
                "Trade pricing available for contractors, designers and builders."]
MARKETING = [38775848533, 40518903587, 40645680760, 40650753548]
SQUARE    = [40512306346, 40543003545, 40646509300]
LOGO      = 38776858109
BUSINESS  = "BetterPatio.com"

for h in HEADLINES:  assert len(h) <= 30, f"headline too long: {h}"
assert len(LONG_HEADLINE) <= 90, LONG_HEADLINE
for d in DESCRIPTIONS: assert len(d) <= 90, d
assert len(BUSINESS) <= 25

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]; e = client.enums
ops = []
def op():
    o = client.get_type("MutateOperation"); ops.append(o); return o

nw = op().ad_group_ad_operation.create
nw.ad_group = f"customers/{CID}/adGroups/{AD_GROUP}"
nw.status = e.AdGroupAdStatusEnum.ENABLED
ad = nw.ad
ad.final_urls.append(FUNNEL)
rda = ad.responsive_display_ad
for h in HEADLINES:
    a = client.get_type("AdTextAsset"); a.text = h; rda.headlines.append(a)
rda.long_headline.text = LONG_HEADLINE
for d in DESCRIPTIONS:
    a = client.get_type("AdTextAsset"); a.text = d; rda.descriptions.append(a)
for i in MARKETING:
    m = client.get_type("AdImageAsset"); m.asset = f"customers/{CID}/assets/{i}"
    rda.marketing_images.append(m)
for i in SQUARE:
    m = client.get_type("AdImageAsset"); m.asset = f"customers/{CID}/assets/{i}"
    rda.square_marketing_images.append(m)
# Logo omitted: the account's 1980x1980 logo asset is rejected in the RDA
# logo_images slot. Logos are optional here, and Google falls back to the
# business name, so this is not worth blocking the rebuild over.
rda.business_name = BUSINESS

old = op().ad_group_ad_operation
old.update.resource_name = f"customers/{CID}/adGroupAds/{AD_GROUP}~{OLD_AD}"
old.update.status = e.AdGroupAdStatusEnum.PAUSED
old.update_mask.paths.append("status")

ga = client.get_service("GoogleAdsService")
req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID
req.mutate_operations.extend(ops)
req.validate_only = not args.live
print(f"{'LIVE' if args.live else 'DRY RUN'}: new ad with "
      f"{len(HEADLINES)} headlines, {len(DESCRIPTIONS)} descriptions, "
      f"{len(MARKETING)+len(SQUARE)} images; old ad paused")
try:
    ga.mutate(request=req)
    print("DONE" if args.live else "VALIDATED — nothing written")
except Exception as ex:
    print("FAILED:"); print(str(ex)[:1500]); sys.exit(1)
