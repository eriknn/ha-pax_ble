import logging
import struct
import datetime
import subprocess

from datetime import timedelta

from homeassistant.core import callback
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.const import TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE

from .const import DOMAIN, CONF_NAME, CONF_MAC

_LOGGER = logging.getLogger(__name__)

DT_INTEGER = 0
DT_FLOAT = 1
DT_UNKNOWN = 10

# Writetype - Local will not send data to device.
WT_REMOTE = 0
WT_LOCAL = 1

OPTIONS = {}
#OPTIONS['key'] = [MaxValue, MinValue, Step, Datatype]
OPTIONS['fanspeed'] = [2400, 0, 1, DT_INTEGER]
OPTIONS['boostmodespeed'] = [2400, 1000, 1, DT_INTEGER]
OPTIONS['boostmodesec'] = [3600, 60, 1, DT_INTEGER]
OPTIONS['hour'] = [23, 0, 1, DT_INTEGER]
OPTIONS['min'] = [59, 0, 1, DT_INTEGER]

class Sensor:
    def __init__(self, key, entityName, units, deviceClass, category, options, writeType):
        self.key = key
        self.entityName = entityName
        self.units = units
        self.deviceClass = deviceClass
        self.category = category
        self.options = options
        self.writeType = writeType

SENSOR_TYPES = [
    Sensor('fanspeed_humidity', 'Fanspeed Humidity', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('fanspeed_light', 'Fanspeed Light', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('fanspeed_trickle', 'Fanspeed Trickle', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('boostmodespeed', 'BoostMode Speed', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_LOCAL),
    Sensor('boostmodesec', 'BoostMode Time', 's', None, EntityCategory.CONFIG, OPTIONS['boostmodesec'], WT_LOCAL),
    Sensor('heatdistributorsettings_temperaturelimit', 'HeatDistributorSettings TemperatureLimit', TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('heatdistributorsettings_fanspeedbelow', 'HeatDistributorSettings FanSpeedBelow', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('heatdistributorsettings_fanspeedabove', 'HeatDistributorSettings FanSpeedAbove', 'rpm', None, EntityCategory.CONFIG, OPTIONS['fanspeed'], WT_REMOTE),
    Sensor('silenthours_startinghour', 'SilentHours StartingHour', 'H', None, EntityCategory.CONFIG, OPTIONS['hour'], WT_REMOTE),
    Sensor('silenthours_startingminute', 'SilentHours StartingMinute', 'Min', None, EntityCategory.CONFIG, OPTIONS['min'], WT_REMOTE),
    Sensor('silenthours_endinghour', 'SilentHours EndingHour', 'H', None, EntityCategory.CONFIG, OPTIONS['hour'], WT_REMOTE),
    Sensor('silenthours_endingminute', 'SilentHours EndingMinute', 'Min', None, EntityCategory.CONFIG, OPTIONS['min'], WT_REMOTE),
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup sensors from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima numbers: %s", config_entry.data[CONF_NAME])

    # Load coordinator and create entities
    mac = config_entry.data[CONF_MAC]
    coordinator = hass.data[DOMAIN][mac]

    # Create entities
    ha_entities = []
    for sensor in SENSOR_TYPES:
        ha_entities.append(PaxCalimaNumberEntity(coordinator,sensor))
    async_add_devices(ha_entities, True)

class PaxCalimaNumberEntity(CoordinatorEntity, NumberEntity):
    """Representation of a Number."""

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
        self._attr_mode = "box"
        self._attr_native_max_value = sensor.options[0]
        self._attr_native_min_value = sensor.options[1]
        self._attr_native_step = sensor.options[2]
        self._datatype = sensor.options[3]
        self._write_type = sensor.writeType
        self._attr_native_unit_of_measurement = sensor.units

        """Initialize the number."""
        self._key = sensor.key

    @property
    def native_value(self):
        """ Return number value. """
        retVal = self.coordinator.calimaApi.get_data(self._key)
        
        if self._datatype == DT_INTEGER:
            try:
                retVal = int(retVal)
            except:
                pass
        return retVal

    async def async_set_native_value(self, value):
        if self._write_type == WT_LOCAL:
            self.coordinator.calimaApi.set_data(self._key, value)
        else: 
            """ Save old value """
            oldValue = self.coordinator.calimaApi.get_data(self._key)
                
            """ Write new value to our storage """
            if self._datatype == DT_INTEGER:
                try:
                    value = int(value)
                except:
                    pass
            self.coordinator.calimaApi.set_data(self._key, value)

            """ Write value to device """
            ret = await self.coordinator.calimaApi.write_data(self._key)
                
            """ Update HA value """
            if not ret:
                """ Restore value """
                self.coordinator.calimaApi.set_data(self._key, oldValue)
        self.async_schedule_update_ha_state()
