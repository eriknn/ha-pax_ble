from homeassistant.const import Platform
from datetime import timedelta

# Global Constants
DOMAIN: str = "pax_ble"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.SELECT]

# Configuration Constants
CONF_NAME: str = "name"
CONF_MAC: str = "mac"
CONF_PIN: str = "pin"
CONF_SCAN_INTERVAL: str = "scan_interval"
CONF_SCAN_INTERVAL_FAST: str = "scan_interval_fast"

# Defaults
DEFAULT_SCAN_INTERVAL: int = 300  # Seconds
DEFAULT_SCAN_INTERVAL_FAST: int = 5  # Seconds
