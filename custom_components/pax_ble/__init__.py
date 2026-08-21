"""Support for Pax fans."""

import asyncio
import contextlib
import logging

from functools import partial
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from homeassistant.const import CONF_DEVICES
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_NAME,
    CONF_MODEL,
    CONF_MAC,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST,
)
from .helpers import getCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pax BLE from a config entry."""
    _LOGGER.debug("Setting up configuration for Pax BLE!")
    hass.data.setdefault(DOMAIN, {})

    # Set up per-entry data storage
    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id][CONF_DEVICES] = {}

    # Create one coordinator for each device
    coordinators = []
    for device_id in entry.data[CONF_DEVICES]:
        device_data = entry.data[CONF_DEVICES][device_id]
        name = device_data[CONF_NAME]
        mac = device_data[CONF_MAC]

        # Register device
        device_registry = dr.async_get(hass)
        dev = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, mac)},
            name=name
        )

        coordinator = getCoordinator(hass, device_data, dev)
        hass.data[DOMAIN][entry.entry_id][CONF_DEVICES][device_id] = coordinator
        coordinators.append((name, coordinator))

    # Avoid forwarding platforms multiple times
    if not hass.data[DOMAIN][entry.entry_id].get("forwarded"):
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        hass.data[DOMAIN][entry.entry_id]["forwarded"] = True
    else:
        _LOGGER.debug("Platforms already forwarded for entry %s", entry.entry_id)

    # Initial connections run in the background so that setup - and with it
    # Home Assistant startup - is not gated on one serial BLE connection per
    # device (a 10s stagger per device makes that over a minute on a larger
    # installation). Entities are created immediately and fill in as each
    # device is read. The task is stored so that async_unload_entry can cancel
    # it before disconnecting.
    initial_refresh_task = entry.async_create_background_task(
        hass,
        _async_initial_refresh(coordinators),
        name="pax_ble initial refresh",
    )
    hass.data[DOMAIN][entry.entry_id]["initial_refresh_task"] = initial_refresh_task

    # Set up update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Register services (only once across all entries)
    if not hass.services.has_service(DOMAIN, "request_update"):
        hass.services.async_register(DOMAIN, "request_update", partial(service_request_update, hass))

    return True

async def _async_initial_refresh(coordinators):
    """Perform each coordinator's first refresh, one device at a time.

    Serial on purpose: connecting to every device at once on startup can
    exhaust the connection slots of shared BLE proxies, which blocks all
    devices, not just the new ones. The pause between devices keeps the
    proxies free for whichever connection is in flight.
    """
    first_iteration = True
    for name, coordinator in coordinators:
        if not first_iteration:
            await asyncio.sleep(10)
        first_iteration = False

        try:
            # async_refresh() rather than async_request_refresh(): the latter
            # goes through the coordinator's debouncer and can return without
            # having refreshed, which would defeat the one-device-at-a-time
            # pacing this loop exists to provide.
            #
            # No outer timeout. This task is off the setup path, so nothing
            # is waiting on it, and a healthy first refresh can legitimately
            # take well over 30s (the coordinator budgets deviceinfo, config
            # and sensor reads separately, each over a multi-attempt
            # connect). An outer bound would cancel a slow-but-working
            # refresh mid-connect, and nothing on that cancellation path
            # disconnects - the abandoned client could keep holding a proxy
            # connection slot. The coordinator's own per-step timeouts
            # already bound how long this can wait.
            await coordinator.async_refresh()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _LOGGER.warning("Initial connection to %s failed, will retry in background: %s", name, e)


# Service-call to update values
async def service_request_update(hass, call: ServiceCall):
    """Handle the service call to update entities for a specific device."""
    device_id = call.data.get("device_id")
    if not device_id:
        _LOGGER.error("Device ID is required")
        return

    # Get the device entry from the device registry
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if not device_entry:
        _LOGGER.error("No device entry found for device ID %s", device_id)
        return

    # Find the coordinator corresponding to the given device ID
    for entry_data in hass.data.get(DOMAIN, {}).values():
        for coordinator in entry_data.get(CONF_DEVICES, {}).values():
            if coordinator.device_id == device_id:
                await coordinator._async_update_data()
                return

    _LOGGER.warning("No coordinator found for device ID %s", device_id)


# Example migration function
async def async_migrate_entry(hass, config_entry: ConfigEntry):
    if config_entry.version == 1:
        _LOGGER.error(
            "You have an old PAX configuration, please remove and add again. Sorry for the inconvenience!"
        )
        return False

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("Updating Pax BLE entry!")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Pax BLE entry!")

    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})

    # Stop the initial refresh chain before disconnecting. Core runs this
    # function first and only cancels the entry's background tasks afterwards,
    # so without this a reload can disconnect a device while its connect is
    # still in flight.
    initial_refresh_task = entry_data.pop("initial_refresh_task", None)
    if initial_refresh_task is not None and not initial_refresh_task.done():
        initial_refresh_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await initial_refresh_task

    # Make sure we are disconnected
    devices = entry_data.get(CONF_DEVICES, {})
    for dev_id, coordinator in devices.items():
        await coordinator.disconnect()

    # Unload entries
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clear per-entry state so a config-entry reload can forward platforms again
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove entities and device from HASS"""
    device_id = device_entry.id
    ent_reg = er.async_get(hass)
    reg_entities = {}
    for ent in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if device_id == ent.device_id:
            reg_entities[ent.unique_id] = ent.entity_id
    for entity_id in reg_entities.values():
        ent_reg.async_remove(entity_id)
    dev_reg = dr.async_get(hass)
    dev_reg.async_remove_device(device_id)

    """Remove from config_entry"""
    devices = []
    for dev_id, dev_config in config_entry.data[CONF_DEVICES].items():
        if dev_config[CONF_NAME] == device_entry.name:
            devices.append(dev_config[CONF_MAC])

    new_data = config_entry.data.copy()
    for dev in devices:
        # Remove device from config entry
        new_data[CONF_DEVICES].pop(dev)
    hass.config_entries.async_update_entry(config_entry, data=new_data)
    hass.config_entries._async_schedule_save()

    return True
