"""Bring the new BetterPatio custom-kitchen Search campaign up to house standard,
then enable it and pause the broken one.

Two gaps found auditing the new build against the rest of the account:

1. CONVERSION GOALS. The new campaign inherited the account default, PURCHASE /
   WEBSITE. But every one of the old campaign's 24 conversions in the last 90
   days came from 'Submit lead form' -- this is a quote funnel, not a purchase
   funnel. Left alone the campaign would report zero conversions forever while
   leads came in. The old campaign carried campaign-level goals overriding the
   account default; this mirrors them exactly:

       SIGNUP / WEBSITE
       PHONE_CALL_LEAD / WEBSITE
       PHONE_CALL_LEAD / CALL_FROM_ADS
       SUBMIT_LEAD_FORM / WEBSITE

2. NEGATIVE KEYWORD LIST. House standard is a universal negative list on every
   campaign. The old campaign had 'EP Generic' attached, which belongs to the
   eCommerce Paradise funnels. The right list here is 'BP Generic Irrelevants'
   (432 members), verified to have zero conflicts with the seven keywords.

Then: enable the new campaign, pause 'Build Your Own Outdoor Kitchen Campaign'.
Paused, never removed -- its history is the evidence this build was based on.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "BetterPatio.com"
NEW = 24221646363
OLD = 23303878302
BP_NEGATIVES = 12052054569           # BP Generic Irrelevants

# (category, origin) pairs copied from the old campaign.
WANT_BIDDABLE = {
    ("SIGNUP", "WEBSITE"),
    ("PHONE_CALL_LEAD", "WEBSITE"),
    ("PHONE_CALL_LEAD", "CALL_FROM_ADS"),
    ("SUBMIT_LEAD_FORM", "WEBSITE"),
}

SKAGS = ["custom outdoor kitchen", "custom outdoor kitchen design",
         "design my outdoor kitchen", "complete outdoor kitchen",
         "outdoor kitchen designers", "custom built outdoor kitchen",
         "outdoor kitchen builders near me"]


def blocks(neg_text, neg_mt, kw_text):
    kt, nt = kw_text.split(), neg_text.split()
    if neg_mt == "EXACT":
        return kt == nt
    if neg_mt == "PHRASE":
        return any(kt[i:i + len(nt)] == nt for i in range(len(kt) - len(nt) + 1))
    return all(w in kt for w in nt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")
    e = client.enums

    # --- guard: the negative list must not switch off a keyword we bought ---
    hits = []
    for r in ga.search(customer_id=cust, query=f"""
        SELECT shared_criterion.keyword.text, shared_criterion.keyword.match_type
        FROM shared_criterion WHERE shared_set.id = {BP_NEGATIVES} """):
        k = r.shared_criterion.keyword
        for kw in SKAGS:
            if blocks(k.text, k.match_type.name, kw):
                hits.append((k.match_type.name, k.text, kw))
    if hits:
        print("ABORT: the negative list would block keywords this campaign buys:")
        for m, n, kw in hits:
            print(f"  [{m}] '{n}' blocks '{kw}'")
        return 1
    print(f"negative list {BP_NEGATIVES}: no conflicts with the {len(SKAGS)} keywords")

    # --- guard: never enable a campaign whose ads are not approved ----------
    bad = []
    for r in ga.search(customer_id=cust, query=f"""
        SELECT ad_group.name, ad_group_ad.ad.id, ad_group_ad.status,
               ad_group_ad.policy_summary.approval_status,
               ad_group_ad.ad.final_urls
        FROM ad_group_ad WHERE campaign.id = {NEW} """):
        a = r.ad_group_ad
        st = a.policy_summary.approval_status.name
        if st in ("DISAPPROVED",):
            bad.append(f"{r.ad_group.name} / ad {a.ad.id}: {st}")
        for u in a.ad.final_urls:
            if "custom-outdoor-kitchens" not in u:
                bad.append(f"{r.ad_group.name} / ad {a.ad.id} -> {u}")
    if bad:
        print("ABORT: ads are not ready to enable:")
        for b in bad:
            print(f"  {b}")
        return 1
    print("all ads approved (or pending review) and pointing at the landing page")

    ops = []

    def op():
        o = client.get_type("MutateOperation")
        ops.append(o)
        return o

    # --- 1. conversion goals ------------------------------------------------
    goal_changes = []
    for r in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, campaign_conversion_goal.resource_name,
               campaign_conversion_goal.category,
               campaign_conversion_goal.origin,
               campaign_conversion_goal.biddable
        FROM campaign_conversion_goal WHERE campaign.id = {NEW} """):
        g = r.campaign_conversion_goal
        key = (g.category.name, g.origin.name)
        want = key in WANT_BIDDABLE
        if g.biddable == want:
            continue
        goal_changes.append((key, g.biddable, want))
        o = op().campaign_conversion_goal_operation
        o.update.resource_name = g.resource_name
        o.update.biddable = want
        o.update_mask.paths.append("biddable")

    # --- 2. attach the negative list ----------------------------------------
    already = any(True for _ in ga.search(customer_id=cust, query=f"""
        SELECT campaign.id, shared_set.id FROM campaign_shared_set
        WHERE campaign.id = {NEW} AND shared_set.id = {BP_NEGATIVES} """))
    if not already:
        o = op().campaign_shared_set_operation.create
        o.campaign = client.get_service("CampaignService").campaign_path(cust, NEW)
        o.shared_set = client.get_service("SharedSetService").shared_set_path(
            cust, BP_NEGATIVES)

    # --- 3. enable new, pause old -------------------------------------------
    svc = client.get_service("CampaignService")
    n = op().campaign_operation
    n.update.resource_name = svc.campaign_path(cust, NEW)
    n.update.status = e.CampaignStatusEnum.ENABLED
    n.update_mask.paths.append("status")

    o2 = op().campaign_operation
    o2.update.resource_name = svc.campaign_path(cust, OLD)
    o2.update.status = e.CampaignStatusEnum.PAUSED
    o2.update_mask.paths.append("status")

    print(f"\n{'EXECUTING' if args.execute else 'DRY RUN'}: {len(ops)} operations")
    print("  conversion goals:")
    for (cat, origin), was, now in goal_changes:
        print(f"      {cat} / {origin}: biddable {was} -> {now}")
    if not goal_changes:
        print("      (already correct)")
    print(f"  negative list: "
          f"{'already attached' if already else 'attach BP Generic Irrelevants (432)'}")
    print(f"  campaign {NEW} (new)  -> ENABLED")
    print(f"  campaign {OLD} (old)  -> PAUSED")

    req = client.get_type("MutateGoogleAdsRequest")
    req.customer_id = cust
    req.mutate_operations.extend(ops)
    req.validate_only = not args.execute
    try:
        ga.mutate(request=req)
    except Exception as ex:
        print("\nFAILED:")
        print(str(ex)[:2000])
        return 1

    print("\n" + ("DONE" if args.execute else "VALIDATED - nothing written"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
