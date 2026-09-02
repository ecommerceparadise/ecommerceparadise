"""Attach negative keyword lists to the campaigns built in this session.

Only the universal junk lists are attached. The accounts also hold large
Shopping-sculpting sets that must NOT go on a general campaign:

  - "All Products 1-5" (BetterPatio, 18,453 bare SKU numbers) and "SKU"
    (Fountains, 1,761) exist to push SKU searches between Shopping campaigns.
    On a PMax campaign they would block the product searches we want.
  - The "Brands" sets contain the brands each store SELLS -- Cal Flame, Bull,
    Giannini, The Outdoor Plus. Attaching those would suppress exactly the
    searches these campaigns are built to win.

Also creates one new set for Fountains USA holding the brand NAMES Trevor does
not want to advertise. The listing filter already keeps those products out of
the ads; this keeps the ads out of those brands' searches, which is the other
half of the same instruction.
"""
import argparse, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

UNIVERSAL = {
    "BetterPatio.com": [(11765673294, "EP Generic"), (12052054569, "BP Generic Irrelevants")],
    "Fountains USA":   [(11712268851, "Generic"), (11765673294, "EP Generic")],
}
NEW_CAMPAIGNS = {
    "BetterPatio.com": ["BP · PMax — Outdoor Kitchens"],
    "Fountains USA":   ["FUSA - PMax - Fountains (feed only)",
                        "FUSA - Dynamic Display Remarketing"],
}
# Brands Trevor rules out on margin: he ranks page 1 organically and the margin is thin.
FUSA_EXCLUDED_BRAND_TERMS = ["sunnydaze", "sunnydaze decor", "smart solar", "smart living"]

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); e = client.enums

for account, campaigns in NEW_CAMPAIGNS.items():
    acct = resolve_account(account, client=client)
    CID = acct["id"]
    ga = client.get_service("GoogleAdsService")
    print(f"\n=== {account} ===")

    ids = {}
    for n in campaigns:
        rows = list(ga.search(customer_id=CID, query=f"""
        SELECT campaign.id FROM campaign WHERE campaign.name = '{n}'"""))
        if not rows:
            print(f"  SKIP, campaign not found: {n}"); continue
        ids[n] = rows[0].campaign.id

    existing = {(r.campaign.id, r.shared_set.id) for r in ga.search(customer_id=CID, query="""
    SELECT campaign.id, shared_set.id FROM campaign_shared_set""")}

    ops = []
    def op():
        o = client.get_type("MutateOperation"); ops.append(o); return o

    sets = list(UNIVERSAL[account])

    if account == "Fountains USA":
        # one shared set carrying the excluded brand names
        have = list(ga.search(customer_id=CID, query="""
        SELECT shared_set.id, shared_set.name FROM shared_set
        WHERE shared_set.name = 'Excluded Brands - Margin' AND shared_set.status != 'REMOVED'"""))
        if have:
            sets.append((have[0].shared_set.id, "Excluded Brands - Margin (existing)"))
        else:
            ss_rn = f"customers/{CID}/sharedSets/-1"
            s = op().shared_set_operation.create
            s.resource_name = ss_rn
            s.name = "Excluded Brands - Margin"
            s.type_ = e.SharedSetTypeEnum.NEGATIVE_KEYWORDS
            for t in FUSA_EXCLUDED_BRAND_TERMS:
                sc = op().shared_criterion_operation.create
                sc.shared_set = ss_rn
                sc.keyword.text = t
                sc.keyword.match_type = e.KeywordMatchTypeEnum.PHRASE
            for n in ids:
                if "PMax" in n:                       # search-facing campaign only
                    link = op().campaign_shared_set_operation.create
                    link.campaign = f"customers/{CID}/campaigns/{ids[n]}"
                    link.shared_set = ss_rn
            print(f"  creating 'Excluded Brands - Margin' with {len(FUSA_EXCLUDED_BRAND_TERMS)} "
                  f"phrase negatives: {', '.join(FUSA_EXCLUDED_BRAND_TERMS)}")

    for n, cid in ids.items():
        for sid, label in sets:
            if isinstance(sid, int) and (cid, sid) in existing:
                print(f"  already linked: {n[:34]} <- {label}"); continue
            link = op().campaign_shared_set_operation.create
            link.campaign = f"customers/{CID}/campaigns/{cid}"
            link.shared_set = f"customers/{CID}/sharedSets/{sid}"
            print(f"  link: {n[:38]:<40} <- {label}")

    if not ops:
        print("  nothing to do"); continue
    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = CID
    req.mutate_operations.extend(ops)
    req.validate_only = not args.live
    try:
        client.get_service("GoogleAdsService").mutate(request=req)
        print(f"  {'APPLIED' if args.live else 'VALIDATED'} ({len(ops)} operations)")
    except Exception as ex:
        print("  FAILED:"); print(str(ex)[:1200]); sys.exit(1)
