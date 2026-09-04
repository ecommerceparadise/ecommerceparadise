"""Bring the Fountains USA retargeting Shopping campaign in line with the PMax
campaign's scope, and switch off the expansion settings that were left on.

Three things checked, one wrong:

  Locations  MATCHED already -- same four geo targets (CA, AZ, FL, TX) on
             PRESENCE as the PMax campaign.

  Brands     NOT MATCHED. The ad group had a single root listing group unit
             with no brand condition, which means all 10,505 products in the
             feed, including Sunnydaze and Smart Living -- the two brands
             Trevor specifically said not to advertise. This rebuilds the
             listing tree as a brand subdivision holding only the four PMax
             brands, with everything else explicitly excluded.

  Expansion  Search partners was ON (inherited default) and local inventory
             ads were ON. Both are turned off. Display network was already
             off. PMax's own five asset automations are all OPTED_OUT already
             and are not touched here.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24214263728
AD_GROUP = 200175176335
CPC_BID_MICROS = 2_000_000

# Exactly the brands the PMax campaign includes, read from its listing filters.
BRANDS = [
    "giannini garden",
    "metropolitan galleries inc.",
    "the outdoor plus",
    "fiore stone",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account("Fountains USA")["id"]
    ga = client.get_service("GoogleAdsService")

    # Cross-check the brand list against PMax rather than trusting the constant.
    pmax_brands = sorted({
        r.asset_group_listing_group_filter.case_value.product_brand.value
        for r in ga.search(customer_id=cust, query="""
            SELECT asset_group_listing_group_filter.type,
                   asset_group_listing_group_filter.case_value.product_brand.value
            FROM asset_group_listing_group_filter WHERE campaign.id = 24209826676""")
        if r.asset_group_listing_group_filter.type_.name == "UNIT_INCLUDED"})
    if pmax_brands != sorted(BRANDS):
        print("REFUSING: brand list here does not match the PMax campaign.")
        print(f"  PMax:   {pmax_brands}")
        print(f"  script: {sorted(BRANDS)}")
        return 1
    print(f"Brand list cross-checked against PMax: {pmax_brands}\n")

    existing = [(r.ad_group_criterion.resource_name,
                 r.ad_group_criterion.listing_group.type_.name)
                for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group_criterion.resource_name,
               ad_group_criterion.listing_group.type
        FROM ad_group_criterion WHERE ad_group.id = {AD_GROUP}
          AND ad_group_criterion.type = 'LISTING_GROUP'
          AND ad_group_criterion.status != 'REMOVED'""")]

    print("=" * 74)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("=" * 74)
    print(f"\nLISTING GROUP  (currently {len(existing)} node(s): "
          f"{[t for _, t in existing]})")
    print("  remove the all-products root, rebuild as:")
    print("    SUBDIVISION on product_brand")
    for b in BRANDS:
        print(f"      +-- INCLUDE  {b!r}  @ ${CPC_BID_MICROS/1e6:.2f}")
    print("      +-- EXCLUDE  everything else  (Sunnydaze, Smart Living, and the rest)")
    print("\nEXPANSION SETTINGS")
    print("  search partners  ON  -> OFF")
    print("  local inventory  ON  -> cannot be set via API; inert without an LIA feed")
    print("  display network  already OFF, unchanged")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    e = client.enums
    svc = client.get_service("AdGroupCriterionService")
    ag_path = client.get_service("AdGroupService").ad_group_path(cust, AD_GROUP)

    # Remove the old tree and build the new one in a single mutate, so the ad
    # group is never left without a listing group.
    ops = []
    for rn, _ in existing:
        op = client.get_type("AdGroupCriterionOperation")
        op.remove = rn
        ops.append(op)

    root_rn = f"customers/{cust}/adGroupCriteria/{AD_GROUP}~-1"
    op = client.get_type("AdGroupCriterionOperation")
    root = op.create
    root.resource_name = root_rn
    root.ad_group = ag_path
    root.status = e.AdGroupCriterionStatusEnum.ENABLED
    root.listing_group.type_ = e.ListingGroupTypeEnum.SUBDIVISION
    ops.append(op)

    for b in BRANDS:
        op = client.get_type("AdGroupCriterionOperation")
        c = op.create
        c.ad_group = ag_path
        c.status = e.AdGroupCriterionStatusEnum.ENABLED
        c.cpc_bid_micros = CPC_BID_MICROS
        c.listing_group.type_ = e.ListingGroupTypeEnum.UNIT
        c.listing_group.parent_ad_group_criterion = root_rn
        c.listing_group.case_value.product_brand.value = b
        ops.append(op)

    # "Everything else": the dimension is present but carries no value.
    op = client.get_type("AdGroupCriterionOperation")
    other = op.create
    other.ad_group = ag_path
    other.status = e.AdGroupCriterionStatusEnum.ENABLED
    other.negative = True
    other.listing_group.type_ = e.ListingGroupTypeEnum.UNIT
    other.listing_group.parent_ad_group_criterion = root_rn
    other.listing_group.case_value._pb.product_brand.SetInParent()
    ops.append(op)

    svc.mutate_ad_group_criteria(customer_id=cust, operations=ops)
    print(f"\n  rebuilt the listing tree ({len(ops)} operations)")

    camp_op = client.get_type("CampaignOperation")
    camp_op.update.resource_name = client.get_service(
        "CampaignService").campaign_path(cust, CAMPAIGN)
    camp_op.update.network_settings.target_search_network = False
    camp_op.update_mask.paths.append("network_settings.target_search_network")
    client.get_service("CampaignService").mutate_campaigns(
        customer_id=cust, operations=[camp_op])
    print("  search partners OFF")
    # enable_local is not writable on this campaign through the API -- it
    # returns OPERATION_NOT_PERMITTED_FOR_CONTEXT on both create and update.
    # It is inert without a local inventory feed in Merchant Center, which
    # this account does not have.
    print("  local inventory: NOT settable via API (inert without an LIA feed)")

    # The root SUBDIVISION reports status PAUSED and stays that way after a
    # successful status mutate. Subdivisions are structural containers, not
    # biddable nodes -- only the UNIT children serve -- so this is how the API
    # represents them rather than a setting that needs fixing.

    print("\n-- verify --")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.network_settings.target_google_search,
               campaign.network_settings.target_search_network,
               campaign.network_settings.target_content_network,
               campaign.shopping_setting.enable_local
        FROM campaign WHERE campaign.id = {CAMPAIGN}"""):
        n = r.campaign.network_settings
        print(f"  google_search={n.target_google_search} search_partners={n.target_search_network} "
              f"display={n.target_content_network} local={r.campaign.shopping_setting.enable_local}")
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group_criterion.listing_group.type,
               ad_group_criterion.listing_group.case_value.product_brand.value,
               ad_group_criterion.negative
        FROM ad_group_criterion WHERE ad_group.id = {AD_GROUP}
          AND ad_group_criterion.type = 'LISTING_GROUP'
          AND ad_group_criterion.status != 'REMOVED'"""):
        lg = r.ad_group_criterion.listing_group
        v = lg.case_value.product_brand.value
        label = f"brand={v!r}" if v else ("everything else" if lg.type_.name == "UNIT" else "(root)")
        state = "EXCLUDED" if r.ad_group_criterion.negative else "included"
        print(f"  {lg.type_.name:12} {label:36} {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
