# CLAUDE.md

Guidance for Claude Code (and other AI agents) working in this repository.

## What this is

A Home Assistant custom integration, domain `zigbee_availability`. It alerts when a
**ZHA** Zigbee device stays unavailable longer than a timeout. It's distributed through
the HA Marketplace (HACS) from GitHub releases. **ZHA only.** Zigbee2MQTT is planned but
needs a tester. Don't add Z2M code that nobody can run.

## Layout

| Path | Purpose |
|---|---|
| `custom_components/zigbee_availability/monitor.py` | Core logic: device evaluation, tracking, persistence, notifications, retries |
| `custom_components/zigbee_availability/sensor.py` | Count sensor (with attributes) and names sensor |
| `custom_components/zigbee_availability/button.py` | "Send test notification" button |
| `custom_components/zigbee_availability/config_flow.py` | Setup and options form (the same schema for both) |
| `custom_components/zigbee_availability/translations/en.json` | UI strings, including entity names via `translation_key` |
| `tests/` | `pytest-homeassistant-custom-component` tests; ZHA is stubbed in `conftest.py` |
| `BUGS.md` | Review findings with verdicts and reasons |
| `CHANGELOG.md` | Keep a Changelog format; release notes are built from it |

## Commands

```bash
pip install -r requirements_test.txt
ruff format . && ruff check .
pytest
```

The tests need **Linux or macOS**. HA's test runner imports `fcntl` and `resource`, so it
doesn't run on Windows. On Windows, run ruff locally and rely on GitHub Actions
(`.github/workflows/validate.yml`: HACS validation, hassfest, ruff, pytest).

## Behaviour that must not regress

These are tested, and each was a review finding (see BUGS.md):

- **Device status** (`_evaluate`):
  - *offline* only when every monitored entity has a state and all are `unavailable`;
  - *online* when at least one entity has a real value (not `unknown`/`unavailable`);
  - anything else is *indeterminate*, and tracking is left unchanged.
- **The timer starts at the latest `last_changed`**, when the last entity went
  unavailable.
- **Tracking is persisted** in a `Store`. Restarts must not reset timers or repeat
  alerts, because `last_changed` resets on restart and the stored `since` wins.
- **A device with no monitored entities** (all disabled or excluded) is skipped and its
  tracking dropped silently.
- **Checks run under `asyncio.Lock`.** `async_unload_entry` awaits `monitor.async_stop()`
  before unloading platforms.
- **The persistent notification is reconciled after every check**, not only on changes.
  HA doesn't persist it across restarts.
- **Undelivered alerts:** retried only when *every* target fails (no duplicates), at most
  `MAX_DELIVERY_ATTEMPTS`.
- **Unique IDs are `{entry_id}_{key}`.** Never change existing ones, or users lose entity
  history and customizations.

Deliberately not done, with reasons in BUGS.md: per-target retry, and handling a
recovery and re-failure between two checks (ZHA's availability checker makes that
impossible).

## Compatibility

- The minimum HA version is in `hacs.json` (`homeassistant`). Before using a newer HA
  API, check the version that introduced it (download that `homeassistant` wheel and grep
  it) and raise the minimum if needed. CI only tests the latest HA. 0.1.2 exists because
  `AddConfigEntryEntitiesCallback` (2025.3) was used while 2025.1 was claimed.
- Keep `manifest.json` keys as hassfest wants them: `domain`, `name`, then alphabetical.
  `categories` must be valid HA category IDs, or the HACS action fails.

## Conventions

- **Every change:**
  - update `CHANGELOG.md` (an *Unreleased* or next-version section) and the README when
    behaviour or options change;
  - add or adjust tests;
  - keep each logical change in its own commit.
- **Review findings** go in BUGS.md as **Fixed / Partly valid / Not needed / Deferred**,
  with the reasoning and the regression test name. When rejecting a finding, back it with
  evidence (HA or ZHA source, a test), not assumptions.
- **Release:**
  1. bump `version` in `manifest.json`;
  2. add `## [X.Y.Z] - YYYY-MM-DD` to the CHANGELOG;
  3. push to `main` and wait for green CI;
  4. push the tag `vX.Y.Z`.

  `release.yml` checks that the tag matches the manifest version and publishes the
  CHANGELOG section as the release notes. Use absolute GitHub URLs in CHANGELOG links,
  because relative links break on the release page.
- **Commit messages** use the imperative mood and explain *why* in the body.
- The code is AI-generated, and the README says so (*About the code*). Keep that section
  accurate.
