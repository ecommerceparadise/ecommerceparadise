"""Discover and resolve the client accounts under the manager (MCC) account.

One set of credentials reaches every account linked under the manager, so the
operating account is a per-request parameter, not a stored setting. These
helpers turn a human name ("Acme Plumbing") into the customer ID the API wants.
"""

from google_ads.auth import get_client, get_login_customer_id

# level 1 = direct children of the manager, level 2 = their children.
ACCOUNTS_QUERY = """
    SELECT
      customer_client.id,
      customer_client.descriptive_name,
      customer_client.manager,
      customer_client.status,
      customer_client.level,
      customer_client.currency_code,
      customer_client.time_zone
    FROM customer_client
    WHERE customer_client.level <= 2
"""


def list_accounts(client=None, include_managers=False, include_closed=False):
    """Return every account under the manager as a list of dicts."""
    client = client or get_client()
    manager_id = get_login_customer_id()
    ga_service = client.get_service("GoogleAdsService")

    accounts = []
    for row in ga_service.search(customer_id=manager_id, query=ACCOUNTS_QUERY):
        c = row.customer_client
        if c.manager and not include_managers:
            continue
        status = c.status.name
        if status != "ENABLED" and not include_closed:
            continue
        accounts.append(
            {
                "id": str(c.id),
                "name": c.descriptive_name or "(unnamed)",
                "status": status,
                "level": c.level,
                "currency": c.currency_code,
                "time_zone": c.time_zone,
            }
        )

    accounts.sort(key=lambda a: a["name"].lower())
    return accounts


def resolve_account(name_or_id, client=None):
    """Resolve a name fragment or ID to exactly one account.

    Raises if nothing matches, or if a name fragment is ambiguous — better to
    stop than to quietly operate on the wrong client's account.
    """
    query = str(name_or_id).strip()
    digits = "".join(c for c in query if c.isdigit())
    accounts = list_accounts(client=client)

    if len(digits) == 10:
        for account in accounts:
            if account["id"] == digits:
                return account
        raise LookupError(
            f"No account with ID {digits} under this manager account. "
            "Run scripts/list_accounts.py to see what's reachable."
        )

    matches = [a for a in accounts if query.lower() in a["name"].lower()]

    if not matches:
        raise LookupError(
            f"No account matching {query!r}. "
            "Run scripts/list_accounts.py to see the exact names."
        )
    if len(matches) > 1:
        names = ", ".join(f"{a['name']} ({a['id']})" for a in matches)
        raise LookupError(f"{query!r} matches more than one account: {names}")

    return matches[0]
