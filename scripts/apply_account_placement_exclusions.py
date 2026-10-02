"""Apply account-level placement exclusions across every managed account.

Trevor, 1-2 October 2026: the client PMax campaigns serve heavily on Display and
YouTube and it is not targeted -- "account-level exclusions now apply across
Performance Max, Demand Gen, YouTube and Display simultaneously. One list, every
campaign, all five accounts... get this done for all accounts."

That is the right lever. PMax has no generally available channel off-switch, but
since January 2026 `customer_negative_criterion` applies across Performance Max,
Demand Gen, YouTube and Display at once, so one list per account covers every
campaign in it.

Two families are applied here, and they are different in kind:

1. CONTENT LABELS -- a fixed enum, so the list is explicit and auditable. These
   are the waste and brand-safety categories. The two that matter most for
   "serving a lot but untargeted" are PARKED_DOMAIN (domain arbitrage, pure
   waste) and BELOW_THE_FOLD (impressions nobody saw).

2. MOBILE APP CATEGORIES -- in-app inventory. On a store selling $2k-$25k
   outdoor kitchens or HVAC systems, app traffic is close to pure waste, and it
   is usually the bulk of untargeted Display volume. The category IDs are a
   Google taxonomy, so they are resolved by query at run time rather than
   hardcoded. Pass --keep-apps to skip this family.

Deliberately NOT included: specific sites, apps and YouTube channels. Those
should come from evidence, not guesswork -- run
`scripts/audit_pmax_placements.py` first and feed its output in with
--placements FILE (one placement per line; a bare domain, an app id, or a
YouTube channel id).

Every mutate uses partial_failure, because content-label support varies by
campaign type and one unsupported value must not roll back the batch. Rejections
are reported rather than swallowed.

Idempotent: existing exclusions are read first and skipped, so a re-run adds
nothing.

Dry run by default. Pass --execute to apply.
"""
import argparse
import pathlib
import sys
from collections import defaultdict

from google_ads.auth import get_client
from google_ads.accounts import load_managed_accounts, resolve_account

# Verified against the v25 ContentLabelTypeEnum. Grouped by why they are here.
CONTENT_LABELS = [
    # Pure waste: nobody is shopping on these.
    "PARKED_DOMAIN",
    "BELOW_THE_FOLD",
    # Low-intent video surfaces that inflate Display/YouTube volume.
    "EMBEDDED_VIDEO",
    "LIVE_STREAMING_VIDEO",
    # Brand safety for a home-improvement / HVAC retailer.
    "SEXUALLY_SUGGESTIVE",
    "JUVENILE",
    "PROFANITY",
    "TRAGEDY",
    "SOCIAL_ISSUES",
    "BRAND_SUITABILITY_GAMES_FIGHTING",
    "BRAND_SUITABILITY_GAMES_MATURE",
    "BRAND_SUITABILITY_POLITICS",
    "BRAND_SUITABILITY_RELIGION",
    "BRAND_SUITABILITY_NEWS_SENSITIVE",
    "VIDEO_RATING_DV_MA",
    "VIDEO_NOT_YET_RATED",
]
# Left ON deliberately: VIDEO (would remove all video, too blunt),
# VIDEO_RATING_DV_G / DV_PG / DV_T and BRAND_SUITABILITY_CONTENT_FOR_FAMILIES
# (these are the placements worth keeping), and the HEALTH and remaining NEWS
# suitability labels (too broad for this niche to be worth the reach loss).


def existing_exclusions(ga, cust):
    """What this account already excludes, keyed for duplicate detection."""
    have = defaultdict(set)
    rows = 0
    for r in ga.search(customer_id=cust, query="""
        SELECT customer_negative_criterion.id,
               customer_negative_criterion.type,
               customer_negative_criterion.content_label.type,
               customer_negative_criterion.mobile_app_category
                   .mobile_app_category_constant,
               customer_negative_criterion.mobile_application.app_id,
               customer_negative_criterion.placement.url,
               customer_negative_criterion.youtube_channel.channel_id,
               customer_negative_criterion.youtube_video.video_id
        FROM customer_negative_criterion"""):
        c = r.customer_negative_criterion
        rows += 1
        t = c.type_.name
        if t == "CONTENT_LABEL":
            have["content_label"].add(c.content_label.type_.name)
        elif t == "MOBILE_APP_CATEGORY":
            have["app_category"].add(
                c.mobile_app_category.mobile_app_category_constant)
        elif t == "MOBILE_APPLICATION":
            have["app"].add(c.mobile_application.app_id)
        elif t == "PLACEMENT":
            have["placement"].add(c.placement.url)
        elif t == "YOUTUBE_CHANNEL":
            have["yt_channel"].add(c.youtube_channel.channel_id)
        elif t == "YOUTUBE_VIDEO":
            have["yt_video"].add(c.youtube_video.video_id)
    return have, rows


