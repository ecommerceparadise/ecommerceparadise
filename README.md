# Google Ads API connection

Direct Google Ads API access for Claude Code, so campaign builds, audits,
negative-keyword passes and reporting can run against the account instead of
through the Google Ads UI.

## Why the connection dropped

The credentials were never stored in the GitHub repo — `.env` and
`credentials.json` are gitignored on purpose, so they only ever lived on disk in
the working environment. A new repo means a new working environment with an
empty disk, so the credentials went with it. Nothing was revoked on Google's
side.

**Your Google Cloud project, OAuth client, developer token and refresh token
are almost certainly still valid.** If you saved them, reconnecting is step 3
only. If you didn't, do all the steps once and save them this time.

## What you need

Six values:

| Value | Where it comes from |
|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Manager account (MCC) → Admin → API Center |
| `GOOGLE_ADS_CLIENT_ID` | `credentials.json` from Google Cloud Console |
| `GOOGLE_ADS_CLIENT_SECRET` | same `credentials.json` |
| `GOOGLE_ADS_REFRESH_TOKEN` | `scripts/get_refresh_token.py` (one time, needs a browser) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | manager (MCC) account ID, 10 digits |
| `GOOGLE_ADS_CUSTOMER_ID` | the account you're operating on, 10 digits |

Dashes and spaces in the IDs are stripped automatically.

## Setup

### 1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Use a virtualenv rather than a system-wide install — a system `pip install`
collides with the preinstalled `cryptography` package and breaks the import.

### 2. Google Cloud + Google Ads (skip if you already have the values)

1. Google Ads manager account (MCC), with the operating account linked under it
   and the link invitation accepted.
2. Manager account → Admin → API Center → copy the developer token.
   Test access allows 2,880 requests/day; apply for Basic Access for more.
3. Google Cloud Console → new project → enable the **Google Ads API**.
4. OAuth consent screen → External → **add your own email as a test user**.
   This is the step that most often breaks auth later.
5. Credentials → Create Credentials → OAuth client ID → **Desktop app** →
   download the JSON → save as `credentials.json` in this folder.

### 3. Get a refresh token

Run this **on a machine with a browser** — a cloud session has no browser:

```bash
.venv/bin/python scripts/get_refresh_token.py
```

Sign in with the email you added as a test user. It prints your client ID,
client secret and refresh token. The refresh token does not expire.

### 4. Store the credentials

Two options, and they can both be true at once — the code reads real
environment variables first, then falls back to `.env`.

**Local:** copy `.env.example` to `.env` and fill it in.

```bash
cp .env.example .env
```

**Cloud sessions (recommended, and what prevents this from happening again):**
set the six values as environment variables on the Claude Code environment
(claude.ai/code → environment settings). Environment variables are attached to
the environment, not the repo, so they survive a fresh container and a deleted
repo. Configuration reference:
https://code.claude.com/docs/en/claude-code-on-the-web

**Put the six values in a password manager either way.** That is the copy that
makes the next reconnect a two-minute job.

### 5. Verify

```bash
.venv/bin/python scripts/verify_connection.py
```

Read-only. It lists the accounts your credentials can reach, then reads up to
10 campaigns from the target account. It changes nothing.

## Using it

```python
from google_ads.auth import get_client, get_customer_id

client = get_client()
customer_id = get_customer_id()
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| `invalid_client: The OAuth client was not found` | client ID/secret wrong, or the Cloud project was deleted |
| `USER_PERMISSION_DENIED` | operating account isn't linked under the manager account, or `LOGIN_CUSTOMER_ID` isn't the manager ID |
| `DEVELOPER_TOKEN_NOT_APPROVED` | token belongs to a different manager account, or needs Basic Access |
| `invalid_grant` | refresh token revoked — re-run step 3 |
| Consent screen blocks sign-in | your email isn't a test user on the consent screen |
| Quota errors | 2,880/day test-access cap — batch calls or apply for Basic Access |

If Claude starts asking for more credentials mid-task, it usually already has
what it needs — re-check `.env` before generating anything new.
