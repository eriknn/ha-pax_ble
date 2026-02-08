from enum import Enum
from homeassistant.const import Platform

# Global Constants
DOMAIN: str = "pax_ble"
PLATFORMS = [
    Platform.TIME,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]

# Configuration Constants
CONF_ACTION = "action"
CONF_ADD_DEVICE = "add_device"
CONF_WRONG_PIN_SELECTOR = "wrong_pin_selector"
CONF_EDIT_DEVICE = "edit_device"
CONF_REMOVE_DEVICE = "remove_device"

# Configuration Device Constants
CONF_NAME: str = "name"
CONF_MODEL: str = "model"
CONF_MAC: str = "mac"
CONF_PIN: str = "pin"
CONF_SCAN_INTERVAL: str = "scan_interval"
CONF_SCAN_INTERVAL_FAST: str = "scan_interval_fast"

# Defaults
DEFAULT_SCAN_INTERVAL: int = 300  # Seconds
DEFAULT_SCAN_INTERVAL_FAST: int = 5  # Seconds


# Device models
class DeviceModel(str, Enum):
    CALIMA = "Calima"
    LEVANTE = "Levante"
    SVARA = "Svara"
    SVENSA = "Svensa"
