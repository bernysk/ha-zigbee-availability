"""Constants for Zigbee Availability."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "zigbee_availability"
ZHA_DOMAIN: Final = "zha"

CONF_TIMEOUT: Final = "timeout_minutes"
CONF_NOTIFY_TARGETS: Final = "notify_targets"
CONF_NOTIFY_RECOVERY: Final = "notify_recovery"
CONF_PERSISTENT_NOTIFICATION: Final = "persistent_notification"
CONF_EXCLUDE_DEVICES: Final = "exclude_devices"
CONF_EXCLUDE_LABELS: Final = "exclude_labels"

DEFAULT_TIMEOUT: Final = 15
DEFAULT_NOTIFY_RECOVERY: Final = True
DEFAULT_PERSISTENT_NOTIFICATION: Final = True

EVENT_DEVICE_UNAVAILABLE: Final = f"{DOMAIN}_device_unavailable"
EVENT_DEVICE_AVAILABLE: Final = f"{DOMAIN}_device_available"

CHECK_INTERVAL: Final = timedelta(seconds=30)
STORAGE_VERSION: Final = 1
PERSISTENT_NOTIFICATION_ID: Final = DOMAIN
