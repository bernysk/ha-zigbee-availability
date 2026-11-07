"""Sensors listing unavailable ZHA devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZigbeeAvailabilityConfigEntry
from .const import DOMAIN
from .monitor import AvailabilityMonitor, TrackedDevice

NO_DEVICES = "None"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZigbeeAvailabilityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    monitor = entry.runtime_data
    async_add_entities(
        [
            UnavailableDevicesSensor(monitor, entry.entry_id),
            UnavailableDeviceNamesSensor(monitor, entry.entry_id),
        ]
    )


def _sorted(devices: dict[str, TrackedDevice]) -> list[tuple[str, TrackedDevice]]:
    return sorted(devices.items(), key=lambda item: item[1].name.lower())


def _device_list(devices: dict[str, TrackedDevice]) -> list[dict[str, Any]]:
    return [
        {"device_id": device_id, "name": tracked.name, "since": tracked.since.isoformat()}
        for device_id, tracked in _sorted(devices)
    ]


def names_state(names: list[str], limit: int = MAX_LENGTH_STATE_STATE) -> str:
    """Join names into a state that fits HA's state length limit.

    Too long a list is cut at a whole name and ends with "… (+N more)".
    """
    if not names:
        return NO_DEVICES
    full = ", ".join(names)
    if len(full) <= limit:
        return full
    for shown in range(len(names) - 1, 0, -1):
        text = f"{', '.join(names[:shown])}, … (+{len(names) - shown} more)"
        if len(text) <= limit:
            return text
    count = len(names)
    return f"{count} device{'s' if count != 1 else ''}"[:limit]


class _MonitorSensor(SensorEntity):
    """Common setup for sensors fed by the monitor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:zigbee"

    def __init__(self, monitor: AvailabilityMonitor, entry_id: str, key: str) -> None:
        """Initialize."""
        self._monitor = monitor
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Zigbee Availability",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to monitor updates."""
        self.async_on_remove(self._monitor.async_add_listener(self.async_write_ha_state))


class UnavailableDevicesSensor(_MonitorSensor):
    """Number of ZHA devices unavailable for longer than the timeout."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, monitor: AvailabilityMonitor, entry_id: str) -> None:
        """Initialize."""
        super().__init__(monitor, entry_id, "unavailable_devices")

    @property
    def native_value(self) -> int:
        """Number of devices past the timeout."""
        return len(self._monitor.offline_devices)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Device details."""
        return {
            "devices": _device_list(self._monitor.offline_devices),
            "pending": _device_list(self._monitor.pending_devices),
            "timeout_minutes": int(self._monitor.timeout.total_seconds() // 60),
        }


class UnavailableDeviceNamesSensor(_MonitorSensor):
    """Names of ZHA devices unavailable for longer than the timeout."""

    def __init__(self, monitor: AvailabilityMonitor, entry_id: str) -> None:
        """Initialize."""
        super().__init__(monitor, entry_id, "unavailable_device_names")

    @property
    def native_value(self) -> str:
        """Comma-separated names, or "None"."""
        return names_state([tracked.name for _, tracked in _sorted(self._monitor.offline_devices)])
