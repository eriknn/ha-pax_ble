import datetime as dt
import logging

from collections import namedtuple
from homeassistant.components.text import TextEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, CONF_NAME, CONF_MAC
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

OptionsTuple = namedtuple('options', ['min_chars', 'max_chars', 'pattern'])
OPTIONS = {}
OPTIONS["silenthours"] = OptionsTuple(4, 5, "^([0-1][0-9]|[2][0-3]):([0-5][0-9])$")

PaxEntity = namedtuple('PaxEntity', ['key', 'entityName', 'category', 'icon', 'options'])
ENTITIES = [
    PaxEntity(
        "silenthours_starttime",
        "SilentHours Start Time",
        EntityCategory.CONFIG,
        "mdi:clock-outline",
        OPTIONS["silenthours"],
    ),
    PaxEntity(
        "silenthours_endtime",
        "SilentHours End Time",
        EntityCategory.CONFIG,
        "mdi:clock-outline",
        OPTIONS["silenthours"],
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup texts from a config entry created in the integrations UI."""
    _LOGGER.debug("Starting paxcalima texts: %s", config_entry.data[CONF_NAME])

    # Load coordinator and create entities
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities
    ha_entities = []
    for paxentity in ENTITIES:
        ha_entities.append(PaxCalimaTextEntity(coordinator, paxentity))
    async_add_devices(ha_entities, True)


class PaxCalimaTextEntity(PaxCalimaEntity, TextEntity):
    """Representation of a Text."""

    def __init__(self, coordinator, paxentity):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, paxentity)

        """Text Entity properties"""
        self._attr_native_min = paxentity.options.min_chars
        self._attr_native_max = paxentity.options.max_chars
        self._attr_pattern = paxentity.options.pattern

    @property
    def native_value(self) -> str | None:
        """Return text value."""
        try:
            return self.coordinator.get_data(self._key).strftime("%H:%M")
        except:
            return None

    async def async_set_value(self, value: str) -> None:
        """Save old value"""
        old_value = self.coordinator.get_data(self._key)

        """Create new value"""
        new_value = dt.datetime.strptime(value, "%H:%M").time()

        """ Write new value to our storage if changed """
        """ This is to avaid double writes which happens at least on iOS """
        if new_value != old_value:
            self.coordinator.set_data(self._key, new_value)
        else:
            return

        """ Write value to device """
        if not await self.coordinator.write_data(self._key):
            """Restore value"""
            self.coordinator.set_data(self._key, old_value)

        self.async_schedule_update_ha_state(force_refresh=False)
