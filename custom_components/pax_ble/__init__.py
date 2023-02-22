"""Support for Pax fans."""
import logging
import async_timeout

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, PLATFORMS, CONF_NAME, CONF_MAC, CONF_PIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .CalimaApi import CalimaApi
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
    
async def async_setup_entry(hass, config_entry):   
    # Set up platform from a ConfigEntry."""
    _LOGGER.debug("Setting up entry: %s", config_entry.data[CONF_NAME]) 
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.data
    
    # Load config data    
    name = config_entry.data[CONF_NAME]
    mac = config_entry.data[CONF_MAC]
    pin = config_entry.data[CONF_PIN]
    scan_interval = config_entry.data[CONF_SCAN_INTERVAL]

    # Set up shared api and coordinator
    calimaApi = CalimaApi(hass, name, mac, pin)                                     
    coordinator = PaxUpdateCoordinator(hass, calimaApi, scan_interval)
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    # Load initial data (model name etc)
    try:
        async with async_timeout.timeout(10):
            await calimaApi.read_deviceinfo()     
    except Exception as err:
        _LOGGER.debug("Failed when loading initdata: " + err)

    # Forward the setup to the platforms.
    hass.async_create_task(hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS))

    # Set up options listener
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener)) 

    return True

async def update_listener(hass, config_entry):
    _LOGGER.debug("Update entry: %s", config_entry.data[CONF_NAME]) 
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    _LOGGER.debug("Unload entry: %s", config_entry.data[CONF_NAME]) 
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    return unload_ok

class PaxUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, calimaApi, scanInterval):
        """ Initialize my coordinator. """
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Pax Calima",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=scanInterval),
        )       
        self.calimaApi = calimaApi


    async def _async_update_data(self):       
        """ Fetch data from device. """
        try:
            async with async_timeout.timeout(30):
                return await self.calimaApi.async_fetch_data()
        except Exception as err:
                return False
