"""Build the BetterPatio Performance Max campaign with brand-level asset groups.

Runs as a dry run by default -- the API validates the whole request and changes
nothing. Pass --live to actually write. The campaign is created PAUSED either
way; enabling it and pausing the old campaigns is a separate, deliberate step.

Everything is sent as one atomic mutate. If any operation is rejected the whole
build is rolled back, so the account never ends up half-built.
"""
import argparse, json, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

FUNNEL = "https://betterpatio.com/pages/custom-outdoor-kitchens"
MERCHANT_ID = 101451631
BUDGET_MICROS = 110_000_000
BUSINESS_NAME = "BetterPatio.com"
KITCHEN_TYPES = ["bbq island", "bbq island accessories", "outdoor kitchens"]

ASSET_GROUPS = [
    {"name": "Mont Alpi", "brands": ["mont alpi"], "images": "Mont Alpi",
     "headlines": ["Mont Alpi Outdoor Kitchens", "Mont Alpi BBQ Islands", "Authorized Dealer",
                   "No Tax & Free Shipping", "Built In BBQ, Fridge & More", "Speak To An Expert 24/7",
                   "Fully Customizable", "Bundle & Save Big", "Commercial Grade Products",
                   "Pro & Trade Accounts"],
     "long_headlines": ["Mont Alpi Outdoor Kitchen Islands - Authorized Dealer, No Tax & Free Shipping",
                        "Complete Mont Alpi BBQ Islands With Built-In Grill, Fridge, Sink & Storage"],
     "descriptions": ["Call in to design your Mont Alpi outdoor kitchen.",
                      "Authorized Mont Alpi dealer. No sales tax and free shipping on every island.",
                      "Complete islands with built-in grill, refrigeration, sink and storage.",
                      "Trade pricing available for contractors, designers and builders."]},
    {"name": "Cal Flame", "brands": ["cal flame"], "images": "Cal Flame",
     "headlines": ["Cal Flame Outdoor Kitchens", "Cal Flame BBQ Islands", "Grand Pavilion Islands",
                   "Authorized Dealer", "No Tax & Free Shipping", "Fully Customizable",
                   "Speak To An Expert 24/7", "Bundle & Save Big", "Commercial Grade Products",
                   "Pro & Trade Accounts"],
     "long_headlines": ["Cal Flame Outdoor Kitchen Islands - Authorized Dealer, No Tax & Free Shipping",
                        "Customizable Cal Flame BBQ Islands Built To Your Exact Specification"],
     "descriptions": ["Call in to design your Cal Flame outdoor kitchen.",
                      "Authorized Cal Flame dealer. No sales tax and free shipping on every island.",
                      "Customizable BBQ islands from compact to full Grand Pavilion builds.",
                      "Trade pricing available for contractors, designers and builders."]},
    {"name": "BetterPatio House Brands", "images": "BetterPatio House Brands",
     "brands": ["ufinish by betterpatio outdoor kitchens", "betterpatio mountain series",
                "betterpatio.com", "betterpatio designer series", "betterpatio",
                "betterpatio unfinished outdoor kitchens", "betterpatio solace series"],
     "headlines": ["BetterPatio Outdoor Kitchens", "Build Your Own Kitchen", "Mountain & Designer Series",
                   "No Tax & Free Shipping", "Fully Customizable", "Speak To An Expert 24/7",
                   "Built In BBQ, Fridge & More", "Bundle & Save Big", "Commercial Grade Products",
                   "Pro & Trade Accounts"],
     "long_headlines": ["Build Your Own Outdoor Kitchen - Mountain, Designer & Ufinish Series",
                        "Custom BetterPatio Outdoor Kitchen Islands With No Tax And Free Shipping"],
     "descriptions": ["Call in to design your custom outdoor kitchen.",
                      "Build your own outdoor kitchen island to your exact specification.",
                      "Mountain Series, Designer Series and Ufinish builds in stock.",
                      "Trade pricing available for contractors, designers and builders."]},
]

LOGO_ASSET_ID = 38776858109   # 1980x1980, already in use as the account logo


