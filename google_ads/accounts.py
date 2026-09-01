"""Discover and resolve the client accounts this project is allowed to touch.

One set of credentials reaches every account linked under the manager, but
that is not the same as "every account this project may work on." The
accounts actually in scope are listed in managed_accounts.json at the repo
root — an explicit allowlist, edited deliberately, not derived from whatever
the manager account happens to contain.

resolve_account() and list_accounts() both enforce that allowlist: a name or
ID outside it is refused, even though the credentials could technically reach
it. Google Ads write operations are hard to reverse, and this account is
linked to accounts that belong to other people's businesses, so refusing to
guess is the safer default.
"""

import json
from pathlib import Path

from google_ads.auth import get_client, get_login_customer_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANAGED_ACCOUNTS_FILE = PROJECT_ROOT / "managed_accounts.json"

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


def _clean_id(value):
    return "".join(c for c in str(value) if c.isdigit())


def load_managed_accounts():
    """Return the {id, name} allowlist from managed_accounts.json.

    Missing or empty file means the allowlist hasn't been set up yet — that
    fails loudly (see resolve_account) rather than silently allowing every
    account the credentials can reach.
    """
    if not MANAGED_ACCOUNTS_FILE.exists():
        return []
    data = json.loads(MANAGED_ACCOUNTS_FILE.read_text())
    return [
        {"id": _clean_id(a["id"]), "name": a["name"]}
        for a in data.get("accounts", [])
    ]


def is_managed(customer_id):
    """True if customer_id is on the allowlist."""
    target = _clean_id(customer_id)
    return any(a["id"] == target for a in load_managed_accounts())


def list_all_accounts(client=None, include_managers=False, include_closed=False):
    """Return every account under the manager, ignoring the allowlist.

    Use this only to audit what the credentials can reach (e.g. when
    deciding what to add to managed_accounts.json). Everyday work should use
    list_accounts(), which is scoped to the allowlist.
    """
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


def list_accounts(client=None, **kwargs):
    """Return only the accounts on the managed_accounts.json allowlist.

    Fetches live details (status, currency, time zone) from the API for
    each, but the account IDs themselves come only from the allowlist —
    never from what the manager account happens to contain.
    """
    managed = load_managed_accounts()
    if not managed:
        return []

    all_accounts = {a["id"]: a for a in list_all_accounts(client=client, **kwargs)}

    result = []
    for entry in managed:
        live = all_accounts.get(entry["id"])
        if live:
            result.append(live)
        else:
            # On the allowlist but not visible right now (closed, or the
            # live name changed) — keep it visible with what we know rather
            # than silently dropping it.
            result.append({**entry, "status": "UNKNOWN", "currency": "?", "time_zone": "?", "level": None})

    result.sort(key=lambda a: a["name"].lower())
    return result


def resolve_account(name_or_id, client=None):
    """Resolve a name fragment or ID to exactly one MANAGED account.

    Refuses anything not in managed_accounts.json, even if the credentials
    can technically reach it — this project is scoped to a specific set of
    client accounts, not every account under the manager.
    """
    managed = load_managed_accounts()
    if not managed:
        raise LookupError(
            "managed_accounts.json has no accounts listed. Add the accounts "
            "you're allowed to work on before resolving any by name."
        )

    query = str(name_or_id).strip()
    digits = _clean_id(query)
    accounts = list_accounts(client=client)

    if len(digits) == 10:
        for account in accounts:
            if account["id"] == digits:
                return account
        raise LookupError(
            f"{digits} is not in managed_accounts.json. This project is scoped "
            "to a specific set of client accounts — edit managed_accounts.json "
            "if this account should be added."
        )

    matches = [a for a in accounts if query.lower() in a["name"].lower()]

    if not matches:
        raise LookupError(
            f"No managed account matching {query!r}. Run scripts/list_accounts.py "
            "to see the accounts in scope, or edit managed_accounts.json to add one."
        )
    if len(matches) > 1:
        names = ", ".join(f"{a['name']} ({a['id']})" for a in matches)
        raise LookupError(f"{query!r} matches more than one managed account: {names}")

    return matches[0]
