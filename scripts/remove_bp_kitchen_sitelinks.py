"""Remove sitelinks from the BetterPatio custom-kitchen funnel campaign.

Google has no per-campaign 'disable sitelinks' switch. Assets resolve at the
lowest level present -- ad group beats campaign, campaign beats account -- so a
campaign with no sitelinks of its own silently inherits the account-level set.
Simply deleting the funnel's four would put the eight account-level ones back.

The only way to leave a campaign with genuinely zero sitelinks is to remove them
at every level that feeds it. That means removing the account-level set, which
also feeds BP - PMax - Outdoor Kitchens ($110/day). So this copies those eight
to the PMax campaign first, and only then removes them from the account.

Order is deliberate: PMax gets its own copy BEFORE the account-level links go,
so it is never left without sitelinks even briefly.

  1. attach the 8 account-level sitelink assets to the PMax campaign
  2. remove the 8 account-level links
  3. remove the 4 campaign-level links on the funnel campaign

Removing a customer_asset or campaign_asset detaches the link; the underlying
asset is left intact, which is why step 1 can reuse the same assets.

The two Display remarketing campaigns also inherit the account-level set and
will lose their sitelinks. That is accepted -- sitelinks rarely render on
Display, and Trevor confirmed the trade.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
FUNNEL = 23303878302          # Build Your Own Outdoor Kitchen Campaign
PMAX = 24209664922            # BP - PMax - Outdoor Kitchens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")

    # --- what is where -------------------------------------------------------
    account_links, account_assets = [], []
    for r in ga.search(customer_id=cust, query="""
        SELECT customer_asset.resource_name, asset.resource_name,
               asset.sitelink_asset.link_text, asset.final_urls
        FROM customer_asset
        WHERE customer_asset.field_type = 'SITELINK'
          AND customer_asset.status != 'REMOVED' """):
        account_links.append(r.customer_asset.resource_name)
        account_assets.append((r.asset.resource_name,
                               r.asset.sitelink_asset.link_text))

    funnel_links = []
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign_asset.resource_name,
               asset.sitelink_asset.link_text
        FROM campaign_asset
        WHERE campaign.id = {FUNNEL}
          AND campaign_asset.field_type = 'SITELINK'
          AND campaign_asset.status != 'REMOVED' """):
        funnel_links.append((r.campaign_asset.resource_name,
                             r.asset.sitelink_asset.link_text))

    pmax_existing = set()
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, asset.resource_name
        FROM campaign_asset
        WHERE campaign.id = {PMAX}
          AND campaign_asset.field_type = 'SITELINK'
          AND campaign_asset.status != 'REMOVED' """):
        pmax_existing.add(r.asset.resource_name)

    # Guard: never strip the account bare without PMax having a copy. If the
    # account-level set is already gone, there is nothing to protect PMax with.
    if not account_assets and not pmax_existing:
        print("ABORT: no account-level sitelinks to copy and PMax has none of "
              "its own -- refusing to proceed, PMax would end up with nothing")
        return 1

    to_copy = [(rn, txt) for rn, txt in account_assets
               if rn not in pmax_existing]

    print(f"STEP 1 -- copy {len(to_copy)} sitelink(s) to PMax {PMAX}")
    for _, txt in to_copy:
        print(f"    '{txt}'")
    if pmax_existing:
        print(f"    ({len(pmax_existing)} already attached, skipped)")

    print(f"\nSTEP 2 -- remove {len(account_links)} account-level link(s)")
    for _, txt in account_assets:
        print(f"    '{txt}'")

    print(f"\nSTEP 3 -- remove {len(funnel_links)} link(s) on funnel {FUNNEL}")
    for _, txt in funnel_links:
        print(f"    '{txt}'")

    print("\nResult: funnel campaign left with zero sitelinks at every level.")
    print("        PMax keeps all 8. Display remarketing loses its inherited set.")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    # --- 1. protect PMax first ----------------------------------------------
    if to_copy:
        ops = []
        for asset_rn, _ in to_copy:
            op = client.get_type("CampaignAssetOperation")
            c = op.create
            c.campaign = client.get_service("CampaignService").campaign_path(
                cust, PMAX)
            c.asset = asset_rn
            c.field_type = client.enums.AssetFieldTypeEnum.SITELINK
            ops.append(op)
        client.get_service("CampaignAssetService").mutate_campaign_assets(
            customer_id=cust, operations=ops)
        print(f"  1. attached {len(ops)} sitelink(s) to PMax")

    # Verify before removing anything, so a partial failure above cannot leave
    # PMax without sitelinks.
    now = len(list(ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign_asset.resource_name
        FROM campaign_asset
        WHERE campaign.id = {PMAX}
          AND campaign_asset.field_type = 'SITELINK'
          AND campaign_asset.status != 'REMOVED' """)))
    if now < len(account_assets):
        print(f"ABORT: PMax has {now} sitelinks, expected "
              f"{len(account_assets)}. Not removing account-level links.")
        return 1
    print(f"     verified: PMax now carries {now} sitelink(s)")

    # --- 2. remove account-level --------------------------------------------
    if account_links:
        ops = []
        for rn in account_links:
            op = client.get_type("CustomerAssetOperation")
            op.remove = rn
            ops.append(op)
        client.get_service("CustomerAssetService").mutate_customer_assets(
            customer_id=cust, operations=ops)
        print(f"  2. removed {len(ops)} account-level link(s)")

    # --- 3. remove the funnel's own -----------------------------------------
    if funnel_links:
        ops = []
        for rn, _ in funnel_links:
            op = client.get_type("CampaignAssetOperation")
            op.remove = rn
            ops.append(op)
        client.get_service("CampaignAssetService").mutate_campaign_assets(
            customer_id=cust, operations=ops)
        print(f"  3. removed {len(ops)} link(s) from the funnel campaign")

    return 0


if __name__ == "__main__":
    sys.exit(main())
