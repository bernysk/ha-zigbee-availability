# Known bugs and review findings

Findings from code reviews, with a verdict and what was done about each one. New bugs
go in [GitHub Issues](https://github.com/bernysk/ha-zigbee-availability/issues). This
file records review results and decisions.

| Status | Meaning |
|---|---|
| Fixed | Confirmed and fixed, with a regression test |
| Partly valid | Part of the finding was wrong; the valid part is fixed |
| Deferred | Confirmed, but not fixed yet, with the reason |

## Codex review, 2026-11-07 (pre-release 0.1.0)

A static review of the full source by Codex. Each finding was checked against the code
and against Home Assistant 2026.10's source.

### 1. The timer started when the first entity went unavailable, not the last. Fixed

- **Severity:** high
- **Problem:** `since` was `min(last_changed)` across the device's entities. If one
  entity had been unavailable for a day and the rest dropped now, the device alerted on
  the next check instead of after the timeout.
- **Fix:** use `max(last_changed)`, the moment "all entities unavailable" became true.
- **Test:** `test_timer_starts_when_last_entity_goes_unavailable`

### 2. `unknown` counted as recovery. Fixed

- **Severity:** high
- **Problem:** anything other than "all unavailable" was treated as back online,
  including an entity briefly reporting `unknown` during startup. That sent a false
  "back online" message, dropped the stored outage, and later caused a duplicate alert.
- **Fix:** a device is now *online* only when at least one entity has a real value. A mix
  of `unknown` and `unavailable` is *indeterminate* and changes nothing.
- **Trade-off:** a device that comes back but only reports `unknown` for every entity
  stays marked offline until one of them reports a value. This is rare and safer than
  false recoveries.
- **Test:** `test_unknown_is_not_a_recovery`

### 3. Devices were evaluated with some entity states missing. Partly valid, fixed

- **Severity:** medium
- **Problem:** entities without a state were dropped, so a device with one unavailable
  entity and one not-yet-loaded entity counted as fully unavailable.
- **Fix:** a device is only judged *offline* when every monitored entity has a state
  and all of them are `unavailable`. A single real value still counts as online, even if
  another entity has no state yet, which is consistent with finding 2.
- **Not valid:** the claim that disabled entities are included.
  `er.async_entries_for_device()` already excludes them by default
  (`include_disabled_entities=False`).
- **Test:** `test_missing_state_defers_evaluation`

### 4. Unload didn't wait for a running check. Fixed

- **Severity:** medium
- **Problem:** an options change reloads the entry. A check still waiting in
  `Store.async_save` could finish after the new monitor had already loaded the old
  stored state, which could duplicate alerts or send them after unload.
- **Fix:** checks run under an `asyncio.Lock`. `async_unload_entry` awaits
  `monitor.async_stop()`, which sets a stop flag and waits for the lock before the
  platforms unload, so the next setup sees the saved state.
- **Test:** `test_stop_waits_for_running_check`

### 5. The persistent notification wasn't kept in sync. Fixed

- **Severity:** medium
- **Problem:** it was only updated when a device went offline or came back.
  - After a restart it was gone (HA keeps persistent notifications in memory only),
    even though stored devices were still offline.
  - Excluding or deleting the last offline device left it on screen.
  - Turning the option off left an existing one on screen.
- **Fix:** it is reconciled after every check against the current offline list and the
  option, starting from an "unrendered" state so the first check always creates or
  dismisses it.
- **Tests:** `test_persistent_notification_recreated_after_restart`,
  `test_persistent_notification_dismissed_when_device_excluded`,
  `test_persistent_notification_dismissed_when_disabled`

### 6. A failed notification is treated as delivered. Deferred in 0.1.0, fixed in 0.1.1

Codex challenged the deferral in the second review; see below.

- **Severity:** medium
- **Problem:** `notified` is saved before sending. If every notify target fails, the
  alert is not retried.
- **Why deferred:** failures where retrying would help are rare.
  `notify.mobile_app_*` usually doesn't raise when the phone is offline, because push
  delivery is queued by the companion app's cloud relay. The common real failure is a
  renamed or removed target, and retrying doesn't fix that. A proper fix needs
  per-target delivery state and retry limits.
- **Mitigation in 0.1.0:**
  - Failures are logged at `ERROR` level with the target and reason.
  - The new **Send test notification** button checks every target and shows failures
    in the UI.
  - The sensor, the events and the persistent notification are still updated even when
    sending fails.
- **Revisit:** if users report lost alerts.

## Codex re-review, 2026-11-07 (after 0.1.0)

Codex was given the 0.1.0 source and this file, and asked to check the fixes and to
argue against the decisions above.

### Fixes 1 to 5: confirmed

Codex confirmed fixes 2 to 5. For fix 1 it confirmed the new code path and raised R1
(below) about the existing one.

### Finding 3, "disabled entities are included": Codex accepted the rejection

`er.async_entries_for_device()` excludes disabled entities by default, so no extra filter
is needed.

### Finding 6 deferral: Codex didn't accept it. Fixed in 0.1.1

- **Codex's argument:** a notify provider that fails temporarily (raises
  `HomeAssistantError`) loses the alert for good. The test button working at setup time
  doesn't help then. With the persistent notification turned off, nothing tells the user.
  Codex also noted that "retrying rarely helps" wasn't backed by evidence. It suggested a
  bounded retry for the case where *every* target fails, which needs no per-target state.
