import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from homeassistant.components.sensor import SensorDeviceClass

from homeassistant.const import UnitOfVolumeFlowRate, UnitOfTemperature
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
)

from .const import DOMAIN, CONF_NAME, CONF_MAC
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)


class Sensor:
    def __init__(self, key, entityName, units, deviceClass, category):
        self.key = key
        self.entityName = entityName
        self.units = units
        self.deviceClass = deviceClass
        self.category = category


SENSOR_TYPES = [
    Sensor("humidity", "Humidity", PERCENTAGE, SensorDeviceClass.HUMIDITY, None),
    Sensor("temperature", "Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, None),
    Sensor("light", "Light", LIGHT_LUX, SensorDeviceClass.ILLUMINANCE, None),
    Sensor("rpm", "RPM", REVOLUTIONS_PER_MINUTE, None, None),
    Sensor("flow", "Flow", UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, None, None),
    Sensor("state", "State", None, None, None),
    Sensor("mode", "Mode", None, None, EntityCategory.CONFIG),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup sensors from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima sensors: %s", config_entry.data[CONF_NAME])

    # Load coordinator and create entities
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities
    ha_entities = []
    for sensor in SENSOR_TYPES:
        ha_entities.append(PaxCalimaSensorEntity(coordinator, sensor))
    async_add_devices(ha_entities, True)


class PaxCalimaSensorEntity(PaxCalimaEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, sensor):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, sensor)

        """Sensor Entity properties"""
        self._attr_device_class = sensor.deviceClass
        self._attr_native_unit_of_measurement = sensor.units

    @property
    def native_value(self):
        """Return the value of the sensor."""
        return self.coordinator.get_data(self._key)
