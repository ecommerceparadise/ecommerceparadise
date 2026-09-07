"""Keep the BetterPatio custom-kitchen funnel on its landing page.

Every enabled ad in 'Build Your Own Outdoor Kitchen Campaign' already points at
/pages/custom-outdoor-kitchens, but sitelinks bypass the ad's destination. In
the last 30 days roughly 67 of 235 clicks (~$162) landed somewhere else.

Two sources, only one of which is still live:

  - Two RSAs with a home-page final URL (byo_home_dealer, byo_home_shop) took
    46 clicks / $103.19. Already PAUSED, so that leak has stopped.
  - Sitelinks are still leaking. The campaign has ZERO campaign-level sitelinks,
    so it inherits 8 account-level ones, all off-target. One ad group also
    carries 3 of its own (Mont Alpi, Le Griddle, About Us).

Google resolves assets at the lowest level present: ad group beats campaign,
campaign beats account. So the fix is to remove the ad group's own sitelinks and
give the campaign its own set pointing at the landing page -- that suppresses the
account-level ones for this campaign without touching any other campaign.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
CAMPAIGN = 23303878302
LANDING = "https://betterpatio.com/pages/custom-outdoor-kitchens"

# Anchors keep the destinations distinct (Google rejects sitelinks that all
# share one URL) while keeping every click on the landing page. An anchor that
# does not exist simply lands at the top of the page.
NEW_SITELINKS = [
    ("Free 3D Design",  "See your kitchen before you buy", "Custom 3D rendering", "#design"),
    ("How It Works",    "Design, build, delivered",        "Start to finish",     "#process"),
    ("See Our Builds",  "Real customer kitchens",          "Photo gallery",       "#gallery"),
    ("Get Your Quote",  "Free, no obligation",             "Fast turnaround",     "#quote"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")

    # Guard: never touch a campaign whose ads do not already point at the
    # landing page -- that would be a different problem than this script fixes.
    bad_ads = []
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.name, ad_group_ad.ad.id, ad_group_ad.ad.final_urls
        FROM ad_group_ad
        WHERE campaign.id = {CAMPAIGN} AND ad_group_ad.status = 'ENABLED' """):
        for u in r.ad_group_ad.ad.final_urls:
            if not u.startswith(LANDING):
                bad_ads.append(f"{r.ad_group.name} / ad {r.ad_group_ad.ad.id} -> {u}")
    if bad_ads:
        print("ABORT: enabled ads still point away from the landing page:")
        for b in bad_ads:
            print(f"  {b}")
        return 1
    print(f"all enabled ads point at {LANDING}  OK")

    # --- what we will remove ------------------------------------------------
    to_remove = []
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, ad_group.id, ad_group.name,
               ad_group_asset.resource_name, ad_group_asset.field_type,
               asset.sitelink_asset.link_text, asset.final_urls
        FROM ad_group_asset
        WHERE campaign.id = {CAMPAIGN}
          AND ad_group_asset.field_type = 'SITELINK'
          AND ad_group_asset.status != 'REMOVED' """):
        to_remove.append((r.ad_group_asset.resource_name,
                          r.ad_group.name,
                          r.asset.sitelink_asset.link_text,
                          r.asset.final_urls[0] if r.asset.final_urls else ""))

    existing_campaign_sitelinks = list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign_asset.resource_name
        FROM campaign_asset
        WHERE campaign.id = {CAMPAIGN}
          AND campaign_asset.field_type = 'SITELINK'
          AND campaign_asset.status != 'REMOVED' """))

    print(f"\nWOULD REMOVE {len(to_remove)} ad-group sitelink(s):")
    for _, ag, text, url in to_remove:
        print(f"  [{ag}] '{text}' -> {url}")

    if existing_campaign_sitelinks:
        print(f"\n{len(existing_campaign_sitelinks)} campaign-level sitelink(s) "
              f"already exist; not adding more.")
    else:
        print(f"\nWOULD ADD {len(NEW_SITELINKS)} campaign-level sitelink(s), "
              f"which suppress the 8 inherited account-level ones:")
        for text, d1, d2, anchor in NEW_SITELINKS:
            print(f"  '{text}' -> {LANDING}{anchor}")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    # --- remove ad group sitelinks ------------------------------------------
    if to_remove:
        ops = []
        for rn, *_ in to_remove:
            op = client.get_type("AdGroupAssetOperation")
            op.remove = rn
            ops.append(op)
        client.get_service("AdGroupAssetService").mutate_ad_group_assets(
            customer_id=cust, operations=ops)
        print(f"  removed {len(ops)} ad-group sitelink(s)")

    # --- create campaign sitelinks ------------------------------------------
    if not existing_campaign_sitelinks:
        asset_ops = []
        for text, d1, d2, anchor in NEW_SITELINKS:
            op = client.get_type("AssetOperation")
            a = op.create
            a.final_urls.append(f"{LANDING}{anchor}")
            a.sitelink_asset.link_text = text
            a.sitelink_asset.description1 = d1
            a.sitelink_asset.description2 = d2
            asset_ops.append(op)
        res = client.get_service("AssetService").mutate_assets(
            customer_id=cust, operations=asset_ops)
        names = [r.resource_name for r in res.results]
        print(f"  created {len(names)} sitelink asset(s)")

        link_ops = []
        for rn in names:
            op = client.get_type("CampaignAssetOperation")
            c = op.create
            c.campaign = client.get_service("CampaignService").campaign_path(
                cust, CAMPAIGN)
            c.asset = rn
            c.field_type = client.enums.AssetFieldTypeEnum.SITELINK
            link_ops.append(op)
        client.get_service("CampaignAssetService").mutate_campaign_assets(
            customer_id=cust, operations=link_ops)
        print(f"  attached {len(link_ops)} sitelink(s) to campaign {CAMPAIGN}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
