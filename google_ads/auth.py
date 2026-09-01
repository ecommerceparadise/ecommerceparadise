"""Build an authenticated Google Ads API client from credentials in the environment.

Credentials are read from real environment variables first, then from a .env file
in the project root. That means the same code works whether you're running Claude
Code locally (.env on disk) or in a cloud session (env vars set on the
environment), and a fresh container never loses the connection.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Vars needed to authenticate at all.
REQUIRED_VARS = [
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
]

# Optional. A convenience default only; the operating account is normally
# passed per request, because one set of credentials reaches every client
# account linked under the manager.
TARGET_VAR = "GOOGLE_ADS_CUSTOMER_ID"


def load_env():
    """Load .env into the environment without overriding real env vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _clean_id(value):
    """Google Ads customer IDs must be 10 digits with no dashes or spaces."""
    return "".join(c for c in value if c.isdigit())


def missing_vars():
    """Return the credential vars that are absent or empty."""
    load_env()
    return [v for v in REQUIRED_VARS if not os.environ.get(v, "").strip()]


def get_config():
    """Return the credential dict, or raise with the exact vars that are missing."""
    load_env()
    absent = missing_vars()
    if absent:
        raise RuntimeError(
            "Google Ads credentials incomplete. Missing:\n  "
            + "\n  ".join(absent)
            + "\n\nFill these in .env (copy .env.example) or set them as environment "
            "variables, then re-run. See README.md for where each value comes from."
        )
    return {
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"].strip(),
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"].strip(),
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"].strip(),
        "login_customer_id": _clean_id(os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"]),
        "use_proto_plus": True,
    }


def get_client():
    """Return an authenticated GoogleAdsClient."""
    from google.ads.googleads.client import GoogleAdsClient

    return GoogleAdsClient.load_from_dict(get_config())


def get_login_customer_id():
    """Return the manager (MCC) account ID, digits only."""
    load_env()
    return _clean_id(os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"])


def get_customer_id(default=None):
    """Return the default operating account ID, or None if none is set.

    Optional by design: most work names the client account explicitly, and
    google_ads.accounts.resolve_account turns a client name into an ID.
    """
    load_env()
    value = os.environ.get(TARGET_VAR, "").strip()
    if not value:
        return _clean_id(default) if default else None
    return _clean_id(value)
