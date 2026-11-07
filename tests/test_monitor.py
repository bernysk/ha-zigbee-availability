"""Availability tracking, notifications and persistence."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.zigbee_availability.const import (
    CONF_EXCLUDE_DEVICES,
    CONF_EXCLUDE_LABELS,
    CONF_NOTIFY_RECOVERY,
    CONF_NOTIFY_TARGETS,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_TIMEOUT,
    DOMAIN,
    EVENT_DEVICE_AVAILABLE,
    EVENT_DEVICE_UNAVAILABLE,
)

SENSOR = "sensor.zigbee_availability_unavailable_devices"

OPTIONS: dict[str, Any] = {
    CONF_TIMEOUT: 15,
    CONF_NOTIFY_TARGETS: ["notify.mobile_app_phone"],
    CONF_NOTIFY_RECOVERY: True,
    CONF_PERSISTENT_NOTIFICATION: True,
    CONF_EXCLUDE_DEVICES: [],
    CONF_EXCLUDE_LABELS: ["ignored"],
}


def _add_device(
    hass: HomeAssistant, zha_entry: MockConfigEntry, ieee: str, name: str, entities: int = 2
) -> tuple[dr.DeviceEntry, list[str]]:
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=zha_entry.entry_id, identifiers={("zha", ieee)}, name=name
    )
    entity_ids = []
    for index in range(entities):
        entity = ent_reg.async_get_or_create(
            "sensor", "zha", f"{ieee}-{index}", device_id=device.id, config_entry=zha_entry
        )
        hass.states.async_set(entity.entity_id, "21")
        entity_ids.append(entity.entity_id)
    return device, entity_ids


def _set(hass: HomeAssistant, entity_ids: list[str], state: str) -> None:
    for entity_id in entity_ids:
        hass.states.async_set(entity_id, state)


async def _setup(hass: HomeAssistant, options: dict[str, Any] | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, options=options or OPTIONS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture
def notify_calls(hass: HomeAssistant):
    return async_mock_service(hass, "notify", "mobile_app_phone")


async def test_alert_after_timeout_and_recovery(
    hass: HomeAssistant,
    zha_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    notify_calls,
) -> None:
    """One alert after the timeout, one when the device comes back."""
    device, entities = _add_device(hass, zha_entry, "00:11", "Kitchen plug")
    down_events = async_capture_events(hass, EVENT_DEVICE_UNAVAILABLE)
    up_events = async_capture_events(hass, EVENT_DEVICE_AVAILABLE)
    await _setup(hass)
    assert hass.states.get(SENSOR).state == "0"

    _set(hass, entities, "unavailable")
    await _advance(hass, freezer, 10)
    assert notify_calls == []
    assert hass.states.get(SENSOR).state == "0"
    assert hass.states.get(SENSOR).attributes["pending"][0]["name"] == "Kitchen plug"

    await _advance(hass, freezer, 6)
    assert len(notify_calls) == 1
    assert notify_calls[0].data["title"] == "Zigbee device unavailable"
    assert "Kitchen plug" in notify_calls[0].data["message"]
    assert hass.states.get(SENSOR).state == "1"
    assert hass.states.get(SENSOR).attributes["devices"][0]["device_id"] == device.id
    assert len(down_events) == 1
    assert down_events[0].data["device_id"] == device.id

    # Staying offline does not repeat the alert.
    await _advance(hass, freezer, 30)
    assert len(notify_calls) == 1

    _set(hass, entities, "21")
    await _advance(hass, freezer, 1)
    assert len(notify_calls) == 2
    assert notify_calls[1].data["title"] == "Zigbee device back online"
    assert hass.states.get(SENSOR).state == "0"
    assert len(up_events) == 1
    assert up_events[0].data["duration_seconds"] >= 46 * 60


async def test_short_outage_is_silent(
    hass: HomeAssistant,
    zha_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    notify_calls,
) -> None:
    """A device back before the timeout causes no alert and no recovery message."""
    _, entities = _add_device(hass, zha_entry, "00:12", "Hall sensor")
    await _setup(hass)

    _set(hass, entities, "unavailable")
    await _advance(hass, freezer, 5)
    _set(hass, entities, "21")
    await _advance(hass, freezer, 20)
    assert notify_calls == []
    assert hass.states.get(SENSOR).attributes["pending"] == []


async def test_partial_unavailability_is_ignored(
    hass: HomeAssistant,
    zha_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    notify_calls,
) -> None:
    """Only a device whose entities are all unavailable counts."""
    _, entities = _add_device(hass, zha_entry, "00:13", "Bulb")
    await _setup(hass)

    _set(hass, entities[:1], "unavailable")
    await _advance(hass, freezer, 30)
    assert notify_calls == []


async def test_exclusions(
    hass: HomeAssistant,
    zha_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    notify_calls,
) -> None:
    """Excluded devices, labelled devices and labelled entities are respected."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    excluded, excluded_entities = _add_device(hass, zha_entry, "00:21", "Excluded")
    labelled, labelled_entities = _add_device(hass, zha_entry, "00:22", "Labelled")
    dev_reg.async_update_device(labelled.id, labels={"ignored"})
    # Second entity of this device is always unavailable but labelled, so only
    # the first entity decides.
    _, mixed_entities = _add_device(hass, zha_entry, "00:23", "Mixed")
    ent_reg.async_update_entity(mixed_entities[1], labels={"ignored"})
    _set(hass, mixed_entities[1:], "unavailable")

    await _setup(hass, {**OPTIONS, CONF_EXCLUDE_DEVICES: [excluded.id]})

    _set(hass, excluded_entities + labelled_entities, "unavailable")
    await _advance(hass, freezer, 20)
    assert notify_calls == []

    _set(hass, mixed_entities[:1], "unavailable")
    await _advance(hass, freezer, 20)
    assert len(notify_calls) == 1
    assert "Mixed" in notify_calls[0].data["message"]


