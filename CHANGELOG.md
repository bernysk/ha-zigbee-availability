# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.2] - 2026-11-07

### Added

- `sensor.zigbee_availability_unavailable_device_names` shows the names of offline
  devices (e.g. `Garage sensor, Kitchen plug`) or `None`. A list longer than HA's
  255-character state limit is cut at a whole name and ends with `… (+N more)`. The count
  sensor is unchanged.

### Fixed

- Minimum Home Assistant version raised to **2025.3.0**. The integration uses
  `AddConfigEntryEntitiesCallback`, which first appears in 2025.3, so it failed to load
  on 2025.1 and 2025.2 even though `hacs.json` claimed support.

## [0.1.1] - 2026-11-07

### Fixed (found in Codex re-review, see [BUGS.md](https://github.com/bernysk/ha-zigbee-availability/blob/main/BUGS.md))

- Alerts that no notify target accepts are retried every 30 seconds for up to 10
  minutes, with "(delayed)" added to the title. Partial failures are not retried, to
  avoid duplicates.
- A device whose entities are all excluded by label or disabled is no longer stuck in
  the offline list.

### Documentation

- README states that the code is AI-generated (Claude Code, reviewed by Codex) and
  how it is checked.

## [0.1.0] - 2026-11-07

### Added

- First release, ZHA only.
- Alert when a ZHA device has been unavailable longer than a configurable timeout
  (a device counts as unavailable when all of its enabled ZHA entities are).
- Optional "back online" message with outage duration.
- Notify targets: any notify service (e.g. `notify.mobile_app_phone`) or notify entity.
- Optional persistent notification listing all currently unavailable devices.
- Exclusions by device and by label (device labels exclude the device; entity labels
  exclude that entity from the check).
- `sensor.zigbee_availability_unavailable_devices` with `devices` and `pending` attributes.
- `zigbee_availability_device_unavailable` and `zigbee_availability_device_available` events.
- Tracking survives restarts: no repeated alerts and no reset timers.
- Setup and options in the UI.
- **Send test notification** button that checks every notify target and reports any
  that fail.

### Fixed (found in pre-release review, see [BUGS.md](BUGS.md))

- The timeout now starts when the *last* entity of a device goes unavailable.
- `unknown` states, or entities without a state yet, no longer count as recovery or
  trigger alerts (no false "back online" messages during startup).
- Unload waits for a running check, so an options change can't load stale state or
  duplicate an alert.
- The persistent notification is kept in sync after restarts, exclusions and option
  changes.
- Failed notify targets are logged as errors with the reason.
