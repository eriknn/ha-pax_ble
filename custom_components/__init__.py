"""Support for Pax fans."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from homeassistant.const import CONF_DEVICES
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_NAME,
    CONF_MODEL,
    CONF_MAC,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST
)
from .coordinator import PaxCalimaCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Set up platform from a ConfigEntry."""
    _LOGGER.debug("Setting up configuration for Pax BLE!")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][CONF_DEVICES] = {}

    # Create one coordinator for each device
    for device_id in entry.data[CONF_DEVICES]:
        name = entry.data[CONF_DEVICES][device_id][CONF_NAME]
        model = entry.data[CONF_DEVICES][device_id].get(CONF_MODEL, "Calima")
        mac = entry.data[CONF_DEVICES][device_id][CONF_MAC]
        pin = entry.data[CONF_DEVICES][device_id][CONF_PIN]
        scan_interval = entry.data[CONF_DEVICES][device_id][CONF_SCAN_INTERVAL]
        scan_interval_fast = entry.data[CONF_DEVICES][device_id][CONF_SCAN_INTERVAL_FAST]

        # Create device
        device_registry = dr.async_get(hass)
        dev = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, mac)},
            name=name
        )

        # Set up coordinator
        coordinator = PaxCalimaCoordinator(hass, dev, model, mac, pin, scan_interval, scan_interval_fast)
        hass.data[DOMAIN][CONF_DEVICES][device_id] = coordinator
    
    # Forward the setup to the platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up options listener
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True

# Example migration function
async def async_migrate_entry(hass, config_entry: ConfigEntry):
    if config_entry.version == 1:
        _LOGGER.error("You have an old PAX configuration, please remove and add again. Sorry for the inconvenience!")
        return False

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("Updating Pax BLE entry!")
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Pax BLE entry!")

    # Make sure we are disconnected
    for dev_id, coordinator in hass.data[DOMAIN][CONF_DEVICES].items():
        await coordinator.disconnect()

    # Unload entries
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    return unload_ok

async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove entities and device from HASS"""
    device_id = device_entry.id
    ent_reg = er.async_get(hass)
    reg_entities = {}
    for ent in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if device_id == ent.device_id:
            reg_entities[ent.unique_id] = ent.entity_id
    for entity_id in reg_entities.values():
        ent_reg.async_remove(entity_id)
    dev_reg = dr.async_get(hass)
    dev_reg.async_remove_device(device_id)

    """Remove from config_entry"""
    devices = []
    for dev_id, dev_config in config_entry.data[CONF_DEVICES].items():
        if dev_config[CONF_NAME] == device_entry.name:
            devices.append(dev_config[CONF_MAC])

    new_data = config_entry.data.copy()
    for dev in devices:
        # Remove device from config entry
        new_data[CONF_DEVICES].pop(dev)
    hass.config_entries.async_update_entry(config_entry, data=new_data)
    hass.config_entries._async_schedule_save()

    return True
