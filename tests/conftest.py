"""Shared fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    return


@pytest.fixture(autouse=True)
def mock_zha(hass: HomeAssistant) -> None:
    """Replace ZHA with a stub so the real zha library is never imported."""
    mock_integration(
        hass,
        MockModule(
            "zha",
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )


@pytest.fixture
def zha_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A ZHA config entry marked as loaded."""
    entry = MockConfigEntry(domain="zha", title="ZHA")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry
