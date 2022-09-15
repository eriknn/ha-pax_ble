import logging
import struct
import datetime
import subprocess

from datetime import timedelta

from homeassistant.core import callback
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.const import TEMP_CELSIUS, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_ILLUMINANCE

from .const import DOMAIN, CONF_NAME, CONF_MAC

_LOGGER = logging.getLogger(__name__)

class Sensor:
    def __init__(self, key, entityName, units, deviceClass, category):
        self.key = key
        self.entityName = entityName
        self.units = units
        self.deviceClass = deviceClass
        self.category = category

SENSOR_TYPES = [
    Sensor('humidity', 'Humidity', '%', DEVICE_CLASS_HUMIDITY, None),
    Sensor('temperature', 'Temperature', TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE, None),
    Sensor('light', 'Light', 'lx', DEVICE_CLASS_ILLUMINANCE, None),
    Sensor('rpm', 'RPM', 'rpm', None, None),
    Sensor('state', 'State', None, None, None),
    Sensor('mode', 'Mode', None, None, EntityCategory.CONFIG),
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup sensors from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima sensors: %s", config_entry.data[CONF_NAME])
    
    # Load coordinator and create entities
    mac = config_entry.data[CONF_MAC]
    coordinator = hass.data[DOMAIN][mac]

    # Create entities
    ha_entities = []
    for sensor in SENSOR_TYPES:
        ha_entities.append(PaxCalimaSensorEntity(coordinator,sensor)) 
    async_add_devices(ha_entities, True)
 
class PaxCalimaSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, sensor):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Generic Entity properties"""
        self._attr_device_class = sensor.deviceClass
        self._attr_entity_category = sensor.category        
        self._attr_name = '{} {}'.format(self.coordinator.calimaApi.name, sensor.entityName)
        self._attr_unique_id = '{}-{}'.format(self.coordinator.calimaApi.mac, self.name)
        self._attr_device_info = {
            "identifiers": { (DOMAIN, self.coordinator.calimaApi.mac) },
            "name": self.coordinator.calimaApi.name,
            "manufacturer": "Pax",
            "model": "Calima"
        }
        
        """Sensor Entity properties"""    
        self._attr_native_unit_of_measurement = sensor.units
        
        """Initialize the sensor."""
        self._key = sensor.key

    @property
    def native_value(self):
        """Return the value of the sensor."""
        return self.coordinator.calimaApi.get_data(self._key)
