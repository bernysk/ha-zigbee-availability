"""Test notification button."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.zigbee_availability.const import (
    CONF_EXCLUDE_DEVICES,
    CONF_EXCLUDE_LABELS,
    CONF_NOTIFY_RECOVERY,
    CONF_NOTIFY_TARGETS,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_TIMEOUT,
    DOMAIN,
)

BUTTON = "button.zigbee_availability_send_test_notification"

OPTIONS: dict[str, Any] = {
    CONF_TIMEOUT: 15,
    CONF_NOTIFY_TARGETS: ["notify.mobile_app_phone"],
    CONF_NOTIFY_RECOVERY: True,
    CONF_PERSISTENT_NOTIFICATION: True,
    CONF_EXCLUDE_DEVICES: [],
    CONF_EXCLUDE_LABELS: [],
}


async def _setup(hass: HomeAssistant, options: dict[str, Any]) -> None:
    entry = MockConfigEntry(domain=DOMAIN, options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _press(hass: HomeAssistant) -> None:
    await hass.services.async_call("button", "press", {"entity_id": BUTTON}, blocking=True)


async def test_press_sends_test_message(hass: HomeAssistant, zha_entry: MockConfigEntry) -> None:
    """Pressing sends to every target."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await _setup(hass, OPTIONS)
    await _press(hass)
    assert len(calls) == 1
    assert calls[0].data["title"] == "Zigbee Availability test"


async def test_press_without_targets_raises(
    hass: HomeAssistant, zha_entry: MockConfigEntry
) -> None:
    """With no targets the user gets an error instead of silence."""
    await _setup(hass, {**OPTIONS, CONF_NOTIFY_TARGETS: []})
    with pytest.raises(HomeAssistantError, match="No notify targets"):
        await _press(hass)


async def test_press_with_missing_target_raises(
    hass: HomeAssistant, zha_entry: MockConfigEntry
) -> None:
    """A broken target is named in the error; working ones still receive it."""
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await _setup(hass, {**OPTIONS, CONF_NOTIFY_TARGETS: ["notify.mobile_app_phone", "notify.old"]})
    with pytest.raises(HomeAssistantError, match=r"notify\.old: does not exist"):
        await _press(hass)
    assert len(calls) == 1
