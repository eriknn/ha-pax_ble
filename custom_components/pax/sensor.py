import logging
import struct
import datetime
import subprocess

from datetime import timedelta

from homeassistant.core import callback
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.const import (TEMP_CELSIUS, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_ILLUMINANCE, STATE_UNKNOWN)

from .const import DOMAIN, CONF_NAME, CONF_MAC, CONF_PIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = [
    # Name, displayName, units, deviceClass, category
    ['humidity', 'Humidity', '%', DEVICE_CLASS_HUMIDITY, None],
    ['temperature', 'Temperature', TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE, None],
    ['light', 'Light', 'lx', DEVICE_CLASS_ILLUMINANCE, None],
    ['rpm', 'RPM', 'rpm', None, None],
    ['state', 'State', None, None, None],
    ['mode', 'Mode', None, None, EntityCategory.CONFIG],
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup sensors from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima sensor")
    
    # Load coordinator and create entities
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_devices([PaxCalimaSensorEntity(coordinator,key,name,unit,device_class, ent_cat) for [key, name, unit, device_class, ent_cat] in SENSOR_TYPES], True)
 
class PaxCalimaSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, key, name, unit, device_class, ent_cat):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Generic Entity properties"""
        self._attr_device_class = device_class
        self._attr_entity_category = ent_cat        
        self._attr_name = '{} {}'.format(self.coordinator.calimaApi.name, name)

        """Sensor Entity properties"""    
        self._attr_native_unit_of_measurement = unit
        
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
    def native_value(self):
        """Return the value of the sensor."""
        return self.coordinator.calimaApi.get_data(self._key)
