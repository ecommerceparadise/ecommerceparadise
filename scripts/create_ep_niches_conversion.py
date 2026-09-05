"""Create the Google Ads conversion action for the Klaviyo niches-list opt-in.

Context. eCommerce Paradise's /niches/ landing page converts -- Klaviyo recorded
118 embed-form submits in the last 30 days at a 12.07% submit rate, and the
'Niches List Leads' list took 137 opt-ins in August. Google Ads recorded zero,
because Klaviyo has no conversion feed to Google Ads and nothing on the page
fires a conversion tag. This creates the action that the onsite snippet fires.

The account already has everything else needed:
  - conversion tracking id AW-11096777331, managed by self
  - Site Kit's Google tag GT-MKPF9XJ already routes to AW-11096777331,
    so no new gtag config has to be added to the site
  - SUBMIT_LEAD_FORM/WEBSITE is already a biddable goal at account level and
    on every enabled campaign, so this action joins an existing goal rather
    than creating a new one

Marked primary so it counts in 'Conversions' and is available to Smart Bidding.
EP 5 (the niches funnel) is MANUAL_CPC, so there is no bidding effect there
today; EP RT 2 is MAXIMIZE_CONVERSIONS on SUBMIT_LEAD_FORM and will begin
optimising toward these opt-ins once they start arriving.

Run with no flags for a dry run. Pass --execute to push.
"""
import argparse
import sys

from google_ads.auth import get_client
from google_ads.accounts import resolve_account

ACCOUNT = "eCommerce Paradise"
NAME = "Niches List Opt-In (Klaviyo)"
EXPECTED_TRACKING_ID = 11096777331


def existing(ga, cust):
    rows = list(ga.search(customer_id=cust, query=f"""
        SELECT conversion_action.id, conversion_action.name, conversion_action.status
        FROM conversion_action
        WHERE conversion_action.name = '{NAME}' """))
    return rows[0].conversion_action if rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    client = get_client()
    cust = resolve_account(ACCOUNT)["id"]
    ga = client.get_service("GoogleAdsService")

    # Guard: the snippet hard-codes AW-11096777331. Refuse if the account's
    # tracking id is anything else, otherwise the tag would fire into nothing.
    tid = None
    for r in ga.search(customer_id=cust, query="""
        SELECT customer.conversion_tracking_setting.conversion_tracking_id
        FROM customer """):
        tid = r.customer.conversion_tracking_setting.conversion_tracking_id
    if tid != EXPECTED_TRACKING_ID:
        print(f"ABORT: account tracking id is AW-{tid}, expected AW-{EXPECTED_TRACKING_ID}")
        return 1
    print(f"account {cust}, conversion tracking id AW-{tid}  OK")

    dupe = existing(ga, cust)
    if dupe:
        print(f"\nAlready exists: [{dupe.id}] {dupe.name} ({dupe.status.name})")
        print("Nothing to create. Re-run scripts/show_ep_conversion_tag.py for the label.")
        return 0

    print(f"\nWOULD CREATE" if not args.execute else "\nCREATING")
    print(f"  name         : {NAME}")
    print(f"  type         : WEBPAGE")
    print(f"  category     : SUBMIT_LEAD_FORM")
    print(f"  counting     : ONE_PER_CLICK  (one lead per click)")
    print(f"  click window : 30 days")
    print(f"  primary      : True  (counts in 'Conversions', biddable)")
    print(f"  value        : none set")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to push.")
        return 0

    svc = client.get_service("ConversionActionService")
    op = client.get_type("ConversionActionOperation")
    c = op.create
    c.name = NAME
    c.type_ = client.enums.ConversionActionTypeEnum.WEBPAGE
    c.category = client.enums.ConversionActionCategoryEnum.SUBMIT_LEAD_FORM
    c.status = client.enums.ConversionActionStatusEnum.ENABLED
    c.counting_type = (
        client.enums.ConversionActionCountingTypeEnum.ONE_PER_CLICK)
    c.click_through_lookback_window_days = 30
    c.primary_for_goal = True

    res = svc.mutate_conversion_actions(customer_id=cust, operations=[op])
    rn = res.results[0].resource_name
    print(f"\n  created {rn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
