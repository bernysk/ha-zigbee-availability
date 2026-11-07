"""Sensor listing unavailable ZHA devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZigbeeAvailabilityConfigEntry
from .const import DOMAIN
from .monitor import AvailabilityMonitor, TrackedDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZigbeeAvailabilityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor."""
    async_add_entities([UnavailableDevicesSensor(entry.runtime_data, entry.entry_id)])


def _device_list(devices: dict[str, TrackedDevice]) -> list[dict[str, Any]]:
    return [
        {"device_id": device_id, "name": tracked.name, "since": tracked.since.isoformat()}
        for device_id, tracked in sorted(devices.items(), key=lambda i: i[1].name.lower())
    ]


class UnavailableDevicesSensor(SensorEntity):
    """Number of ZHA devices unavailable for longer than the timeout."""

    _attr_has_entity_name = True
    _attr_translation_key = "unavailable_devices"
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:zigbee"

    def __init__(self, monitor: AvailabilityMonitor, entry_id: str) -> None:
        """Initialize."""
        self._monitor = monitor
        self._attr_unique_id = f"{entry_id}_unavailable_devices"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Zigbee Availability",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to monitor updates."""
        self.async_on_remove(self._monitor.async_add_listener(self.async_write_ha_state))

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
