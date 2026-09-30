"""Fix the BetterPatio dynamic remarketing campaign.

Trevor, 30 September 2026: "only bid on purchase. attach the feed. split the
audiences. add the logo and delete staule paused ad".

`Dynamic Display Remarketing Ads` [24040677834] is a DISPLAY campaign on
$20/day. Over 90 days it ran 185,533 impressions and 2,191 clicks for $977.13
with `conversions = 0` -- while `all_conversions = 40` (26+2 lead form
submissions and 12 add-to-carts worth $33,491, none of which count toward the
conversions metric).

Four changes here.

1. BID ON PURCHASE ONLY -- verify, do not change. The campaign already inherits
   the account's only biddable goal, Purchase / Website, and no campaign-level
   override is set. Leaving `campaign_conversion_goal` unset is deliberate:
   setting it has silently blinded campaigns in these accounts before. So this
   step asserts the state and aborts if it is anything else.

2. THE FEED IS ALREADY ATTACHED -- assert it, do not change it. I first read
   the campaign's empty `campaign_asset_set` as a missing feed. That was wrong.
   For a DISPLAY campaign the dynamic remarketing feed is attached through
   `campaign.shopping_setting.merchant_id`, which is set to 101451631 and
   matches the account's active Merchant Center link. The asset-set rows that
   every PMax campaign carries are Google-managed; trying to create one returns
   `MUTATE_NOT_ALLOWED` because the MERCHANT_CENTER_FEED asset set is not
   user-writable. So this step verifies the merchant link and stops if it is
   missing or points somewhere unexpected.

3. SPLIT THE AUDIENCES. All four remarketing lists sat in one ad group, where
   84,000 general visitors drowned out 200 cart abandoners -- Google spends
   where it is cheapest, so the high-intent audience never won an auction. One
   ad group per intent tier instead.

4. ADD THE LOGO, DELETE THE STALE AD. The live ad carries no logo at all, which
   costs it placements. A responsive display ad's creative is IMMUTABLE, so a
   logo cannot be added to the existing ad -- a new ad has to be built with the
   same text and images plus the logo, and the old one paused. The genuinely
   stale ad (paused, one headline, one description) is removed.

Note on what feed-only means here, since it came up: a Display dynamic
remarketing ad is NOT feed only the way a PMax asset group is. A responsive
display ad REQUIRES headlines, descriptions and images -- the feed supplies the
product panel and the assets supply the frame around it. A Display ad cannot
serve with zero assets. The assets on this ad are correct; the missing feed was
the fault.

Run with no flags for a dry run. Pass --execute to apply.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
CAMPAIGN = 24040677834
FEED_ASSET_SET = 6492764954        # MERCHANT_CENTER_FEED, as used by the live PMax
EXISTING_AD_GROUP = 199114685912   # 'Ad group 1'
STALE_AD = 817410863199            # paused, 1 headline / 1 description

SQUARE_LOGO = 38776858109          # 1980x1980, the brand logo the PMax uses
LANDSCAPE_LOGO = 440608012         # 800x200 (4:1)

# Intent tiers. The existing ad group is repurposed as the broad tier so its
# history is kept; the two higher-intent tiers are new.
GENERAL_NAME = "BP RMK · General Visitors"
TIERS = [
    ("BP RMK · Cart Abandoners", [67061291, 8139768599]),
    ("BP RMK · Product Viewers", [67061171]),
]
KEEP_ON_GENERAL = [67061051, 67060931]      # general visitors, all visitors
MOVE_OFF_GENERAL = [67061171, 67061291]     # now live in their own ad groups

BUSINESS_NAME = "BetterPatio.com"
LONG_HEADLINE = ("Come Back And Finish Your Outdoor Kitchen Build - "
                 "No Tax & Free Shipping")
HEADLINES = ["Still Thinking It Over?", "Your Outdoor Kitchen Awaits",
             "No Tax & Free Shipping", "Authorized Dealer",
             "Speak To An Expert 24/7"]
DESCRIPTIONS = [
    "Pick up where you left off.",
    "Free shipping and no sales tax on every outdoor kitchen island.",
    "Authorized dealer with expert design help seven days a week.",
    "Trade pricing available for contractors, designers and builders."]
MARKETING_IMAGES = [38775848533, 40518903587, 40645680760, 40650753548]
SQUARE_IMAGES = [40512306346, 40543003545, 40646509300]
FINAL_URL = "https://betterpatio.com/pages/custom-outdoor-kitchens"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    def asset_rn(i):
        return f"customers/{cust}/assets/{i}"

    # ---- guards ------------------------------------------------------------
    camp = None
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type, campaign.bidding_strategy_type,
               campaign.shopping_setting.merchant_id,
               campaign_budget.amount_micros
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""):
        camp = r
    if camp is None:
        print(f"ABORT: campaign {CAMPAIGN} not found")
        return 1
    if camp.campaign.advertising_channel_type.name != "DISPLAY":
        print(f"ABORT: campaign is {camp.campaign.advertising_channel_type.name}, "
              "expected DISPLAY")
        return 1

    goals = [(g.campaign_conversion_goal.category.name,
              g.campaign_conversion_goal.origin.name)
             for g in ga.search(customer_id=cust, query=f"""
        SELECT campaign_conversion_goal.category, campaign_conversion_goal.origin,
               campaign_conversion_goal.biddable, campaign.id
        FROM campaign_conversion_goal WHERE campaign.id = {CAMPAIGN}""")
             if g.campaign_conversion_goal.biddable]

    print("=" * 76)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 76)
    print(f"\n{camp.campaign.name!r} [{CAMPAIGN}]  {camp.campaign.status.name}  "
          f"${camp.campaign_budget.amount_micros/1e6:.2f}/day  "
          f"{camp.campaign.bidding_strategy_type.name}")

    print("\n1. BID ON PURCHASE ONLY (assert, no change)")
    print(f"   biddable goals: {goals}")
    if goals != [("PURCHASE", "WEBSITE")]:
        print("   ABORT: expected exactly [('PURCHASE','WEBSITE')]. Something "
              "else is biddable -- fix that deliberately, not as a side effect.")
        return 1
    print("   OK: purchase only, inherited from the account. Nothing to change.")

    mc = camp.campaign.shopping_setting.merchant_id
    account_mcs = {r.product_link.merchant_center.merchant_center_id
                   for r in ga.search(customer_id=cust, query="""
        SELECT product_link.merchant_center.merchant_center_id, product_link.type
        FROM product_link""")
                   if r.product_link.type_.name == "MERCHANT_CENTER"}
    print(f"\n2. FEED (assert, no change)")
    print(f"   campaign shopping_setting.merchant_id = {mc or 'NONE'}")
    print(f"   account Merchant Center links: {sorted(account_mcs)}")
    if not mc:
        print("   ABORT: no merchant_id on the campaign, so it has no dynamic "
              "feed. That has to be set in the UI under Dynamic ads.")
        return 1
    if mc not in account_mcs:
        print(f"   ABORT: merchant_id {mc} is not an active Merchant Center "
              "link on this account.")
        return 1
    print("   OK: feed attached via merchant_id, matching an active link. "
          "Nothing to change.")
    print("   (campaign_asset_set is empty, which is normal here -- those rows "
          "are Google-managed and only appear for PMax/Shopping.)")
    need_feed = False

    ag_lists, ag_names = {}, {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.id, ad_group.name, ad_group.status, campaign.id
        FROM ad_group WHERE campaign.id = {CAMPAIGN}
          AND ad_group.status != 'REMOVED'"""):
        ag_names[r.ad_group.id] = r.ad_group.name
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.id, ad_group_criterion.criterion_id,
               ad_group_criterion.user_list.user_list, campaign.id
        FROM ad_group_criterion WHERE campaign.id = {CAMPAIGN}
          AND ad_group_criterion.type = 'USER_LIST'
          AND ad_group_criterion.status != 'REMOVED'"""):
        lid = int(r.ad_group_criterion.user_list.user_list.split("/")[-1])
        ag_lists.setdefault(r.ad_group.id, {})[lid] = \
            r.ad_group_criterion.criterion_id
    if EXISTING_AD_GROUP not in ag_names:
        print(f"ABORT: ad group {EXISTING_AD_GROUP} not found")
        return 1

    sizes = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT user_list.id, user_list.name, user_list.size_for_display
        FROM user_list"""):
        sizes[r.user_list.id] = (r.user_list.name,
                                 r.user_list.size_for_display)

    print(f"\n3. SPLIT THE AUDIENCES")
    print(f"   {ag_names[EXISTING_AD_GROUP]!r} holds "
          f"{len(ag_lists.get(EXISTING_AD_GROUP, {}))} lists today:")
    for lid in ag_lists.get(EXISTING_AD_GROUP, {}):
        nm, sz = sizes.get(lid, ("?", 0))
        print(f"      [{lid}] {sz:>7,} {nm!r}")
    print(f"   -> rename it {GENERAL_NAME!r}, keep "
          f"{[sizes[l][0] for l in KEEP_ON_GENERAL if l in sizes]}")
    print(f"   -> remove from it: "
          f"{[sizes[l][0] for l in MOVE_OFF_GENERAL if l in sizes]}")
    existing_tier_names = set(ag_names.values())
    for nm, lists in TIERS:
        tot = sum(sizes.get(l, ('', 0))[1] for l in lists)
        state = "ALREADY EXISTS" if nm in existing_tier_names else "create"
        print(f"   -> {state}: {nm!r}  {tot:,} users  "
              f"{[sizes.get(l, ('?',))[0] for l in lists]}")

    ads = {}
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.id, ad_group_ad.ad.id, ad_group_ad.status, campaign.id
        FROM ad_group_ad WHERE campaign.id = {CAMPAIGN}
          AND ad_group_ad.status != 'REMOVED'"""):
        ads[r.ad_group_ad.ad.id] = (r.ad_group.id, r.ad_group_ad.status.name)
    print(f"\n4. LOGO + STALE AD")
    print(f"   ads today: {[(i, s) for i, (g, s) in ads.items()]}")
    print(f"   -> build a new RDA per ad group with square logo {SQUARE_LOGO} "
          f"and landscape logo {LANDSCAPE_LOGO}")
    print(f"      (RDA creative is immutable, so the logo needs a new ad)")
    print(f"   -> PAUSE the current live ad once its replacement exists")
    print(f"   -> REMOVE the stale paused ad {STALE_AD}"
          if STALE_AD in ads else f"   -> stale ad {STALE_AD} already gone")

    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
        return 0

    # ---- 3a. rename the broad ad group, drop the moved lists ---------------
    ag_svc = client.get_service("AdGroupService")
    op = client.get_type("AdGroupOperation")
    op.update.resource_name = ag_svc.ad_group_path(cust, EXISTING_AD_GROUP)
    op.update.name = GENERAL_NAME
    op.update_mask.paths.append("name")
    ag_svc.mutate_ad_groups(customer_id=cust, operations=[op])
    print(f"  renamed ad group -> {GENERAL_NAME!r}")

    crit_svc = client.get_service("AdGroupCriterionService")
    rm = []
    for lid in MOVE_OFF_GENERAL:
        cid = ag_lists.get(EXISTING_AD_GROUP, {}).get(lid)
        if cid:
            o = client.get_type("AdGroupCriterionOperation")
            o.remove = crit_svc.ad_group_criterion_path(
                cust, EXISTING_AD_GROUP, cid)
            rm.append(o)
    if rm:
        crit_svc.mutate_ad_group_criteria(customer_id=cust, operations=rm)
        print(f"  removed {len(rm)} list(s) from the broad ad group")

    # ---- 3b. create the intent-tier ad groups ------------------------------
    new_groups = {}
    make = [(nm, l) for nm, l in TIERS if nm not in existing_tier_names]
    if make:
        ops = []
        for nm, _ in make:
            o = client.get_type("AdGroupOperation")
            a = o.create
            a.name = nm
            a.campaign = client.get_service("CampaignService").campaign_path(
                cust, CAMPAIGN)
            a.type_ = e.AdGroupTypeEnum.DISPLAY_STANDARD
            a.status = e.AdGroupStatusEnum.ENABLED
            ops.append(o)
        rns = [r.resource_name for r in ag_svc.mutate_ad_groups(
            customer_id=cust, operations=ops).results]
        new_groups = dict(zip([nm for nm, _ in make], rns))
        print(f"  created {len(rns)} ad group(s)")

        ops = []
        for nm, lists in make:
            for lid in lists:
                o = client.get_type("AdGroupCriterionOperation")
                cr = o.create
                cr.ad_group = new_groups[nm]
                cr.user_list.user_list = f"customers/{cust}/userLists/{lid}"
                cr.status = e.AdGroupCriterionStatusEnum.ENABLED
                ops.append(o)
        crit_svc.mutate_ad_group_criteria(customer_id=cust, operations=ops)
        print(f"  attached {len(ops)} user list(s) to the new ad groups")

    # ---- 4. new RDAs with a logo, in every ad group ------------------------
    def build_rda(ad_group_rn):
        o = client.get_type("AdGroupAdOperation")
        a = o.create
        a.ad_group = ad_group_rn
        a.status = e.AdGroupAdStatusEnum.ENABLED
        ad = a.ad
        ad.final_urls.append(FINAL_URL)
        rd = ad.responsive_display_ad
        rd.business_name = BUSINESS_NAME
        rd.long_headline.text = LONG_HEADLINE
        for h in HEADLINES:
            t = client.get_type("AdTextAsset")
            t.text = h
            rd.headlines.append(t)
        for d in DESCRIPTIONS:
            t = client.get_type("AdTextAsset")
            t.text = d
            rd.descriptions.append(t)
        for i in MARKETING_IMAGES:
            im = client.get_type("AdImageAsset")
            im.asset = asset_rn(i)
            rd.marketing_images.append(im)
        for i in SQUARE_IMAGES:
            im = client.get_type("AdImageAsset")
            im.asset = asset_rn(i)
            rd.square_marketing_images.append(im)
        im = client.get_type("AdImageAsset")
        im.asset = asset_rn(SQUARE_LOGO)
        rd.square_logo_images.append(im)
        im = client.get_type("AdImageAsset")
        im.asset = asset_rn(LANDSCAPE_LOGO)
        rd.logo_images.append(im)
        return o

    ad_svc = client.get_service("AdGroupAdService")
    targets = [ag_svc.ad_group_path(cust, EXISTING_AD_GROUP)] + \
              [new_groups[nm] for nm, _ in TIERS if nm in new_groups]
    ops = [build_rda(rn) for rn in targets]
    made = ad_svc.mutate_ad_group_ads(customer_id=cust, operations=ops)
    print(f"  created {len(made.results)} responsive display ad(s) with a logo")

    # pause the old live ad, remove the stale one
    ops = []
    for ad_id, (gid, st) in ads.items():
        if ad_id == STALE_AD:
            o = client.get_type("AdGroupAdOperation")
            o.remove = ad_svc.ad_group_ad_path(cust, gid, ad_id)
            ops.append(o)
        elif st == "ENABLED":
            o = client.get_type("AdGroupAdOperation")
            o.update.resource_name = ad_svc.ad_group_ad_path(cust, gid, ad_id)
            o.update.status = e.AdGroupAdStatusEnum.PAUSED
            o.update_mask.paths.append("status")
            ops.append(o)
    if ops:
        ad_svc.mutate_ad_group_ads(customer_id=cust, operations=ops)
        print(f"  retired {len(ops)} old ad(s) (stale removed, live paused)")

    # ---- read-back --------------------------------------------------------
    print("\n--- read-back ---")
    print(f"  feed: merchant_id {mc} (unchanged)")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.id, ad_group.name, ad_group.status,
               ad_group.primary_status, campaign.id
        FROM ad_group WHERE campaign.id = {CAMPAIGN}
          AND ad_group.status != 'REMOVED' ORDER BY ad_group.name"""):
        gid = r.ad_group.id
        lists = [sizes.get(int(x.ad_group_criterion.user_list.user_list
                               .split("/")[-1]), ("?", 0))
                 for x in ga.search(customer_id=cust, query=f"""
            SELECT ad_group_criterion.user_list.user_list, ad_group.id
            FROM ad_group_criterion WHERE ad_group.id = {gid}
              AND ad_group_criterion.type = 'USER_LIST'
              AND ad_group_criterion.status != 'REMOVED'""")]
        nads = [(x.ad_group_ad.ad.id, x.ad_group_ad.status.name,
                 len(x.ad_group_ad.ad.responsive_display_ad.square_logo_images)
                 + len(x.ad_group_ad.ad.responsive_display_ad.logo_images))
                for x in ga.search(customer_id=cust, query=f"""
            SELECT ad_group_ad.ad.id, ad_group_ad.status,
                   ad_group_ad.ad.responsive_display_ad.square_logo_images,
                   ad_group_ad.ad.responsive_display_ad.logo_images, ad_group.id
            FROM ad_group_ad WHERE ad_group.id = {gid}
              AND ad_group_ad.status != 'REMOVED'""")]
        print(f"\n  {r.ad_group.name!r} [{gid}] {r.ad_group.status.name} "
              f"{r.ad_group.primary_status.name}")
        for nm, sz in lists:
            print(f"      list {sz:>7,}  {nm!r}")
        for aid, st, logos in nads:
            print(f"      ad {aid} {st} logos={logos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
