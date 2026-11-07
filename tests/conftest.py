"""Shared fixtures."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    return


@pytest.fixture
def zha_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A ZHA config entry marked as loaded, without loading real ZHA."""
    entry = MockConfigEntry(domain="zha", title="ZHA")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry
