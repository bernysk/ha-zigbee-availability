"""Button that sends a test notification."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZigbeeAvailabilityConfigEntry
from .const import DOMAIN
from .monitor import AvailabilityMonitor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZigbeeAvailabilityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button."""
    async_add_entities([TestNotificationButton(entry.runtime_data, entry.entry_id)])


class TestNotificationButton(ButtonEntity):
    """Send a test message to the configured notify targets."""

    _attr_has_entity_name = True
    _attr_translation_key = "test_notification"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:bell-ring"

    def __init__(self, monitor: AvailabilityMonitor, entry_id: str) -> None:
        """Initialize."""
        self._monitor = monitor
        self._attr_unique_id = f"{entry_id}_test_notification"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Zigbee Availability",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Send the test message; errors are shown to the user."""
        await self._monitor.async_send_test()
