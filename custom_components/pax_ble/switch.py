import logging
import struct
import datetime
import subprocess

from homeassistant.core import callback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_NAME, CONF_MAC

_LOGGER = logging.getLogger(__name__)

class Sensor:
    def __init__(self, key, entityName, category):
        self.key = key

        self.entityName = entityName
        self.category = category

SENSOR_TYPES = [
    Sensor('boostmode', 'BoostMode', None),
    Sensor('silenthours_on', 'SilentHours On', EntityCategory.CONFIG),
    Sensor('trickledays_weekdays', 'TrickleDays Weekdays', EntityCategory.CONFIG),
    Sensor('trickledays_weekends', 'TrickleDays Weekends', EntityCategory.CONFIG)    
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup switch from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima switches: %s", config_entry.data[CONF_NAME])

    # Load coordinator and create entities
    mac = config_entry.data[CONF_MAC]
    coordinator = hass.data[DOMAIN][mac]

    # Create entities
    ha_entities = []
    for sensor in SENSOR_TYPES:
        ha_entities.append(PaxCalimaSwitchEntity(coordinator,sensor))
    async_add_devices(ha_entities, True)

class PaxCalimaSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Representation of a Command."""

    def __init__(self, coordinator, sensor):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Generic Entity properties"""
        self._attr_entity_category = sensor.category
        self._attr_name = '{} {}'.format(self.coordinator.calimaApi.name, sensor.entityName)
        self._attr_unique_id = '{}-{}'.format(self.coordinator.calimaApi.mac, self.name)
        self._attr_device_info = {
            "identifiers": { (DOMAIN, self.coordinator.calimaApi.mac) },
            "name": self.coordinator.calimaApi.name,
            "manufacturer": "Pax",
            "model": "Calima"
        }
            
        """Initialize the sensor."""
        self._key = sensor.key
    
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
