"""One-time: generate a Google Ads API refresh token.

Run this on a machine with a browser (your own laptop) — it opens a Google
sign-in window. A cloud/remote session has no browser, so this step can't
happen there.

    python scripts/get_refresh_token.py

Needs credentials.json (the OAuth "Desktop app" client you download from
Google Cloud Console) in the project root. Prints the refresh token to paste
into .env as GOOGLE_ADS_REFRESH_TOKEN.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/adwords"]


def main():
    if not CREDENTIALS_FILE.exists():
        sys.exit(
            f"credentials.json not found at {CREDENTIALS_FILE}\n\n"
            "Get it from Google Cloud Console -> APIs & Services -> Credentials\n"
            "  -> Create Credentials -> OAuth client ID\n"
            "  -> Application type: Desktop app -> Create -> Download JSON\n"
            "Save it as credentials.json in the project root. It is gitignored."
        )

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit("Missing dependency. Run: pip install -r requirements.txt")

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)

    print("Opening your browser to sign in to Google...")
    print("Sign in with the SAME email you added as a test user on the OAuth")
    print("consent screen, or Google will refuse the request.\n")

    # port=0 lets the OS pick a free port for the loopback redirect.
    flow.run_local_server(port=0, prompt="consent")

    refresh_token = flow.credentials.refresh_token
    if not refresh_token:
        sys.exit(
            "Google did not return a refresh token. This usually means this app was "
            "already authorized for your account. Revoke it at "
            "https://myaccount.google.com/permissions and run this again."
        )

    client_config = json.loads(CREDENTIALS_FILE.read_text())
    installed = client_config.get("installed") or client_config.get("web") or {}

    print("\n" + "=" * 62)
    print("SUCCESS — add these three lines to your .env file:")
    print("=" * 62)
    print(f"GOOGLE_ADS_CLIENT_ID={installed.get('client_id', '')}")
    print(f"GOOGLE_ADS_CLIENT_SECRET={installed.get('client_secret', '')}")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
    print("=" * 62)
    print("\nThe refresh token does not expire. Store it somewhere safe -")
    print("a password manager - so you never have to redo this step.")


if __name__ == "__main__":
    main()
