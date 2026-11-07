"""Tracks how long ZHA devices have been unavailable and sends alerts."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CHECK_INTERVAL,
    CONF_EXCLUDE_DEVICES,
    CONF_EXCLUDE_LABELS,
    CONF_NOTIFY_RECOVERY,
    CONF_NOTIFY_TARGETS,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_TIMEOUT,
    DEFAULT_NOTIFY_RECOVERY,
    DEFAULT_PERSISTENT_NOTIFICATION,
    DEFAULT_TIMEOUT,
    DOMAIN,
    EVENT_DEVICE_AVAILABLE,
    EVENT_DEVICE_UNAVAILABLE,
    PERSISTENT_NOTIFICATION_ID,
    STORAGE_VERSION,
    ZHA_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TrackedDevice:
    """A ZHA device that is currently unavailable."""

    name: str
    since: datetime
    notified: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "name": self.name,
            "since": self.since.isoformat(),
            "notified": self.notified,
        }


class AvailabilityMonitor:
    """Watches ZHA devices and alerts when one stays unavailable too long.

    A device counts as unavailable when every enabled ZHA entity it has is
    unavailable. Tracking state is persisted so restarts don't reset timers
    or cause duplicate alerts.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._tracked: dict[str, TrackedDevice] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------------ setup

    async def async_start(self) -> None:
        """Load stored state and start the periodic check."""
        data = await self._store.async_load() or {}
        for device_id, raw in data.get("devices", {}).items():
            since = dt_util.parse_datetime(raw.get("since", ""))
            if since is None:
                continue
            self._tracked[device_id] = TrackedDevice(
                name=raw.get("name", device_id),
                since=since,
                notified=bool(raw.get("notified", False)),
            )

        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, CHECK_INTERVAL))
        self._unsubs.append(async_at_started(self.hass, self._async_started))

    @callback
    def async_stop(self) -> None:
        """Stop the periodic check."""
        while self._unsubs:
            self._unsubs.pop()()

    async def _async_started(self, _hass: HomeAssistant) -> None:
        await self.async_check()

    # -------------------------------------------------------------- listeners

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Register a callback for when the device lists change."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    @callback
    def _async_notify_listeners(self) -> None:
        for update_callback in list(self._listeners):
            update_callback()

    # ------------------------------------------------------------- properties

    @property
    def options(self) -> dict[str, Any]:
        """Current options."""
        return dict(self.entry.options)

    @property
    def timeout(self) -> timedelta:
        """How long a device must be unavailable before alerting."""
        return timedelta(minutes=int(self.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)))

    @property
    def offline_devices(self) -> dict[str, TrackedDevice]:
        """Devices unavailable for longer than the timeout (alerted)."""
        return {k: v for k, v in self._tracked.items() if v.notified}

    @property
    def pending_devices(self) -> dict[str, TrackedDevice]:
        """Devices unavailable, but not yet for longer than the timeout."""
        return {k: v for k, v in self._tracked.items() if not v.notified}

    # ------------------------------------------------------------------ check

    async def _async_tick(self, _now: datetime) -> None:
        await self.async_check()

    def _zha_loaded(self) -> bool:
        return any(
            entry.state is ConfigEntryState.LOADED
            for entry in self.hass.config_entries.async_entries(ZHA_DOMAIN)
        )

    def _iter_devices(self) -> Iterator[tuple[dr.DeviceEntry, list[State]]]:
        """Yield monitored ZHA devices with the states of their entities.

        The state list is empty when the device's entities have no state yet
        (for example during startup); such devices are not evaluated.
        """
        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)
        zha_entry_ids = {
            entry.entry_id for entry in self.hass.config_entries.async_entries(ZHA_DOMAIN)
        }
        excluded_devices = set(self.options.get(CONF_EXCLUDE_DEVICES, []))
        excluded_labels = set(self.options.get(CONF_EXCLUDE_LABELS, []))

        for device in dev_reg.devices.values():
            if not zha_entry_ids & device.config_entries:
                continue
            if device.disabled or device.id in excluded_devices:
                continue
            if excluded_labels & device.labels:
                continue

            states: list[State] = []
            for entity in er.async_entries_for_device(ent_reg, device.id):
                if entity.platform != ZHA_DOMAIN or excluded_labels & entity.labels:
                    continue
                if (state := self.hass.states.get(entity.entity_id)) is not None:
                    states.append(state)
            yield device, states

    async def async_check(self) -> None:
        """Evaluate all devices, send alerts and update state."""
        if self.hass.state is not CoreState.running or not self._zha_loaded():
            return

        now = dt_util.utcnow()
        timeout = self.timeout
        went_offline: list[tuple[str, TrackedDevice]] = []
        came_back: list[tuple[str, TrackedDevice]] = []
        changed = False
        monitored: set[str] = set()

        for device, states in self._iter_devices():
            monitored.add(device.id)
            if not states:
                continue

            name = device.name_by_user or device.name or device.id
            tracked = self._tracked.get(device.id)

            if all(state.state == STATE_UNAVAILABLE for state in states):
                if tracked is None:
                    tracked = TrackedDevice(
                        name=name, since=min(state.last_changed for state in states)
                    )
                    self._tracked[device.id] = tracked
                    changed = True
                elif tracked.name != name:
                    tracked.name = name
                    changed = True

                if not tracked.notified and now - tracked.since >= timeout:
                    tracked.notified = True
                    went_offline.append((device.id, tracked))
                    changed = True
            elif tracked is not None:
                del self._tracked[device.id]
                changed = True
                if tracked.notified:
                    came_back.append((device.id, tracked))

        # Devices that were removed or excluded since: forget them silently.
        for device_id in set(self._tracked) - monitored:
            del self._tracked[device_id]
            changed = True

        if not changed:
            return

        for device_id, tracked in went_offline:
            self.hass.bus.async_fire(
                EVENT_DEVICE_UNAVAILABLE,
                {
                    "device_id": device_id,
                    "name": tracked.name,
                    "since": tracked.since.isoformat(),
                },
            )
        for device_id, tracked in came_back:
            self.hass.bus.async_fire(
                EVENT_DEVICE_AVAILABLE,
                {
                    "device_id": device_id,
                    "name": tracked.name,
                    "since": tracked.since.isoformat(),
                    "duration_seconds": int((now - tracked.since).total_seconds()),
                },
            )

        await self._store.async_save(
            {"devices": {k: v.as_dict() for k, v in self._tracked.items()}}
        )
        self._async_notify_listeners()

        if went_offline or came_back:
            self._update_persistent_notification()
        if went_offline:
            await self._async_send(*self._offline_message(went_offline))
        if came_back and self.options.get(CONF_NOTIFY_RECOVERY, DEFAULT_NOTIFY_RECOVERY):
            await self._async_send(*self._recovery_message(came_back, now))

    # ---------------------------------------------------------- notifications

    @staticmethod
    def _local_time(value: datetime) -> str:
        local = dt_util.as_local(value)
        if local.date() == dt_util.now().date():
            return local.strftime("%H:%M")
        return local.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _duration(delta: timedelta) -> str:
        minutes = int(delta.total_seconds() // 60)
        if minutes < 60:
            return f"{minutes} min"
        hours, minutes = divmod(minutes, 60)
        if hours < 24:
            return f"{hours} h {minutes} min"
        days, hours = divmod(hours, 24)
        return f"{days} d {hours} h"

    def _offline_message(self, devices: list[tuple[str, TrackedDevice]]) -> tuple[str, str]:
        if len(devices) == 1:
            title = "Zigbee device unavailable"
        else:
            title = f"{len(devices)} Zigbee devices unavailable"
        lines = [
            f"{tracked.name}: unavailable since {self._local_time(tracked.since)}"
            for _, tracked in sorted(devices, key=lambda item: item[1].name.lower())
        ]
        return title, "\n".join(lines)

    def _recovery_message(
        self, devices: list[tuple[str, TrackedDevice]], now: datetime
    ) -> tuple[str, str]:
        if len(devices) == 1:
            title = "Zigbee device back online"
        else:
            title = f"{len(devices)} Zigbee devices back online"
        lines = [
            f"{tracked.name}: back after {self._duration(now - tracked.since)}"
            for _, tracked in sorted(devices, key=lambda item: item[1].name.lower())
        ]
        return title, "\n".join(lines)

    @callback
    def _update_persistent_notification(self) -> None:
        if not self.options.get(CONF_PERSISTENT_NOTIFICATION, DEFAULT_PERSISTENT_NOTIFICATION):
            return
        offline = self.offline_devices
        if not offline:
            persistent_notification.async_dismiss(self.hass, PERSISTENT_NOTIFICATION_ID)
            return
        lines = [
            f"- **{tracked.name}**: unavailable since {self._local_time(tracked.since)}"
            for tracked in sorted(offline.values(), key=lambda t: t.name.lower())
        ]
        persistent_notification.async_create(
            self.hass,
            "\n".join(lines),
            title="Unavailable Zigbee devices",
            notification_id=PERSISTENT_NOTIFICATION_ID,
        )

    async def _async_send(self, title: str, message: str) -> None:
        """Send a message to every configured notify target.

        A target is either a notify service (``notify.mobile_app_phone``) or a
        notify entity, which is sent through ``notify.send_message``.
        """
        for target in self.options.get(CONF_NOTIFY_TARGETS, []):
            domain, _, service = target.partition(".")
            if not service:
                domain, service = "notify", target
            try:
                if self.hass.services.has_service(domain, service):
                    await self.hass.services.async_call(
                        domain, service, {"title": title, "message": message}, blocking=True
                    )
                elif domain == "notify" and self.hass.states.get(target) is not None:
                    await self.hass.services.async_call(
                        "notify",
                        "send_message",
                        {"entity_id": target, "title": title, "message": message},
                        blocking=True,
                    )
                else:
                    _LOGGER.warning("Notify target %s does not exist", target)
            except HomeAssistantError as err:
                _LOGGER.warning("Sending notification via %s failed: %s", target, err)
