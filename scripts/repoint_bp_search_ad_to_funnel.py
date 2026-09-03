"""Point the BetterPatio Search campaign's live ad at the custom kitchen funnel.

Ad 786072183293 is the ad that produced all 11 of the campaign's 30-day
conversions, and it did so pointing at betterpatio.com/. This repoints it to
/pages/custom-outdoor-kitchens per the account's landing page policy.

The tradeoff is real and worth stating: the funnel destination has never
converted in this account (592 impressions, 0 conversions across the two funnel
ads). Keywords, bid strategy, target CPA and ad copy are unchanged, so the
destination is now the only difference from the configuration that worked.

Changing final_urls sends the ad back through Google review.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

AD = 786072183293
FUNNEL = "https://betterpatio.com/pages/custom-outdoor-kitchens"
ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]
op = client.get_type("AdOperation")
op.update.resource_name = f"customers/{CID}/ads/{AD}"
op.update.final_urls.append(FUNNEL)
op.update_mask.paths.append("final_urls")
req = client.get_type("MutateAdsRequest")
req.customer_id = CID; req.operations.append(op); req.validate_only = not args.live
try:
    client.get_service("AdService").mutate_ads(request=req)
    print("DONE" if args.live else "VALIDATED - nothing written")
except Exception as ex:
    print("FAILED:", str(ex)[:800]); sys.exit(1)
