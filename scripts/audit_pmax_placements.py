"""Where are the PMax campaigns actually serving, and what is already excluded?

Trevor, 1 October 2026: the client PMax campaigns seem to serve heavily on
Display and YouTube, untargeted -- can those placements be excluded?

Short answer, which shapes this script: Performance Max has NO generally
available channel off-switch. You cannot tick "no Display" or "no YouTube" the
way a Search campaign can. Google began alpha-testing a Partners setting with
independent Search Partner and Display checkboxes in mid-2026, but it is a
limited alpha and does not cover YouTube.

What IS generally available, and applies to PMax, is placement exclusion:

* ACCOUNT level, via `customer_negative_criterion`. Since January 2026 these
  apply across Performance Max, Demand Gen, YouTube and Display at once, so one
  list covers every campaign. v25 accepts: placement, placement_list,
  youtube_video, youtube_channel, mobile_application, mobile_app_category,
  content_label, negative_keyword_list, ip_block.
* CAMPAIGN level, via `campaign_criterion` with `negative = true`.

So the lever exists, but it is a list of things to exclude -- which means the
honest first move is to find out what it is actually serving on rather than
guessing. This script is READ ONLY and does three things per account:

  1. the network split per enabled PMax campaign (segments.ad_network_type),
     so we can see how much really goes to Display and YouTube versus Search
  2. the actual placements, from `performance_max_placement_view`, so the
     exclusion list is built from evidence
  3. what is already excluded at account and campaign level, so we do not
     duplicate work

Run it, read it, then we write the exclusions from the output.

    PYTHONPATH=/home/user/ecommerceparadise .venv/bin/python \
        scripts/audit_pmax_placements.py [--days 30] [--account NAME_OR_ID]
"""
import argparse
import datetime as dt
import sys
from collections import Counter, defaultdict

