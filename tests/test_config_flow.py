"""Config and options flow tests."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zigbee_availability.const import (
    CONF_EXCLUDE_DEVICES,
    CONF_EXCLUDE_LABELS,
    CONF_NOTIFY_RECOVERY,
    CONF_NOTIFY_TARGETS,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_TIMEOUT,
    DOMAIN,
)

USER_INPUT = {
    CONF_TIMEOUT: 20.0,
    CONF_NOTIFY_TARGETS: ["notify.mobile_app_phone"],
    CONF_NOTIFY_RECOVERY: True,
    CONF_PERSISTENT_NOTIFICATION: False,
    CONF_EXCLUDE_DEVICES: [],
    CONF_EXCLUDE_LABELS: ["no_unavailable_alert"],
}


async def test_user_flow(hass: HomeAssistant, zha_entry: MockConfigEntry) -> None:
    """Setup stores the answers as options, with the timeout as an int."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"][CONF_TIMEOUT] == 20
    assert isinstance(result["options"][CONF_TIMEOUT], int)
    assert result["options"][CONF_EXCLUDE_LABELS] == ["no_unavailable_alert"]


async def test_abort_without_zha(hass: HomeAssistant) -> None:
    """Setup refuses to start when ZHA isn't configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "zha_not_configured"


async def test_single_instance(hass: HomeAssistant, zha_entry: MockConfigEntry) -> None:
    """A second instance is not allowed."""
    MockConfigEntry(domain=DOMAIN, options=USER_INPUT).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass: HomeAssistant, zha_entry: MockConfigEntry) -> None:
    """Options can be changed after setup."""
    entry = MockConfigEntry(domain=DOMAIN, options={**USER_INPUT, CONF_TIMEOUT: 20})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_TIMEOUT: 5.0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_TIMEOUT] == 5
