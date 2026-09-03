"""Add search themes to the BetterPatio PMax asset groups.

Search themes are signals, not targeting: they tell Google what intent an asset
group is meant to reach, but carry no bid or match type. Up to 25 per asset
group. Every theme below is drawn from a term that has actually converted in
this account, rather than invented.

Brand-specific themes go to the matching asset group; the shared kitchen-intent
themes go to all three.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

CAMPAIGN = 24209664922
SHARED = [
    "custom outdoor kitchen", "outdoor kitchen island", "bbq island",
    "built in bbq outdoor kitchen", "outdoor kitchen design",
    "modular outdoor kitchen", "prefab outdoor kitchen",
    "outdoor kitchen with grill and fridge", "complete outdoor kitchen",
    "outdoor grill island", "custom bbq island", "outdoor kitchen cabinets",
]
PER_GROUP = {
    "BP · Mont Alpi":                 ["mont alpi outdoor kitchen", "mont alpi bbq island",
                                       "mont alpi grill island"],
    "BP · Cal Flame":                 ["cal flame bbq island", "cal flame outdoor kitchen",
                                       "cal flame grand pavilion"],
    "BP · BetterPatio House Brands":  ["build your own outdoor kitchen",
                                       "unfinished outdoor kitchen island",
                                       "diy outdoor kitchen frame"],
}

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); acct = resolve_account("BetterPatio.com", client=client)
CID = acct["id"]
ga = client.get_service("GoogleAdsService")

groups = {r.asset_group.name: r.asset_group.id for r in ga.search(customer_id=CID, query=f"""
SELECT asset_group.id, asset_group.name FROM asset_group
WHERE campaign.id = {CAMPAIGN}""")}
have = {}
for r in ga.search(customer_id=CID, query=f"""
SELECT asset_group.id, asset_group_signal.search_theme.text
FROM asset_group_signal WHERE campaign.id = {CAMPAIGN}"""):
    have.setdefault(r.asset_group.id, set()).add(
        r.asset_group_signal.search_theme.text.lower())

ops = []
def op():
    o = client.get_type("MutateOperation"); ops.append(o); return o

for name, gid in groups.items():
    themes = SHARED + PER_GROUP.get(name, [])
    existing = have.get(gid, set())
    new = [t for t in themes if t.lower() not in existing]
    if len(existing) + len(new) > 25:
        new = new[: 25 - len(existing)]
    for t in new:
        s = op().asset_group_signal_operation.create
        s.asset_group = f"customers/{CID}/assetGroups/{gid}"
        s.search_theme.text = t
    print(f"  {name:<32} {len(existing)} existing + {len(new)} new")

print(f"\n{'LIVE' if args.live else 'DRY RUN'}: {len(ops)} search themes")
if not ops:
    print("nothing to do"); sys.exit(0)
req = client.get_type("MutateGoogleAdsRequest")
req.customer_id = CID; req.mutate_operations.extend(ops); req.validate_only = not args.live
try:
    ga.mutate(request=req)
    print("DONE" if args.live else "VALIDATED - nothing written")
except Exception as ex:
    print("FAILED:"); print(str(ex)[:1200]); sys.exit(1)