def app_categories(ga, cust):
    """The live mobile app category taxonomy: resource name -> label."""
    out = {}
    for r in ga.search(customer_id=cust, query="""
        SELECT mobile_app_category_constant.id,
               mobile_app_category_constant.name,
               mobile_app_category_constant.resource_name
        FROM mobile_app_category_constant"""):
        c = r.mobile_app_category_constant
        out[c.resource_name] = c.name
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--account", action="append",
                    help="limit to these accounts (default: all managed)")
    ap.add_argument("--keep-apps", action="store_true",
                    help="do NOT exclude mobile app categories")
    ap.add_argument("--placements", type=pathlib.Path,
                    help="file of specific placements to exclude, one per line "
                         "(domain, app id, or YouTube channel id). Lines "
                         "starting with # are ignored.")
    args = ap.parse_args()

    extra = []
    if args.placements:
        if not args.placements.exists():
            print(f"ABORT: {args.placements} not found")
            return 1
        for line in args.placements.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                extra.append(line)

    client = get_client()
    ga = client.get_service("GoogleAdsService")
    svc = client.get_service("CustomerNegativeCriterionService")
    e = client.enums

    print("=" * 78)
    print("DRY RUN" if not args.execute else "EXECUTING")
    print("Account-level exclusions -- these apply to Performance Max, Demand")
    print("Gen, YouTube and Display at once, every campaign in the account.")
    print("=" * 78)

    accounts = args.account or [a["id"] for a in load_managed_accounts()]
    grand = 0

    for key in accounts:
        acct = resolve_account(key)
        cust, name = acct["id"], acct["name"]
        have, nrows = existing_exclusions(ga, cust)
        print(f"\n\n### {name} [{cust}]")
        print(f"  already excluded: {nrows} criteria "
              f"{ {k: len(v) for k, v in have.items()} or '(none)'}")

        ops = []
        plan = defaultdict(list)
        labels = []          # parallel to ops, so a rejection can be named

        for label in CONTENT_LABELS:
            if label in have["content_label"]:
                continue
            o = client.get_type("CustomerNegativeCriterionOperation")
            o.create.content_label.type_ = e.ContentLabelTypeEnum[label]
            ops.append(o)
            labels.append(("content label", label))
            plan["content label"].append(label)

        if not args.keep_apps:
            cats = app_categories(ga, cust)
            for rn, label in sorted(cats.items(), key=lambda kv: kv[1]):
                if rn in have["app_category"]:
                    continue
                o = client.get_type("CustomerNegativeCriterionOperation")
                o.create.mobile_app_category.mobile_app_category_constant = rn
                ops.append(o)
                nice = label or rn.split("/")[-1]
                labels.append(("app category", nice))
                plan["app category"].append(nice)

        for p in extra:
            # A YouTube channel id is 24 chars starting UC; anything with a dot
            # is treated as a site; otherwise an app id.
            if p.startswith("UC") and len(p) == 24:
                if p in have["yt_channel"]:
                    continue
                o = client.get_type("CustomerNegativeCriterionOperation")
                o.create.youtube_channel.channel_id = p
                labels.append(("youtube channel", p))
                plan["youtube channel"].append(p)
            elif "." in p:
                if p in have["placement"]:
                    continue
                o = client.get_type("CustomerNegativeCriterionOperation")
                o.create.placement.url = p
                labels.append(("placement", p))
                plan["placement"].append(p)
            else:
                if p in have["app"]:
                    continue
                o = client.get_type("CustomerNegativeCriterionOperation")
                o.create.mobile_application.app_id = p
                labels.append(("mobile app", p))
                plan["mobile app"].append(p)
            ops.append(o)

        for kind, items in sorted(plan.items()):
            print(f"\n  + {len(items)} {kind}(s):")
            for i in items[:20]:
                print(f"      {i}")
            if len(items) > 20:
                print(f"      ... and {len(items) - 20} more")
        if not ops:
            print("\n  nothing to add -- already in place")
            continue
        print(f"\n  TOTAL to add for this account: {len(ops)}")
        grand += len(ops)

        if not args.execute:
            continue

        # partial_failure: content-label support varies by campaign type, and one
        # unsupported value must not roll back the whole batch.
        resp = svc.mutate_customer_negative_criteria(
            customer_id=cust, operations=ops, partial_failure=True)
        # A rejected operation comes back with an empty resource_name, in the
        # same order as it was sent. Mapping that against `labels` names the
        # rejection without having to unpack GoogleAdsFailure, whose shape
        # differs between library versions.
        ok, rejected = 0, []
        for i, r in enumerate(resp.results):
            if r.resource_name:
                ok += 1
            elif i < len(labels):
                rejected.append(labels[i])
        print(f"  added {ok} of {len(ops)}")
        if rejected:
            print(f"  {len(rejected)} rejected by Google (left alone):")
            for kind, val in rejected:
                print(f"      {kind:16} {val}")
            if resp.partial_failure_error:
                print(f"      reason: {resp.partial_failure_error.message[:160]}")

    print(f"\n\n{'=' * 78}")
    print(f"TOTAL across all accounts: {grand}")
    if not args.execute:
        print("\nDry run. Re-run with --execute to apply.")
        return 0

    print("\n--- read-back ---")
    for key in accounts:
        acct = resolve_account(key)
        have, nrows = existing_exclusions(ga, acct["id"])
        print(f"  {acct['name']:34} {nrows:>4} criteria "
              f"{ {k: len(v) for k, v in have.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
