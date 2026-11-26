import logging

from collections import namedtuple
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, CONF_NAME
from .const import DeviceModel
from .entity import PaxCalimaEntity

_LOGGER = logging.getLogger(__name__)

PaxAttribute = namedtuple("PaxAttribute", ["key", "descriptor", "unit"])
boostmode_attribute = PaxAttribute("boostmodesecread", "Boost time remaining", " s")
pause_attribute = PaxAttribute("pausesecread", "Pause time remaining", " s")

PaxEntity = namedtuple(
    "PaxEntity", ["key", "entityName", "category", "icon", "attributes"]
)
ENTITIES = [
    PaxEntity("boostmode", "BoostMode", None, "mdi:wind-power", boostmode_attribute),
]
CALIMA_ENTITIES = [
    PaxEntity("pause", "Pause", None, "mdi:pause", pause_attribute),
    PaxEntity(
        "trickledays_weekdays",
        "TrickleDays Weekdays",
        EntityCategory.CONFIG,
        "mdi:calendar",
        None,
    ),
    PaxEntity(
        "trickledays_weekends",
        "TrickleDays Weekends",
        EntityCategory.CONFIG,
        "mdi:calendar",
        None,
    ),
    PaxEntity(
        "silenthours_on",
        "SilentHours On",
        EntityCategory.CONFIG,
        "mdi:volume-off",
        None,
    ),
]
# Keeps the fan stopped until turned off again; see long_stop.py.
LONG_STOP_ENTITY = PaxEntity("long_stop", "Stop", None, "mdi:fan-off", None)
LONG_STOP_SAVED_ATTRIBUTE = "saved_settings"

SVENSA_ENTITIES = [
    PaxEntity(
        "trickle_on", "Trickle On", EntityCategory.CONFIG, "mdi:volume-off", None
    ),
    PaxEntity(
        "pause", "Pause", None, "mdi:pause", None
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Setup switch from a config entry created in the integrations UI."""
    # Create entities
    ha_entities = []

    for device_id in config_entry.data[CONF_DEVICES]:
        _LOGGER.debug(
            "Starting paxcalima switches: %s",
            config_entry.data[CONF_DEVICES][device_id][CONF_NAME],
        )

        # Find coordinator for this device
        coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DEVICES][device_id]

        # Create entities for this device
        for paxentity in ENTITIES:
            ha_entities.append(PaxCalimaSwitchEntity(coordinator, paxentity))

        # Device specific entities
        match coordinator._model:
            case (
                DeviceModel.CALIMA.value
                | DeviceModel.SVARA.value
                | DeviceModel.LEVANTE.value
            ):
                for paxentity in CALIMA_ENTITIES:
                    ha_entities.append(PaxCalimaSwitchEntity(coordinator, paxentity))
                ha_entities.append(PaxLongStopSwitchEntity(coordinator, LONG_STOP_ENTITY))
            case DeviceModel.SVENSA.value:
                for paxentity in SVENSA_ENTITIES:
                    ha_entities.append(PaxCalimaSwitchEntity(coordinator, paxentity))

    # No update_before_add - see sensor.py: pre-add updates would run the
    # first BLE connection inside platform setup and block startup.
    async_add_devices(ha_entities, False)


class PaxCalimaSwitchEntity(PaxCalimaEntity, SwitchEntity):
    """Representation of a Switch."""

    def __init__(self, coordinator, paxentity):
        """Pass coordinator to PaxCalimaEntity."""
        super().__init__(coordinator, paxentity)
        self._paxattr = paxentity.attributes

    @property
    def is_on(self):
        """Return the state of the switch."""
        return self.coordinator.get_data(self._key)

    @property
    def extra_state_attributes(self):
        if self._paxattr is not None:
            """Return entity specific state attributes."""
            descriptor = self._paxattr.descriptor
            key = self.coordinator.get_data(self._paxattr.key)
            unit = self._paxattr.unit
            attrs = {descriptor: str(key) + unit}
            attrs.update(super().extra_state_attributes)
            return attrs
        else:
            return None

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug("Enabling %s", self._attr_name)
        await self.writeVal(1)

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug("Disabling %s", self._attr_name)
        await self.writeVal(0)

    async def writeVal(self, val):
        """Save old value"""
        old_value = self.coordinator.get_data(self._key)

        """Write new value to our storage"""
        self.coordinator.set_data(self._key, val)

        """ Write value to device """
        ret = await self.coordinator.write_data(self._key)

        """ Update HA value """
        if not ret:
            """Restore value"""
            self.coordinator.set_data(self._key, old_value)
        self.async_schedule_update_ha_state(force_refresh=False)


class PaxLongStopSwitchEntity(PaxCalimaEntity, SwitchEntity, RestoreEntity):
    """Keeps the fan stopped until turned off, then restores its settings."""

    def __init__(self, coordinator, paxentity):
        super().__init__(coordinator, paxentity)
        self._busy = False

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state == "on":
            self.coordinator.restore_long_stop(
                last_state.attributes.get(LONG_STOP_SAVED_ATTRIBUTE)
            )

    @property
    def is_on(self):
        return bool(self.coordinator.get_data(self._key))

    @property
    def icon(self):
        # Starting or ending a stop takes several BLE writes; show that the
        # tap was taken rather than leave the switch looking unchanged.
        if self._busy:
            return "mdi:timer-sand"
        return "mdi:fan-off" if self.is_on else "mdi:fan"

    @property
    def extra_state_attributes(self):
        # Kept as an attribute so the stop survives a restart.
        saved = self.coordinator.get_data("long_stop_saved")
        return {LONG_STOP_SAVED_ATTRIBUTE: saved} if saved else None

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)

    async def _set(self, on):
        # Ignore taps while a stop or resume is still being written.
        if self._busy:
            _LOGGER.debug("%s is busy, ignoring", self._attr_name)
            return
        self._busy = True
        self.async_write_ha_state()
        try:
            _LOGGER.debug("%s %s", "Starting" if on else "Ending", self._attr_name)
            await self.coordinator.set_long_stop(on)
        finally:
            self._busy = False
            self.async_write_ha_state()