from google_ads.auth import get_client
from google_ads.accounts import load_managed_accounts, resolve_account


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--account", action="append",
                    help="limit to these accounts (default: all managed)")
    ap.add_argument("--top", type=int, default=25,
                    help="how many placements to list per campaign")
    args = ap.parse_args()

    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=args.days - 1)
    # v25 wants an explicit BETWEEN range; DURING LAST_30_DAYS is invalid.
    window = f"BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"

    client = get_client()
    ga = client.get_service("GoogleAdsService")
    accounts = args.account or [a["id"] for a in load_managed_accounts()]

    print("=" * 78)
    print(f"PMax placement audit   {start} to {end}   (read only)")
    print("=" * 78)

    for key in accounts:
        acct = resolve_account(key)
        cust, name = acct["id"], acct["name"]

        camps = {}
        for r in ga.search(customer_id=cust, query="""
            SELECT campaign.id, campaign.name, campaign_budget.amount_micros
            FROM campaign
            WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
              AND campaign.status = 'ENABLED'"""):
            camps[r.campaign.id] = (r.campaign.name,
                                    r.campaign_budget.amount_micros / 1e6)

        print(f"\n\n{'#' * 70}\n### {name} [{cust}]")

        # ---- what is already excluded account-wide ------------------------
        acct_excl = defaultdict(list)
        for r in ga.search(customer_id=cust, query="""
            SELECT customer_negative_criterion.id,
                   customer_negative_criterion.type,
                   customer_negative_criterion.placement.url,
                   customer_negative_criterion.youtube_channel.channel_id,
                   customer_negative_criterion.youtube_video.video_id,
                   customer_negative_criterion.mobile_application.name,
                   customer_negative_criterion.mobile_app_category
                       .mobile_app_category_constant,
                   customer_negative_criterion.content_label.type
            FROM customer_negative_criterion"""):
            c = r.customer_negative_criterion
            v = (c.placement.url or c.youtube_channel.channel_id
                 or c.youtube_video.video_id or c.mobile_application.name
                 or c.mobile_app_category.mobile_app_category_constant
                 or c.content_label.type_.name)
            acct_excl[c.type_.name].append(v)
        print(f"\n  ACCOUNT-LEVEL exclusions already in place "
              f"({sum(len(v) for v in acct_excl.values())}):")
        if not acct_excl:
            print("    NONE -- nothing is excluded account-wide")
        for k, v in sorted(acct_excl.items()):
            print(f"    {k:22} {len(v):>4}  e.g. {v[:3]}")

        if not camps:
            print("\n  no ENABLED PMax campaign")
            continue

        for cid, (cname, budget) in camps.items():
            print(f"\n  {'-' * 66}")
            print(f"  [{cid}] ${budget:.2f}/day  {cname!r}")

            # ---- network split -------------------------------------------
            net = defaultdict(lambda: [0, 0, 0.0, 0.0])
            for r in ga.search(customer_id=cust, query=f"""
                SELECT campaign.id, segments.ad_network_type,
                       metrics.impressions, metrics.clicks,
                       metrics.cost_micros, metrics.conversions
                FROM campaign WHERE campaign.id = {cid}
                  AND segments.date {window}"""):
                k = r.segments.ad_network_type.name
                net[k][0] += r.metrics.impressions
                net[k][1] += r.metrics.clicks
                net[k][2] += r.metrics.cost_micros / 1e6
                net[k][3] += r.metrics.conversions
            ti = sum(v[0] for v in net.values())
            tc = sum(v[2] for v in net.values())
            if not ti:
                print("      no delivery in the window")
                continue
            print(f"\n      {'network':24} {'impr':>10} {'%':>6} {'clicks':>7} "
                  f"{'cost':>10} {'%':>6} {'conv':>6}")
            for k, v in sorted(net.items(), key=lambda kv: -kv[1][2]):
                print(f"      {k:24} {v[0]:>10,} {100*v[0]/ti:>5.1f}% "
                      f"{v[1]:>7,} ${v[2]:>9,.2f} "
                      f"{100*v[2]/tc if tc else 0:>5.1f}% {v[3]:>6.1f}")
            print(f"      {'TOTAL':24} {ti:>10,} {'':>6} "
                  f"{sum(v[1] for v in net.values()):>7,} ${tc:>9,.2f}")

            # ---- the actual placements -----------------------------------
            # performance_max_placement_view is the only way to see where a
            # PMax campaign ran. It supports impressions, not cost.
            places = Counter()
            kinds = Counter()
            urls = {}
            try:
                for r in ga.search(customer_id=cust, query=f"""
                    SELECT performance_max_placement_view.display_name,
                           performance_max_placement_view.placement,
                           performance_max_placement_view.placement_type,
                           performance_max_placement_view.target_url,
                           metrics.impressions, campaign.id
                    FROM performance_max_placement_view
                    WHERE campaign.id = {cid}
                      AND segments.date {window}"""):
                    v = r.performance_max_placement_view
                    label = v.display_name or v.placement or "(unnamed)"
                    places[(v.placement_type.name, label)] += r.metrics.impressions
                    kinds[v.placement_type.name] += r.metrics.impressions
                    urls[label] = v.target_url
            except Exception as ex:
                print(f"\n      placement view unavailable: "
                      f"{type(ex).__name__}: {str(ex)[:160]}")
                continue

            if not places:
                print("\n      no placements reported")
                continue
            tot = sum(places.values())
            print(f"\n      PLACEMENTS by type ({tot:,} impressions total):")
            for k, v in kinds.most_common():
                print(f"        {k:24} {v:>10,} {100*v/tot:>5.1f}%")
            print(f"\n      TOP {args.top} placements by impressions:")
            for (ptype, label), imps in places.most_common(args.top):
                print(f"        {imps:>9,} {100*imps/tot:>5.1f}%  "
                      f"{ptype:18} {label[:44]:44} {urls.get(label,'')[:40]}")

            # ---- campaign-level exclusions already set -------------------
            cex = Counter()
            for r in ga.search(customer_id=cust, query=f"""
                SELECT campaign_criterion.type, campaign_criterion.negative,
                       campaign.id
                FROM campaign_criterion WHERE campaign.id = {cid}
                  AND campaign_criterion.negative = true"""):
                cex[r.campaign_criterion.type_.name] += 1
            print(f"\n      campaign-level negatives: {dict(cex) or 'none'}")

    print("\n\nNEXT: the exclusion list gets written from the placements above, "
          "at ACCOUNT level so it covers PMax, Demand Gen, Display and YouTube "
          "in one place. Nothing was changed by this script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
