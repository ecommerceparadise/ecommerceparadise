"""Rebuild the BetterPatio Search keyword set from what has actually converted.

Every keyword added below earned conversions in this account between 2019 and
2026. The set is restricted to kitchen and design intent -- the job of the
custom kitchen funnel. Grill-product terms that also converted (drop in grill,
built in grills for sale, outdoor barbecues for sale) are deliberately left out:
under the current model PMax and Shopping own product intent.

Brand terms that converted (cal flame $20,496 / 256 conv, napoleon, aog) are
also left out for the same reason -- they belong to the PMax asset groups.

Caveat worth carrying: those historic conversions were Zoho CRM lead uploads,
which stopped in July 2025. These keywords are proven lead generators, but the
measurement that proved it is currently switched off, so nothing here will
report conversions until the Zoho pipeline is restored.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN, AD_GROUP = 23303878302, 190077137940

# (text, match type) -- EXACT where the term is ambiguous between indoor and
# outdoor kitchens or is a bare head term; PHRASE where "outdoor" is explicit.
ADD = [
    ("design your own kitchen",          "EXACT"),   # 789 conv, CPA $4
    ("3d kitchen design",                "EXACT"),   # 775 conv, CPA $2
    ("design my kitchen",                "EXACT"),   #   8 conv, CPA $14
    ("outdoor kitchen",                  "EXACT"),   #  91 conv, CPA $11
    ("outdoor kitchens",                 "EXACT"),   #   7 conv, CPA $6
    ("outdoor spaces design",            "EXACT"),   #  34 conv, CPA $9
    ("built outdoor kitchen",            "PHRASE"),  # 525 conv, CPA $5
    ("outdoor kitchen plans",            "PHRASE"),  #  66 conv, CPA $2
    ("outdoor kitchen companies near me","PHRASE"),  #  49 conv, CPA $4
    ("built in bbq outdoor kitchen",     "PHRASE"),  #  41 conv, CPA $2
    ("outdoor kitchen ideas",            "PHRASE"),  #  55 conv, CPA $21
    ("outdoor kitchen design",           "PHRASE"),  #  45 conv, CPA $10
    ("outdoor kitchen designs",          "PHRASE"),  #  20 conv, CPA $17
    ("backyard kitchen ideas",           "PHRASE"),  #  26 conv, CPA $2
    ("pre built outdoor kitchen islands","PHRASE"),  #  14 conv, CPA $9
    ("outdoor grill island",             "PHRASE"),  #   3 conv, CPA $32
]

# Live keywords that have spent without earning. Paused, never removed.
PAUSE = [
    "build your own outdoor kitchen",  # $582 this campaign / 0 conv, and blocked
                                       # by the 'build your own' phrase negative
    "outdoor kitchen island",          # $568 / 0 conv here, 0 all time
    "pre made bbq islands",            # $82 / 0 conv
    "outdoor kitchens for sale",       # $1,244 all time for 3 conv, CPA $415;
                                       # it is what pulls the bare "outdoor
                                       # kitchen" query, now its own keyword
]

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]; e = client.enums
ga = client.get_service("GoogleAdsService")

# --- guard: never add a keyword the campaign's own negatives would block ------
negs = []
for s in ga.search(customer_id=CID, query=f"""
SELECT shared_set.id, shared_set.name FROM campaign_shared_set
WHERE campaign.id = {CAMPAIGN} AND campaign_shared_set.status = 'ENABLED'"""):
    for c in ga.search(customer_id=CID, query=f"""
    SELECT shared_criterion.keyword.text, shared_criterion.keyword.match_type
    FROM shared_criterion WHERE shared_set.id = {s.shared_set.id}"""):
        negs.append((c.shared_criterion.keyword.text.lower(),
                     c.shared_criterion.keyword.match_type.name, s.shared_set.name))

def blocked_by(text):
    """Negatives match whole words, not substrings, and not close variants."""
    toks = text.lower().split()
    for n, mt, src in negs:
        nt = n.split()
        if mt == "EXACT" and toks == nt: return (n, mt, src)
        if mt == "PHRASE" and any(toks[i:i+len(nt)] == nt
                                  for i in range(len(toks)-len(nt)+1)): return (n, mt, src)
        if mt == "BROAD" and all(w in toks for w in nt): return (n, mt, src)
    return None

existing = {r.ad_group_criterion.keyword.text.lower(): r.ad_group_criterion
            for r in ga.search(customer_id=CID, query=f"""
            SELECT ad_group_criterion.criterion_id, ad_group_criterion.keyword.text,
                   ad_group_criterion.status FROM ad_group_criterion
            WHERE ad_group.id = {AD_GROUP} AND ad_group_criterion.type='KEYWORD'
              AND ad_group_criterion.negative=FALSE
              AND ad_group_criterion.status != 'REMOVED'""")}

ops, skipped, added = [], [], []
def op():
    o = client.get_type("MutateOperation"); ops.append(o); return o

for text, mt in ADD:
    if text.lower() in existing:
        skipped.append((text, "already in the ad group")); continue
    b = blocked_by(text)
    if b:
        skipped.append((text, f"BLOCKED by {b[1]} negative '{b[0]}' ({b[2]})")); continue
    k = op().ad_group_criterion_operation.create
    k.ad_group = f"customers/{CID}/adGroups/{AD_GROUP}"
    k.status = e.AdGroupCriterionStatusEnum.ENABLED
    k.keyword.text = text
    k.keyword.match_type = getattr(e.KeywordMatchTypeEnum, mt)
    added.append((text, mt))

paused = []
for text in PAUSE:
    c = existing.get(text.lower())
    if not c or c.status.name == "PAUSED": continue
    p = op().ad_group_criterion_operation
    p.update.resource_name = f"customers/{CID}/adGroupCriteria/{AD_GROUP}~{c.criterion_id}"
    p.update.status = e.AdGroupCriterionStatusEnum.PAUSED
    p.update_mask.paths.append("status")
    paused.append(text)

print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} operations")
print(f"\n  adding {len(added)} proven keywords:")
for t, mt in added: print(f"      {mt:<7} {t}")
if skipped:
    print(f"\n  skipped {len(skipped)}:")
    for t, why in skipped: print(f"      {t:<38} {why}")
print(f"\n  pausing {len(paused)} non-performers:")
for t in paused: print(f"      {t}")

if not ops:
    print("\nnothing to do"); sys.exit(0)
req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID; req.mutate_operations.extend(ops); req.validate_only = not args.live
try:
    ga.mutate(request=req)
    print("\n" + ("DONE" if args.live else "VALIDATED - nothing written"))
except Exception as ex:
    print("\nFAILED:"); print(str(ex)[:1500]); sys.exit(1)