- **Verdict:** accepted. The argument holds and the fix is small.
- **Fix:** if no target accepts an alert, it is retried on every check (30 s) for up to 10
  minutes, with "(delayed)" added to the title. Partial failures are not retried,
  because resending would duplicate the message on the targets that worked; the failing
  targets are logged. The retry queue is in memory only, so a restart during those 10
  minutes drops it. The sensor and persistent notification still show the device.
- **Tests:** `test_alert_retried_when_no_target_works`, `test_retry_gives_up`,
  `test_partial_failure_not_retried`

### R1. A recovery between two checks keeps the old timer. Not needed

- **Codex's scenario:** a device recovers and goes unavailable again *between* two
  30-second checks, so the next check still sees the old outage. The alert comes too
  early, or a second outage merges into an alert that was already sent.
- **Why it can't happen with ZHA** (checked in zha 2.4.3, `DeviceAvailabilityChecker`
  and `Device._check_available`):
  1. ZHA marks a device **available** as soon as any message arrives, but marks it
     **unavailable** only from its availability checker, which runs every **30–45 s**.
  2. Before marking a device unavailable, ZHA needs `_CHECKIN_GRACE_PERIODS = 2` failed
     pings, one per checker run. So after a device was last heard from, it takes at
     least two more checker runs (**at least 60 s**) to go unavailable, *whatever the
     unavailability timeout is set to*.
  3. Our check runs every 30 s, so it always sees the device online at least once in
     between and closes the old outage.
- **The one exception:** LUMI (Aqara) devices and devices without endpoints skip the
  pings. They can only flap within 30 s if ZHA's unavailability timeout is set below
  30 s. Aqara sensors report about every 50–60 minutes, so such a setting would mark them
  unavailable all the time anyway.
- **Cost of a fix:** a fix would have to tell a real new outage apart from timestamps
  reset by a restart, which is exactly what persisting `since` protects. Doing it
  reliably means listening to every ZHA state change instead of checking every 30 s.
  That's more code and more risk for a case ZHA's own design prevents.
- **Revisit:** if ZHA changes its availability logic, or Z2M support is added. Z2M marks
  devices unavailable on its own schedule.

### R2. An offline device stays listed if all its entities are excluded or disabled. Fixed in 0.1.1

- **Severity:** medium
- **Problem:** with every entity of an offline device labelled or disabled, the device
  had no states left. It counted as *indeterminate*, so its old entry stayed in the
  sensor and the persistent notification forever.
- **Fix:** a device with no monitored entities left is skipped like an excluded device,
  so its entry is dropped without a "back online" message.
- **Test:** `test_device_with_no_monitored_entities_is_forgotten`
