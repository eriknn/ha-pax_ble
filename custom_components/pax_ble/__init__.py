"""Support for Pax fans."""
import logging
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_NAME,
    CONF_MAC,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST
)
from .coordinator import PaxCalimaCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Set up platform from a ConfigEntry."""
    _LOGGER.debug("Setting up entry: %s", entry.data[CONF_NAME])
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Load config data
    name = entry.data[CONF_NAME]
    mac = entry.data[CONF_MAC]
    pin = entry.data[CONF_PIN]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    scan_interval_fast = entry.data[CONF_SCAN_INTERVAL_FAST]

    # Set up coordinator
    coordinator = PaxCalimaCoordinator(hass, entry.entry_id, name, mac, pin, scan_interval, scan_interval_fast)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Forward the setup to the platforms.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )

    # Set up options listener
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("Update entry: %s", entry.data[CONF_NAME])
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unload entry: %s", entry.data[CONF_NAME])

    # Make sure we are disconnected
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.disconnect()

    # Unload entries
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    return unload_ok
