import logging

from collections import namedtuple
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, CONF_NAME
from .const import DeviceModel
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

# Creating nested dictionary of key/pairs
OPTIONS = {
    "airing": {
        "0": "Off",
        "30": "30 min",
        "60": "60 min",
        "90": "90 min",
        "120": "120 min",
    },
    "automatic_cycles": {"0": "Off", "1": "30 min", "2": "60 min", "3": "90 min"},
    "lightsensorsettings_delayedstart": {"0": "No delay", "5": "5 min", "10": "10 min"},
    "lightsensorsettings_runningtime": {
        "5": "5 min",
        "10": "10 min",
        "15": "15 min",
        "30": "30 min",
        "60": "60 min",
    },
    "sensitivity": {
        "0": "Off",
        "1": "Low sensitivity",
        "2": "Medium sensitivity",
        "3": "High sensitivity",
    },
    "timer_delay": {
        "0": "Off",
        "2": "2 min",
        "4": "4 min",
    },
    "pausemin": {
        "30": "30 min",
        "60": "60 min", # Default.
        "90": "90 min",
        "120": "120 min",
    },
}

PaxEntity = namedtuple(
    "PaxEntity", ["key", "entityName", "category", "icon", "options"]
)
ENTITIES = [
    PaxEntity(
        "sensitivity_humidity",
        "Sensitivity Humidity",
        EntityCategory.CONFIG,
        "mdi:water-percent",
        OPTIONS["sensitivity"],
    ),
]
CALIMA_ENTITIES = [
    PaxEntity(
        "automatic_cycles",
        "Automatic Cycles",
        EntityCategory.CONFIG,
        "mdi:fan-auto",
        OPTIONS["automatic_cycles"],
    ),
    PaxEntity(
        "sensitivity_light",
        "Sensitivity Light",
        EntityCategory.CONFIG,
        "mdi:brightness-5",
        OPTIONS["sensitivity"],
    ),
    PaxEntity(
        "lightsensorsettings_delayedstart",
        "LightSensorSettings DelayedStart",
        EntityCategory.CONFIG,
        "mdi:timer-outline",
        OPTIONS["lightsensorsettings_delayedstart"],
    ),
    PaxEntity(
        "lightsensorsettings_runningtime",
        "LightSensorSettings Runningtime",
        EntityCategory.CONFIG,
        "mdi:timer-outline",
        OPTIONS["lightsensorsettings_runningtime"],
    ),
]
SVENSA_ENTITIES = [
    PaxEntity(
        "airing", "Airing", EntityCategory.CONFIG, "mdi:fan-auto", OPTIONS["airing"]
    ),
    PaxEntity(
        "sensitivity_presence",
        "Sensitivity Presence",
        EntityCategory.CONFIG,
        "mdi:brightness-5",
        OPTIONS["sensitivity"],
    ),
    PaxEntity(
        "sensitivity_gas",
        "Sensitivity Gas",
        EntityCategory.CONFIG,
        "mdi:molecule",
        OPTIONS["sensitivity"],
    ),
    PaxEntity(
        "timer_runtime",
        "Timer Runtime",
        EntityCategory.CONFIG,
        "mdi:timer-outline",
        OPTIONS["lightsensorsettings_runningtime"],
    ),
    PaxEntity(
        "timer_delay",
        "Timer Delay",
        EntityCategory.CONFIG,
        "mdi:timer-outline",
        OPTIONS["timer_delay"],
    ),
    PaxEntity(
        "pausemin",
        "Pause Time",
        EntityCategory.CONFIG,
        "mdi:pause-circle-outline",
        OPTIONS["pausemin"],
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup selects from a config entry created in the integrations UI."""
    # Create entities
    ha_entities = []

    for device_id in config_entry.data[CONF_DEVICES]:
        _LOGGER.debug(
            "Starting paxcalima selects: %s",
            config_entry.data[CONF_DEVICES][device_id][CONF_NAME],
        )

        # Find coordinator for this device
        coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DEVICES][device_id]

        # Create entities for this device
        for paxentity in ENTITIES:
            ha_entities.append(PaxCalimaSelectEntity(coordinator, paxentity))

        # Device specific entities
        match coordinator._model:
            case DeviceModel.CALIMA.value:
                for paxentity in CALIMA_ENTITIES:
                    ha_entities.append(PaxCalimaSelectEntity(coordinator, paxentity))
            case DeviceModel.LEVANTE.value:
                for paxentity in CALIMA_ENTITIES:
                    ha_entities.append(PaxCalimaSelectEntity(coordinator, paxentity))
            case DeviceModel.SVENSA.value:
                for paxentity in SVENSA_ENTITIES:
                    ha_entities.append(PaxCalimaSelectEntity(coordinator, paxentity))

    async_add_devices(ha_entities, True)


class PaxCalimaSelectEntity(PaxCalimaEntity, SelectEntity):
    """Representation of a Select."""

    def __init__(self, coordinator, paxentity):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, paxentity)

        """Select Entity properties"""
        self._options = paxentity.options

    @property
    def current_option(self):
        try:
            optionIndexStr = self.coordinator.get_data(self._key)
            option = self._options[str(optionIndexStr)]
        except Exception as e:
            option = "Unknown"
        return option

    @property
    def options(self):
        return list(self._options.values())

    async def async_select_option(self, option):
        """Save old value"""
        old_value = self.coordinator.get_data(self._key)

        """ Find new value """
        value = None
        for key, val in self._options.items():
            if val == option:
                value = key
                break

        if value is None:
            return

        """ Write new value to our storage """
        self.coordinator.set_data(self._key, value)

        """ Write value to device """
        ret = await self.coordinator.write_data(self._key)

        """ Update HA value """
        if not ret:
            """Restore value"""
            self.coordinator.set_data(self._key, old_value)
        self.async_schedule_update_ha_state(force_refresh=False)


# type: ignore
