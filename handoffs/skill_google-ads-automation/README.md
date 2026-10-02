# google-ads-automation skill — account-exclusions update, 2 October 2026

Trevor asked for the new-account SOP and the skill to carry the account-level
placement exclusion step, so it happens by default next time an account is set
up.

The repo side is done and durable: `build_specs/NEW_ACCOUNT_SOP.md`,
`build_specs/_ACCOUNT_TEMPLATE.json` (`account_level_setup`) and the standing
rule in `CLAUDE.md`.

## The skill side needs one manual step

`google-ads-automation` is a **plugin-backed skill** (`"source": "plugin"`,
`backingPluginId: plugin_01YT6H2ZVB9gQ7YRRvz6hni2`). It is synced into the
session container at startup, under
`/root/.claude/skills/synced/<...>/google-ads-automation/`. That copy is
rebuilt from the plugin on every sync, so edits made there are live for the
current session only and are lost afterwards. The edits below are applied in
this container; to make them permanent they have to go into the plugin source.

### 1. New reference file

Add `references/account-exclusions.md` to the skill, from
`references/account-exclusions.md` next to this README.

### 2. Workflow router — add one row, directly under the setup-guide row

```
| Account-level placement / content exclusions (new account, or a PMax campaign serving untargeted on Display or YouTube) | `references/account-exclusions.md` |
```

### 3. Build order — replace the "full account build from scratch" paragraph with

```
For a full account build from scratch, run the phases in this order: setup → **account-level exclusions** → keywords → campaigns → negative keywords (universal list) → ads → landing pages → tracking → audit cadence.

Account-level exclusions are second because they are set ONCE per account and then cover every campaign built afterwards — including PMax, which has no channel off-switch of its own. Setting them before the first campaign is enabled is what keeps budget off parked domains and in-app inventory. Never skip this phase on a new account; `references/account-exclusions.md` has the list and the scripts.
```

### 4. Safety rails — add a bullet after the Presence-targeting one

```
- Every new account gets account-level placement and content exclusions before its first campaign is enabled (Trevor's instruction, 2 October 2026). See `references/account-exclusions.md`.
```

## Worth knowing while editing the plugin

The skill's core philosophy still says to avoid Performance Max and Display for
cold traffic and that Search-only is the lead-gen default. The client ecommerce
accounts in this portfolio are built the other way — feed-only PMax is the house
pattern, per `CLAUDE.md` — so that section and the account template disagree.
The exclusions phase is written to be correct either way, but the contradiction
is real and should be reconciled deliberately rather than by accident.
