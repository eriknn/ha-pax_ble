import logging

from collections import namedtuple
from datetime import time
from homeassistant.components.time import TimeEntity
from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, CONF_NAME
from .const import DeviceModel
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

PaxEntity = namedtuple("PaxEntity", ["key", "entityName", "category", "icon"])
CALIMA_ENTITIES = [
    PaxEntity(
        "silenthours_starttime",
        "SilentHours Start Time",
        EntityCategory.CONFIG,
        "mdi:clock-outline",
    ),
    PaxEntity(
        "silenthours_endtime",
        "SilentHours End Time",
        EntityCategory.CONFIG,
        "mdi:clock-outline",
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup switch from a config entry created in the integrations UI."""
    # Create entities
    ha_entities = []

    for device_id in config_entry.data[CONF_DEVICES]:
        _LOGGER.debug(
            "Starting paxcalima times: %s",
            config_entry.data[CONF_DEVICES][device_id][CONF_NAME],
        )

        # Find coordinator for this device
        coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DEVICES][device_id]

        # Device specific entities
        match coordinator._model:
            case (
                DeviceModel.CALIMA.value
                | DeviceModel.SVARA.value
                | DeviceModel.LEVANTE.value
            ):
                for paxentity in CALIMA_ENTITIES:
                    ha_entities.append(PaxCalimaTimeEntity(coordinator, paxentity))
            case DeviceModel.SVENSA.value:
                # Svensa does not support these entities
                pass

    async_add_devices(ha_entities, True)


class PaxCalimaTimeEntity(PaxCalimaEntity, TimeEntity):
    """Representation of a Time."""

    def __init__(self, coordinator, paxentity):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, paxentity)

    @property
    def native_value(self) -> time | None:
        """Return time value."""
        try:
            return self.coordinator.get_data(self._key)
        except:
            return None

    async def async_set_value(self, value: time) -> None:
        """Save old value"""
        old_value = self.coordinator.get_data(self._key)

        """Create new value"""
        new_value = value

        """ Write new value to our storage """
        self.coordinator.set_data(self._key, new_value)

        """ Write value to device """
        if not await self.coordinator.write_data(self._key):
            """Restore value"""
            self.coordinator.set_data(self._key, old_value)

        self.async_schedule_update_ha_state(force_refresh=False)
