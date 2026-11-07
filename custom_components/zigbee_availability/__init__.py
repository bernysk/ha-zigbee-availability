"""Zigbee Availability: alert when ZHA devices stay unavailable."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .monitor import AvailabilityMonitor

PLATFORMS: list[Platform] = [Platform.SENSOR]

type ZigbeeAvailabilityConfigEntry = ConfigEntry[AvailabilityMonitor]


async def async_setup_entry(hass: HomeAssistant, entry: ZigbeeAvailabilityConfigEntry) -> bool:
    """Set up from a config entry."""
    monitor = AvailabilityMonitor(hass, entry)
    await monitor.async_start()
    entry.runtime_data = monitor
    entry.async_on_unload(monitor.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZigbeeAvailabilityConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ZigbeeAvailabilityConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
