"""Device names sensor."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
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
)
from custom_components.zigbee_availability.sensor import names_state

NAMES = "sensor.zigbee_availability_unavailable_device_names"
COUNT = "sensor.zigbee_availability_unavailable_devices"


def test_names_state_short() -> None:
    """Short lists are joined in full; an empty list reads None."""
    assert names_state([]) == "None"
    assert names_state(["A", "B"]) == "A, B"


def test_names_state_truncates_at_whole_names() -> None:
    """Long lists are cut at a whole name and say how many are hidden."""
    names = [f"Zigbee device number {i:02d}" for i in range(30)]
    state = names_state(names)
    assert len(state) <= 255
    shown = state.split(", … ")[0].split(", ")
    assert all(name in names for name in shown)
    assert state.endswith(f"(+{30 - len(shown)} more)")


def test_names_state_single_huge_name() -> None:
    """A list that can't fit even one name falls back to a count."""
    assert names_state(["x" * 300, "y" * 300]) == "2 devices"
    assert names_state(["x" * 300]) == "1 device"


async def test_names_sensor_follows_outages(
    hass: HomeAssistant, zha_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """The names sensor lists offline devices alphabetically next to the count."""
    async_mock_service(hass, "notify", "mobile_app_phone")
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    entity_ids = {}
    for ieee, name in (("00:91", "Kitchen plug"), ("00:92", "Garage sensor")):
        device = dev_reg.async_get_or_create(
            config_entry_id=zha_entry.entry_id, identifiers={("zha", ieee)}, name=name
        )
        entity = ent_reg.async_get_or_create(
            "sensor", "zha", ieee, device_id=device.id, config_entry=zha_entry
        )
        hass.states.async_set(entity.entity_id, "21")
        entity_ids[name] = entity.entity_id

    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_TIMEOUT: 15,
            CONF_NOTIFY_TARGETS: ["notify.mobile_app_phone"],
            CONF_NOTIFY_RECOVERY: True,
            CONF_PERSISTENT_NOTIFICATION: False,
            CONF_EXCLUDE_DEVICES: [],
            CONF_EXCLUDE_LABELS: [],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(NAMES).state == "None"

    for entity_id in entity_ids.values():
        hass.states.async_set(entity_id, "unavailable")
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NAMES).state == "Garage sensor, Kitchen plug"
    assert hass.states.get(COUNT).state == "2"

    hass.states.async_set(entity_ids["Garage sensor"], "21")
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NAMES).state == "Kitchen plug"
