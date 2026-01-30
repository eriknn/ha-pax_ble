import logging

from collections import namedtuple
from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import CONF_DEVICES
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.const import REVOLUTIONS_PER_MINUTE
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, CONF_NAME
from .const import DeviceModel
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

OptionsTuple = namedtuple("options", ["min_value", "max_value", "step"])
OPTIONS = {}
OPTIONS["fanspeed"] = OptionsTuple(800, 2400, 25)
OPTIONS["temperature"] = OptionsTuple(5, 50, 1)
OPTIONS["boostmodesec"] = OptionsTuple(60, 900, 1)
OPTIONS["boostmodespeed"] = OptionsTuple(1000, 2400, 25)

PaxEntity = namedtuple(
    "PaxEntity",
    ["key", "entityName", "units", "deviceClass", "category", "icon", "options"],
)
ENTITIES = [
    PaxEntity(
        "fanspeed_humidity",
        "Fanspeed Humidity",
        REVOLUTIONS_PER_MINUTE,
        None,
        EntityCategory.CONFIG,
        "mdi:engine",
        OPTIONS["fanspeed"],
    ),
    PaxEntity(
        "fanspeed_trickle",
        "Fanspeed Trickle",
        REVOLUTIONS_PER_MINUTE,
        None,
        EntityCategory.CONFIG,
        "mdi:engine",
        OPTIONS["fanspeed"],
    ),
]
CALIMA_ENTITIES = [
    PaxEntity(
        "heatdistributorsettings_temperaturelimit",
        "HeatDistributorSettings TemperatureLimit",
        UnitOfTemperature.CELSIUS,
        NumberDeviceClass.TEMPERATURE,
        EntityCategory.CONFIG,
        None,
        OPTIONS["temperature"],
    ),
    PaxEntity(
        "heatdistributorsettings_fanspeedbelow",
        "HeatDistributorSettings FanSpeedBelow",
        REVOLUTIONS_PER_MINUTE,
        None,
        EntityCategory.CONFIG,
        "mdi:engine",
        OPTIONS["fanspeed"],
    ),
    PaxEntity(
        "heatdistributorsettings_fanspeedabove",
        "HeatDistributorSettings FanSpeedAbove",
        REVOLUTIONS_PER_MINUTE,
        None,
        EntityCategory.CONFIG,
        "mdi:engine",
        OPTIONS["fanspeed"],
    ),
    PaxEntity(
        "fanspeed_light",
        "Fanspeed Light",
        REVOLUTIONS_PER_MINUTE,
        None,
        EntityCategory.CONFIG,
        "mdi:engine",
        OPTIONS["fanspeed"],
    ),
]
SVENSA_ENTITIES = [
    PaxEntity(
        "fanspeed_airing",
        "Fanspeed Airing",
        REVOLUTIONS_PER_MINUTE,
        None,
        EntityCategory.CONFIG,
        "mdi:engine",
        OPTIONS["fanspeed"],
    ),
    PaxEntity(
        "fanspeed_sensor",
        "Fanspeed Sensor",
        REVOLUTIONS_PER_MINUTE,
        None,
        EntityCategory.CONFIG,
        "mdi:engine",
        OPTIONS["fanspeed"],
    ),
]
RESTOREENTITIES = [
    PaxEntity(
        "boostmodesecwrite",
        "BoostMode Time",
        UnitOfTime.SECONDS,
        None,
        EntityCategory.CONFIG,
        "mdi:timer-outline",
        OPTIONS["boostmodesec"],
    ),
    PaxEntity(
        "boostmodespeedwrite",
        "BoostMode Speed",
        REVOLUTIONS_PER_MINUTE,
        None,
        EntityCategory.CONFIG,
        "mdi:engine",
        OPTIONS["boostmodespeed"],
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup numbers from a config entry created in the integrations UI."""
    # Create entities
    ha_entities = []

    for device_id in config_entry.data[CONF_DEVICES]:
        _LOGGER.debug(
            "Starting paxcalima numbers: %s",
            config_entry.data[CONF_DEVICES][device_id][CONF_NAME],
        )

        # Find coordinator for this device
        coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DEVICES][device_id]

        # Create entities for this device
        for paxentity in ENTITIES:
            ha_entities.append(PaxCalimaNumberEntity(coordinator, paxentity))

        # Device specific entities
        match coordinator._model:
            case (
                DeviceModel.CALIMA.value
                | DeviceModel.SVARA.value
                | DeviceModel.LEVANTE.value
            ):
                for paxentity in CALIMA_ENTITIES:
                    ha_entities.append(PaxCalimaNumberEntity(coordinator, paxentity))
            case DeviceModel.SVENSA.value:
                for paxentity in SVENSA_ENTITIES:
                    ha_entities.append(PaxCalimaNumberEntity(coordinator, paxentity))

        # Entities with local datas
        for paxentity in RESTOREENTITIES:
            ha_entities.append(PaxCalimaRestoreNumberEntity(coordinator, paxentity))

    async_add_devices(ha_entities, True)


class PaxCalimaNumberEntity(PaxCalimaEntity, NumberEntity):
    """Representation of a Number."""

    def __init__(self, coordinator, paxentity):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, paxentity)

        """Number Entity properties"""
        self._attr_device_class = paxentity.deviceClass
        self._attr_mode = "box"
        self._attr_native_min_value = paxentity.options.min_value
        self._attr_native_max_value = paxentity.options.max_value
        self._attr_native_step = paxentity.options.step
        self._attr_native_unit_of_measurement = paxentity.units

    @property
    def native_value(self) -> float | None:
        """Return number value."""
        try:
            return int(self.coordinator.get_data(self._key))
        except:
            return None

    async def async_set_native_value(self, value):
        """Save old value"""
        old_value = self.coordinator.get_data(self._key)

        """ Write new value to our storage """
        self.coordinator.set_data(self._key, int(value))

        """ Write value to device """
        if not await self.coordinator.write_data(self._key):
            """Restore value"""
            self.coordinator.set_data(self._key, old_value)

        self.async_schedule_update_ha_state(force_refresh=False)


class PaxCalimaRestoreNumberEntity(PaxCalimaNumberEntity, RestoreEntity):
    """Representation of a Number with restore ability (and only local storage)."""

    def __init__(self, coordinator, paxentity):
        super().__init__(coordinator, paxentity)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()

        if (last_state is not None) and (
            last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            self.coordinator.set_data(self._key, last_state.state)

    async def async_set_native_value(self, value):
        self.coordinator.set_data(self._key, int(value))
        self.async_schedule_update_ha_state(force_refresh=False)
