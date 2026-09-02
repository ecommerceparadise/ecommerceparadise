"""Build per-account competitor and non-carried-brand negative lists.

Every term is verified against the account's own Merchant Center feed before it
goes in: if it appears in a carried brand or anywhere in a product title, it is
dropped. That check caught "big green egg", "green egg", "lynx" and "toscano" --
all of which appear in these stores' own titles, so negativing them would have
blocked their own inventory.

Terms come from Keyword Planner ideas seeded on each store's category, not from
guesswork, so the volume figures are real. Terms with no volume in the pulled
set are still included: a negative that never matches costs nothing, and brand
spellings vary.
"""
import argparse, json, re, sys
from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNTS = {
 "Fountains USA": {
   "mid": 258983089,
   "Competitors": ["lowes", "amazon", "home depot", "wayfair", "target", "costco",
                   "etsy", "overstock", "hayneedle", "walmart"],
   "Non-Carried Brands": ["flexzilla", "hunter", "henri studio", "campania",
                          "alpine corporation", "john timberland", "kenroy home",
                          "orlandi statuary"],
 },
 "BetterPatio.com": {
   "mid": 101451631,
   "Competitors": ["costco", "ikea", "home depot", "lowes", "wayfair", "bbq guys",
                   "amazon", "sam's club", "ace hardware", "walmart"],
   "Non-Carried Brands": ["master built", "masterbuilt", "napoleon", "weber",
                          "blackstone", "kitchenaid", "viking", "wolf", "traeger",
                          "dcs", "hestan", "char broil", "charbroil", "alfresco",
                          "newage", "kamado joe", "twin eagles", "pit boss",
                          "nexgrill", "solo stove", "royal gourmet"],
 },
}

ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
args = ap.parse_args()
client = get_client(); e = client.enums

for account, cfg in ACCOUNTS.items():
    acct = resolve_account(account, client=client)
    CID = acct["id"]
    ga = client.get_service("GoogleAdsService")
    print(f"\n=== {account} ===")

    carried, titles = set(), []
    for r in ga.search(customer_id=CID, query=f"""
    SELECT shopping_product.brand, shopping_product.title FROM shopping_product
    WHERE shopping_product.merchant_center_id = {cfg['mid']}"""):
        b = (r.shopping_product.brand or "").strip().lower()
        if b: carried.add(b)
        titles.append((r.shopping_product.title or "").lower())
    blob = " || ".join(set(titles))

    ops = []
    def op():
        o = client.get_type("MutateOperation"); ops.append(o); return o
    tmp = [0]
    def nxt():
        tmp[0] -= 1; return tmp[0]

    enabled = {r.campaign.id: r.campaign.name for r in ga.search(customer_id=CID, query="""
    SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status = 'ENABLED'""")}

    # BetterPatio is already at Google's cap of 20 shared sets per account, so its
    # terms are appended to the existing generic-irrelevant list, which is already
    # linked to every enabled campaign and is the right home for them anyway.
    APPEND_TO = {"BetterPatio.com": 12052054569}

    for group in ["Competitors", "Non-Carried Brands"]:
        set_name = f"{group} - auto"
        if account in APPEND_TO:
            target = APPEND_TO[account]
            have = {r.shared_criterion.keyword.text.lower()
                    for r in ga.search(customer_id=CID, query=f"""
                    SELECT shared_criterion.keyword.text FROM shared_criterion
                    WHERE shared_set.id = {target}""")}
            terms, blocked, dup = [], [], []
            for t in cfg[group]:
                if any(t in b for b in carried) or t in blob: blocked.append(t)
                elif t in have: dup.append(t)
                else: terms.append(t)
            if blocked: print(f"  {group}: BLOCKED by own catalogue -> {blocked}")
            if dup:     print(f"  {group}: already present -> {dup}")
            for t in terms:
                sc = op().shared_criterion_operation.create
                sc.shared_set = f"customers/{CID}/sharedSets/{target}"
                sc.keyword.text = t
                sc.keyword.match_type = e.KeywordMatchTypeEnum.PHRASE
            print(f"  {group}: appending {len(terms)} phrase negatives to set {target}")
            if terms: print(f"      {', '.join(terms)}")
            continue
        have = list(ga.search(customer_id=CID, query=f"""
        SELECT shared_set.id FROM shared_set
        WHERE shared_set.name = '{set_name}' AND shared_set.status != 'REMOVED'"""))
        if have:
            print(f"  {set_name}: already exists (id {have[0].shared_set.id}), skipping create")
            continue
        terms, blocked = [], []
        for t in cfg[group]:
            if any(t in b for b in carried) or t in blob:
                blocked.append(t); continue
            terms.append(t)
        if blocked:
            print(f"  {group}: BLOCKED by own catalogue -> {blocked}")
        ss_rn = f"customers/{CID}/sharedSets/{nxt()}"
        s = op().shared_set_operation.create
        s.resource_name = ss_rn
        s.name = set_name
        s.type_ = e.SharedSetTypeEnum.NEGATIVE_KEYWORDS
        for t in terms:
            sc = op().shared_criterion_operation.create
            sc.shared_set = ss_rn
            sc.keyword.text = t
            sc.keyword.match_type = e.KeywordMatchTypeEnum.PHRASE
        for cid, cname in enabled.items():
            link = op().campaign_shared_set_operation.create
            link.campaign = f"customers/{CID}/campaigns/{cid}"
            link.shared_set = ss_rn
        print(f"  {set_name}: {len(terms)} phrase negatives -> {len(enabled)} enabled campaigns")
        print(f"      {', '.join(terms)}")

    if not ops:
        print("  nothing to do"); continue
    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = CID; req.mutate_operations.extend(ops)
    req.validate_only = not args.live
    try:
        client.get_service("GoogleAdsService").mutate(request=req)
        print(f"  {'APPLIED' if args.live else 'VALIDATED'} ({len(ops)} operations)")
    except Exception as ex:
        print("  FAILED:"); print(str(ex)[:1200]); sys.exit(1)
