"""Base entity class for Pax Calima integration."""
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PaxCalimaEntity(CoordinatorEntity):
    """Pax Calima base entity class."""

    def __init__(self, coordinator, paxentity):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Generic Entity properties"""
        self._attr_entity_category = paxentity.category
        self._attr_icon = paxentity.icon
        self._attr_name = "{} {}".format(self.coordinator.devicename, paxentity.entityName)
        self._attr_unique_id = "{}-{}".format(self.coordinator.mac, self.name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.coordinator.mac)},
        }
        self._extra_state_attributes = {}
        
        """Store this entities key."""
        self._key = paxentity.key

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_state_attributes        
