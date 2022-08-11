import logging
import struct
import datetime
import subprocess

from homeassistant.core import callback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.util import Throttle

from .const import DOMAIN, CONF_NAME, CONF_MAC, CONF_PIN

_LOGGER = logging.getLogger(__name__)

ENTITIES = [
    ['boostmode', 'BoostMode'],
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup switch from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima switch")

    # Load coordinator and create entities
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_devices([ PaxCalimaSwitchEntity(coordinator, key, name) for [key, name] in ENTITIES], True)

class PaxCalimaSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Representation of a Command."""

    def __init__(self, coordinator, key, name):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Generic Entity properties"""   
        self._attr_name = '{} {}'.format(self.coordinator.calimaApi.name, name)
        
        """Initialize the sensor."""
        self._key = key

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
        
    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self.coordinator.calimaApi.mac)
            },
            "name": self.coordinator.calimaApi.name,
            "manufacturer": "Pax",
            "model": "Calima"
        }
    
    @property
    def unique_id(self):
        return '{}-{}'.format(self.coordinator.calimaApi.mac, self.name)
    
    @property
    def is_on(self):
        """Return the state of the switch."""
        return self.coordinator.calimaApi.get_data(self._key)
    
    async def async_turn_on(self, **kwargs):
        _LOGGER.debug('Enabling Boost Mode')
        
        """ Write new value to our storage """ 
        self.coordinator.calimaApi.set_data(self._key, 1)
        
        """ Write value to device """
        ret = await self.coordinator.calimaApi.write_data(self._key)
        
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug('Disabling Boost Mode')
        
        """ Write new value to our storage """ 
        self.coordinator.calimaApi.set_data(self._key, 0)
        
        """ Write value to device """
        ret = await self.coordinator.calimaApi.write_data(self._key)
        
        self.async_schedule_update_ha_state()
