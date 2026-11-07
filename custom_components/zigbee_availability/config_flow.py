"""Config and options flow for Zigbee Availability."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    DeviceSelector,
    DeviceSelectorConfig,
    LabelSelector,
    LabelSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .const import (
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
    ZHA_DOMAIN,
)

_SKIP_NOTIFY_SERVICES = {"send_message", "persistent_notification"}


def _notify_targets(hass: HomeAssistant) -> list[str]:
    """Notify services and notify entities the user can pick from."""
    targets = {
        f"notify.{service}"
        for service in hass.services.async_services_for_domain("notify")
        if service not in _SKIP_NOTIFY_SERVICES
    }
    targets.update(state.entity_id for state in hass.states.async_all("notify"))
    return sorted(targets)


def _schema(hass: HomeAssistant, values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_TIMEOUT, default=values.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=10080,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_NOTIFY_TARGETS, default=list(values.get(CONF_NOTIFY_TARGETS, []))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_notify_targets(hass),
                    multiple=True,
                    custom_value=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_NOTIFY_RECOVERY,
                default=values.get(CONF_NOTIFY_RECOVERY, DEFAULT_NOTIFY_RECOVERY),
            ): BooleanSelector(),
            vol.Required(
                CONF_PERSISTENT_NOTIFICATION,
                default=values.get(CONF_PERSISTENT_NOTIFICATION, DEFAULT_PERSISTENT_NOTIFICATION),
            ): BooleanSelector(),
            vol.Optional(
                CONF_EXCLUDE_DEVICES,
                default=list(values.get(CONF_EXCLUDE_DEVICES, [])),
            ): DeviceSelector(DeviceSelectorConfig(integration=ZHA_DOMAIN, multiple=True)),
            vol.Optional(
                CONF_EXCLUDE_LABELS,
                default=list(values.get(CONF_EXCLUDE_LABELS, [])),
            ): LabelSelector(LabelSelectorConfig(multiple=True)),
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    data[CONF_TIMEOUT] = int(data[CONF_TIMEOUT])
    return data


class ZigbeeAvailabilityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the options."""
        if not self.hass.config_entries.async_entries(ZHA_DOMAIN):
            return self.async_abort(reason="zha_not_configured")
        if user_input is not None:
            return self.async_create_entry(
                title="Zigbee Availability", data={}, options=_clean(user_input)
            )
        return self.async_show_form(step_id="user", data_schema=_schema(self.hass, {}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return ZigbeeAvailabilityOptionsFlow()


class ZigbeeAvailabilityOptionsFlow(OptionsFlow):
    """Change settings after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the same form as setup, prefilled."""
        if user_input is not None:
            return self.async_create_entry(data=_clean(user_input))
        return self.async_show_form(
            step_id="init", data_schema=_schema(self.hass, self.config_entry.options)
        )