def check_text_limits():
    """Google rejects over-length text at mutate time; fail here with a clearer message."""
    bad = []
    for g in ASSET_GROUPS:
        for h in g["headlines"]:
            if len(h) > 30: bad.append(f"{g['name']}: headline {len(h)}>30 {h!r}")
        for h in g["long_headlines"]:
            if len(h) > 90: bad.append(f"{g['name']}: long headline {len(h)}>90 {h!r}")
        for d in g["descriptions"]:
            if len(d) > 90: bad.append(f"{g['name']}: description {len(d)}>90 {d!r}")
        if len(g["descriptions"][0]) > 60:
            bad.append(f"{g['name']}: first description must be <=60, is {len(g['descriptions'][0])}")
    if len(BUSINESS_NAME) > 25:
        bad.append(f"business name {len(BUSINESS_NAME)}>25")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="actually write (default: validate only)")
    args = ap.parse_args()

    bad = check_text_limits()
    if bad:
        print("TEXT LIMIT VIOLATIONS:"); [print("  " + b) for b in bad]; sys.exit(1)

    client = get_client()
    acct = resolve_account("BetterPatio.com", client=client)
    CID = acct["id"]
    images = json.load(open("build_specs/_asset_ids.json"))

    e = client.enums
    ops = []
    def op():
        o = client.get_type("MutateOperation"); ops.append(o); return o

    tmp = [0]
    def nxt():
        tmp[0] -= 1; return tmp[0]

    # --- budget ---------------------------------------------------------
    bid = nxt()
    budget_rn = f"customers/{CID}/campaignBudgets/{bid}"
    b = op().campaign_budget_operation.create
    b.resource_name = budget_rn
    b.name = "BP · PMax — Outdoor Kitchens"
    b.amount_micros = BUDGET_MICROS
    b.delivery_method = e.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False

    # --- campaign -------------------------------------------------------
    cid_t = nxt()
    camp_rn = f"customers/{CID}/campaigns/{cid_t}"
    c = op().campaign_operation.create
    c.resource_name = camp_rn
    c.name = "BP · PMax — Outdoor Kitchens"
    c.status = e.CampaignStatusEnum.PAUSED                     # never auto-live
    c.advertising_channel_type = e.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
    c.campaign_budget = budget_rn
    c.maximize_conversions = client.get_type("MaximizeConversions")
    c.shopping_setting.merchant_id = MERCHANT_ID
    c.contains_eu_political_advertising = (
        e.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    # v25: final URL expansion is governed by asset automation, not a campaign flag.
    aa = client.get_type("Campaign").AssetAutomationSetting()
    aa.asset_automation_type = e.AssetAutomationTypeEnum.FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION
    aa.asset_automation_status = e.AssetAutomationStatusEnum.OPTED_OUT
    c.asset_automation_settings.append(aa)

    # Brand guidelines are on by default for new PMax campaigns, which means the
    # logo and business name are linked to the CAMPAIGN, not to each asset group.
    bn_rn = f"customers/{CID}/assets/{nxt()}"
    bna = op().asset_operation.create
    bna.resource_name = bn_rn
    bna.text_asset.text = BUSINESS_NAME
    for asset_rn, ft in [(bn_rn, e.AssetFieldTypeEnum.BUSINESS_NAME),
                         (f"customers/{CID}/assets/{LOGO_ASSET_ID}", e.AssetFieldTypeEnum.LOGO)]:
        ca = op().campaign_asset_operation.create
        ca.campaign = camp_rn
        ca.asset = asset_rn
        ca.field_type = ft

    # --- asset groups ---------------------------------------------------
    for g in ASSET_GROUPS:
        ag_t = nxt()
        ag_rn = f"customers/{CID}/assetGroups/{ag_t}"
        ag = op().asset_group_operation.create
        ag.resource_name = ag_rn
        ag.campaign = camp_rn
        ag.name = f"BP · {g['name']}"
        ag.final_urls.append(FUNNEL)
        ag.status = e.AssetGroupStatusEnum.ENABLED

        pending = []
        def add_text(text, field_type):
            a_rn = f"customers/{CID}/assets/{nxt()}"
            a = op().asset_operation.create
            a.resource_name = a_rn
            a.text_asset.text = text
            pending.append((a_rn, field_type))

        for h in g["headlines"]:       add_text(h, e.AssetFieldTypeEnum.HEADLINE)
        for h in g["long_headlines"]:  add_text(h, e.AssetFieldTypeEnum.LONG_HEADLINE)
        for d in g["descriptions"]:    add_text(d, e.AssetFieldTypeEnum.DESCRIPTION)
        for a_rn, field_type in pending:
            link = op().asset_group_asset_operation.create
            link.asset_group = ag_rn; link.asset = a_rn; link.field_type = field_type

        for ft, ids in images[g["images"]].items():
            for aid in ids:
                if aid == LOGO_ASSET_ID:      # reserve the logo for the LOGO slot
                    continue
                link = op().asset_group_asset_operation.create
                link.asset_group = ag_rn
                link.asset = f"customers/{CID}/assets/{aid}"
                link.field_type = getattr(e.AssetFieldTypeEnum, ft)

        # --- listing group filter tree: brand -> product type ------------
        root_t = nxt()
        root_rn = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{root_t}"
        r = op().asset_group_listing_group_filter_operation.create
        r.resource_name = root_rn
        r.asset_group = ag_rn
        r.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
        r.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING

        for brand in g["brands"]:
            b_t = nxt()
            b_rn = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{b_t}"
            bn = op().asset_group_listing_group_filter_operation.create
            bn.resource_name = b_rn
            bn.asset_group = ag_rn
            bn.type_ = e.ListingGroupFilterTypeEnum.SUBDIVISION
            bn.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            bn.parent_listing_group_filter = root_rn
            bn.case_value.product_brand.value = brand

            for pt in KITCHEN_TYPES:
                n = op().asset_group_listing_group_filter_operation.create
                n.resource_name = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
                n.asset_group = ag_rn
                n.type_ = e.ListingGroupFilterTypeEnum.UNIT_INCLUDED
                n.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
                n.parent_listing_group_filter = b_rn
                n.case_value.product_type.value = pt
                n.case_value.product_type.level = e.ListingGroupFilterProductTypeLevelEnum.LEVEL1
            # every subdivision needs its catch-all sibling
            o = op().asset_group_listing_group_filter_operation.create
            o.resource_name = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
            o.asset_group = ag_rn
            o.type_ = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
            o.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
            o.parent_listing_group_filter = b_rn
            o.case_value.product_type.level = e.ListingGroupFilterProductTypeLevelEnum.LEVEL1

        o = op().asset_group_listing_group_filter_operation.create
        o.resource_name = f"customers/{CID}/assetGroupListingGroupFilters/{ag_t}~{nxt()}"
        o.asset_group = ag_rn
        o.type_ = e.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
        o.listing_source = e.ListingGroupFilterListingSourceEnum.SHOPPING
        o.parent_listing_group_filter = root_rn
        # "Everything else": the brand dimension must be PRESENT but with no
        # value. Assigning "" instead would mean "brand is the empty string".
        o.case_value._pb.product_brand.SetInParent()

    ga = client.get_service("GoogleAdsService")
    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = CID
    req.mutate_operations.extend(ops)
    req.validate_only = not args.live

    mode = "LIVE WRITE" if args.live else "DRY RUN (validate_only)"
    print(f"{mode}: {len(ops)} operations, campaign will be created PAUSED")
    try:
        resp = ga.mutate(request=req)
        if args.live:
            made = [r.campaign_result.resource_name for r in resp.mutate_operation_responses
                    if r.campaign_result.resource_name]
            print("SUCCESS — created:", made)
        else:
            print("VALIDATED OK — nothing written. Re-run with --live to build.")
    except Exception as ex:
        print("FAILED:")
        print(str(ex)[:2500])
        sys.exit(1)


if __name__ == "__main__":
    main()
