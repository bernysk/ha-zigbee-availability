# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

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
