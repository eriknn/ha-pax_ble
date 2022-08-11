import logging
import struct
import datetime
import subprocess

from datetime import timedelta

from homeassistant.core import callback
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.const import (TEMP_CELSIUS, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_ILLUMINANCE, STATE_UNKNOWN)

from .const import DOMAIN, CONF_NAME, CONF_MAC, CONF_PIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

OPTIONS = {}

# Creating nested dictionary of key/pairs
OPTIONS = {
    'automatic_cycles': {'0': "Off", '1': "30 min", '2': "60 min", '3': "90 min"},
    'boostmode': {'0': "Off", '1': "Activate"},
    'lightsensorsettings_delayedstart': {'0': "No delay", '5': "5 min", '10': "10 min"},
    'lightsensorsettings_runningtime': {'5': "5 min", '10': "10 min", '15': "15 min", '30': "30 min", '60': "60 min"},
    'off_on': {'0': "Off", '1': "On"},
    'sensitivity': {'0': "Off", '1': "Low sensitivity", '2': "Medium sensitivity", '3': "High sensitivity"}
}
ENTITIES = [
    # Name, displayName, category
    ['automatic_cycles', 'Automatic Cycles', EntityCategory.CONFIG, OPTIONS['automatic_cycles']],
    ['lightsensorsettings_delayedstart', 'LightSensorSettings DelayedStart', EntityCategory.CONFIG, OPTIONS['lightsensorsettings_delayedstart']],
    ['lightsensorsettings_runningtime', 'LightSensorSettings Runningtime', EntityCategory.CONFIG, OPTIONS['lightsensorsettings_runningtime']],
    ['silenthours_on', 'SilentHours On', EntityCategory.CONFIG, OPTIONS['off_on']],
    ['sensitivity_humidity', 'Sensitivity Humidity', EntityCategory.CONFIG, OPTIONS['sensitivity']],
    ['sensitivity_light', 'Sensitivity Light', EntityCategory.CONFIG, OPTIONS['sensitivity']],
    ['trickledays_weekdays', 'TrickleDays Weekdays', EntityCategory.CONFIG, OPTIONS['off_on']],
    ['trickledays_weekends', 'TrickleDays Weekends', EntityCategory.CONFIG, OPTIONS['off_on']],
]

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup selects from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima select")
    
    # Load coordinator and create entities
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_devices([PaxCalimaSelectEntity(coordinator,key,name,ent_cat,options) for [key,name,ent_cat,options] in ENTITIES], True)

class PaxCalimaSelectEntity(CoordinatorEntity, SelectEntity):
    """Representation of a Select."""

    def __init__(self, coordinator, key, name, ent_cat, options):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Generic Entity properties"""
        self._attr_entity_category = ent_cat
        self._attr_name = '{} {}'.format(self.coordinator.calimaApi.name, name)

        """Select Entity properties"""    
        self._options = options

        """Initialize the select."""
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
    def current_option(self):
        try:
            optionIndexStr = self.coordinator.calimaApi.get_data(self._key)
            option = self._options[str(optionIndexStr)]
        except Exception as e:            
            option = "Unknown"
        return option

    @property
    def options(self):
        return list(self._options.values())

    async def async_select_option(self, option):
        """ Save old value """
        oldValue = self.coordinator.calimaApi.get_data(self._key)
        
        """ Find new value """ 
        value = None
        for key, val in self._options.items():
            if val == option:
                value = key
                break

        if value is None:
            return
        
        """ Write new value to our storage """ 
        self.coordinator.calimaApi.set_data(self._key, value)
        
        """ Write value to device """
        ret = await self.coordinator.calimaApi.write_data(self._key)
        
        """ Update HA value """
        if not ret:
            """ Restore value """
            self.coordinator.calimaApi.set_data(self._key, oldValue)
        self.async_schedule_update_ha_state()
