"""BetterPatio cutover: settings hardening + switch from old campaigns to new.

Dry run unless --live. Sent as one atomic mutate, so a rejected operation
leaves the account exactly as it was rather than half switched over.

What it does:
  1. New PMax gets the lower-48 geo list copied from the remarketing campaigns,
     with location option PRESENCE (never presence-or-interest).
  2. optimized_targeting OFF on both remarketing ad groups. Left on, Google
     serves past the remarketing lists to people who never visited the site.
  3. Budgets set to the agreed $150/day split: PMax 110, static 20, dynamic 20.
  4. Pauses every other enabled campaign and enables the new PMax, in the same
     operation, so the account is never running both structures at once.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

PMAX, DYNAMIC_RT, STATIC_RT = 24209664922, 24040677834, 24064549810
KEEP = {PMAX, DYNAMIC_RT, STATIC_RT}
BUDGETS = {PMAX: 110_000_000, STATIC_RT: 20_000_000, DYNAMIC_RT: 20_000_000}

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()

client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]; e = client.enums
ga = client.get_service("GoogleAdsService")
ops = []
def op():
    o = client.get_type("MutateOperation"); ops.append(o); return o

# --- 1. lower-48 geo on the new PMax, copied from the proven remarketing setup
geos = [r.campaign_criterion.location.geo_target_constant
        for r in ga.search(customer_id=CID, query=f"""
        SELECT campaign_criterion.location.geo_target_constant FROM campaign_criterion
        WHERE campaign.id = {STATIC_RT} AND campaign_criterion.type = 'LOCATION'
          AND campaign_criterion.negative = FALSE""")]
assert len(geos) == 48, f"expected 48 states, found {len(geos)}"
existing = len(list(ga.search(customer_id=CID, query=f"""
SELECT campaign_criterion.criterion_id FROM campaign_criterion
WHERE campaign.id = {PMAX} AND campaign_criterion.type = 'LOCATION'""")))
if existing == 0:
    for g in geos:
        cc = op().campaign_criterion_operation.create
        cc.campaign = f"customers/{CID}/campaigns/{PMAX}"
        cc.location.geo_target_constant = g
        cc.negative = False

c = op().campaign_operation
c.update.resource_name = f"customers/{CID}/campaigns/{PMAX}"
c.update.geo_target_type_setting.positive_geo_target_type = (
    e.PositiveGeoTargetTypeEnum.PRESENCE)
c.update.geo_target_type_setting.negative_geo_target_type = (
    e.NegativeGeoTargetTypeEnum.PRESENCE)
c.update_mask.paths.append("geo_target_type_setting.positive_geo_target_type")
c.update_mask.paths.append("geo_target_type_setting.negative_geo_target_type")

# --- 2. kill audience expansion on the remarketing ad groups
for r in ga.search(customer_id=CID, query=f"""
SELECT ad_group.id, ad_group.optimized_targeting_enabled FROM ad_group
WHERE campaign.id IN ({DYNAMIC_RT}, {STATIC_RT}) AND ad_group.status != 'REMOVED'"""):
    a = op().ad_group_operation
    a.update.resource_name = f"customers/{CID}/adGroups/{r.ad_group.id}"
    a.update.optimized_targeting_enabled = False
    a.update_mask.paths.append("optimized_targeting_enabled")

# --- 3. budgets ------------------------------------------------------------
for cid, micros in BUDGETS.items():
    row = list(ga.search(customer_id=CID, query=f"""
    SELECT campaign_budget.id, campaign_budget.amount_micros FROM campaign
    WHERE campaign.id = {cid}"""))[0]
    if row.campaign_budget.amount_micros != micros:
        b = op().campaign_budget_operation
        b.update.resource_name = f"customers/{CID}/campaignBudgets/{row.campaign_budget.id}"
        b.update.amount_micros = micros
        b.update_mask.paths.append("amount_micros")

# --- 4. the cutover itself -------------------------------------------------
to_pause = []
for r in ga.search(customer_id=CID, query="""
SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status = 'ENABLED'"""):
    if r.campaign.id not in KEEP:
        to_pause.append((r.campaign.id, r.campaign.name))
for cid, name in to_pause:
    p = op().campaign_operation
    p.update.resource_name = f"customers/{CID}/campaigns/{cid}"
    p.update.status = e.CampaignStatusEnum.PAUSED
    p.update_mask.paths.append("status")

en = op().campaign_operation
en.update.resource_name = f"customers/{CID}/campaigns/{PMAX}"
en.update.status = e.CampaignStatusEnum.ENABLED
en.update_mask.paths.append("status")

print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
print(f"  geo criteria added to PMax : {0 if existing else len(geos)} states, PRESENCE")
print(f"  pausing {len(to_pause)} campaigns:")
for _, n in to_pause:
    print(f"      - {n}")
print(f"  enabling: BP · PMax — Outdoor Kitchens")
print(f"  staying enabled: static + dynamic remarketing")

req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID
req.mutate_operations.extend(ops)
req.validate_only = not args.live
try:
    ga.mutate(request=req)
    print("\n" + ("DONE" if args.live else "VALIDATED — nothing written"))
except Exception as ex:
    print("\nFAILED:"); print(str(ex)[:1800]); sys.exit(1)