async def test_batched_alert(
    hass: HomeAssistant,
    zha_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    notify_calls,
) -> None:
    """Devices that cross the timeout together share one message."""
    _, first = _add_device(hass, zha_entry, "00:31", "Plug A")
    _, second = _add_device(hass, zha_entry, "00:32", "Plug B")
    await _setup(hass)

    _set(hass, first + second, "unavailable")
    await _advance(hass, freezer, 16)
    assert len(notify_calls) == 1
    assert notify_calls[0].data["title"] == "2 Zigbee devices unavailable"


async def test_no_recovery_message_when_disabled(
    hass: HomeAssistant,
    zha_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    notify_calls,
) -> None:
    """Recovery messages can be turned off."""
    _, entities = _add_device(hass, zha_entry, "00:41", "Plug")
    await _setup(hass, {**OPTIONS, CONF_NOTIFY_RECOVERY: False})

    _set(hass, entities, "unavailable")
    await _advance(hass, freezer, 16)
    _set(hass, entities, "21")
    await _advance(hass, freezer, 1)
    assert len(notify_calls) == 1


async def test_restart_keeps_state(
    hass: HomeAssistant,
    zha_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    notify_calls,
) -> None:
    """Reloading (like a restart) neither repeats the alert nor resets the timer."""
    _, entities = _add_device(hass, zha_entry, "00:51", "Garage sensor")
    entry = await _setup(hass)

    _set(hass, entities, "unavailable")
    await _advance(hass, freezer, 16)
    assert len(notify_calls) == 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    # A restart resets last_changed; the stored timestamp must win.
    _set(hass, entities, "unknown")
    _set(hass, entities, "unavailable")
    await hass.async_block_till_done()
    await _advance(hass, freezer, 20)
    assert len(notify_calls) == 1
    assert hass.states.get(SENSOR).state == "1"

    _set(hass, entities, "21")
    await _advance(hass, freezer, 1)
    assert len(notify_calls) == 2
    assert notify_calls[1].data["title"] == "Zigbee device back online"


async def test_waits_for_zha(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    """Nothing is evaluated while ZHA is not loaded."""
    zha = MockConfigEntry(domain="zha")
    zha.add_to_hass(hass)
    _, entities = _add_device(hass, zha, "00:61", "Plug")
    await _setup(hass)

    _set(hass, entities, "unavailable")
    await _advance(hass, freezer, 30)
    assert notify_calls == []
    assert hass.states.get(SENSOR).attributes["pending"] == []
