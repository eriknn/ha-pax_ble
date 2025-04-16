import asyncio
import async_timeout
import datetime as dt
import logging

from abc import ABC, abstractmethod
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from typing import Optional

from .devices.base_device import BaseDevice

_LOGGER = logging.getLogger(__name__)

class BaseCoordinator(DataUpdateCoordinator, ABC):
    _fast_poll_enabled = False
    _fast_poll_count = 0
    _normal_poll_interval = 60
    _fast_poll_interval = 10

    _deviceInfoLoaded = False
    _last_config_timestamp = None

    # Should be set by a child class
    _fan: Optional[BaseDevice] = None  # This is basically a type hint

    def __init__(self, hass, device:DeviceEntry, model:str, mac:str, pin:int, scan_interval:int, scan_interval_fast:int):
        """Initialize coordinator parent"""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=model + ": " + device.name,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=dt.timedelta(seconds=scan_interval),
        )

        self._normal_poll_interval = scan_interval
        self._fast_poll_interval = scan_interval_fast

        self._device = device
        self._model = model

        # Initialize state in case of new integration
        self._state = {}
        self._state["boostmodespeedwrite"] = 2400
        self._state["boostmodesecwrite"] = 600

    @property
    def device_id(self):
        return self._device.id

    @property
    def devicename(self):
        return self._device.name

    @property
    def identifiers(self):
        return self._device.identifiers

    def setFastPollMode(self):
        _LOGGER.debug("Enabling fast poll mode")
        self._fast_poll_enabled = True
        self._fast_poll_count = 0
        self.update_interval = dt.timedelta(seconds=self._fast_poll_interval)
        self._schedule_refresh()

    def setNormalPollMode(self):
        _LOGGER.debug("Enabling normal poll mode")
        self._fast_poll_enabled = False
        self.update_interval = dt.timedelta(seconds=self._normal_poll_interval)

    async def disconnect(self):
        await self._fan.disconnect()

    async def _safe_connect(self) -> bool:
        """
        Try up to 5× with exponential backoff.
        """
        backoff = 1.0
        for attempt in range(1, 6):
            if await self._fan.connect():
                return True
            _LOGGER.debug("Coordinator connect attempt %d failed", attempt)
            if attempt < 5:
                await asyncio.sleep(backoff)
                backoff *= 2
        _LOGGER.warning("Coordinator failed to connect after 5 attempts")
        return False

    async def _async_update_data(self):
        _LOGGER.debug("Coordinator updating data!!")

        """ Counter for fast polling """
        self._update_poll_counter()

        """ Fetch device info if not already fetched """
        if not self._deviceInfoLoaded:
            try:
                async with async_timeout.timeout(20):
                    if await self.read_deviceinfo(disconnect=False):
                        await self._async_update_device_info()
                        self._deviceInfoLoaded = True
            except Exception as err:
                _LOGGER.debug("Failed when loading device information: %s", str(err))

        """ Fetch config data if we have no/old values """
        if  dt.datetime.now().date() != self._last_config_timestamp:
            try:
                async with async_timeout.timeout(20):
                    if await self.read_configdata(disconnect=False):
                        self._last_config_timestamp = dt.datetime.now().date()
            except Exception as err:
                _LOGGER.debug("Failed when loading config data: %s", str(err))

        """ Fetch sensor data """
        try:
            async with async_timeout.timeout(20):
                await self.read_sensordata(disconnect=not self._fast_poll_enabled)
        except Exception as err:
            _LOGGER.debug("Failed when fetching sensordata: %s", str(err))

    async def _async_update_device_info(self) -> None:
        device_registry = dr.async_get(self.hass)
        device_registry.async_update_device(
            self.device_id,
            manufacturer=self.get_data("manufacturer"),
            model=self.get_data("model"),
            hw_version=self.get_data("hw_rev"),
            sw_version=self.get_data("sw_rev"),
        )
        _LOGGER.debug("Updated device data for: %s", self.devicename)

    def _update_poll_counter(self):
        if self._fast_poll_enabled:
            self._fast_poll_count += 1
            if self._fast_poll_count > 10:
                self.setNormalPollMode()

    def get_data(self, key):
        if key in self._state:
            return self._state[key]
        return None

    def set_data(self, key, value):
        _LOGGER.debug("Set_Data: %s %s", key, value)
        self._state[key] = value

    async def read_deviceinfo(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading device information")
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                raise Exception("Not connected!")
        except Exception as e:
            _LOGGER.warning("Error when fetching device info: %s", str(e))
            return False

        # Fetch data. Some data may not be availiable, that's okay.
        try:
            self._state["manufacturer"] = await self._fan.getManufacturer()
        except Exception as err:
            _LOGGER.debug("Couldn't read manufacturer! %s", str(err))
        try:
            self._state["model"] = await self._fan.getDeviceName()
        except Exception as err:
            _LOGGER.debug("Couldn't read device name! %s", str(err))
        try:
            self._state["fw_rev"] = await self._fan.getFirmwareRevision()
        except Exception as err:
            _LOGGER.debug("Couldn't read firmware revision! %s", str(err))
        try:
            self._state["hw_rev"] = await self._fan.getHardwareRevision()
        except Exception as err:
            _LOGGER.debug("Couldn't read hardware revision! %s", str(err))
        try:
            self._state["sw_rev"] = await self._fan.getSoftwareRevision()
        except Exception as err:
            _LOGGER.debug("Couldn't read software revision! %s", str(err))

        if not self._fan.isConnected():
            return False
        elif disconnect:
            await self._fan.disconnect()
        return True

    # Must be overridden by subclass
    @abstractmethod
    async def read_sensordata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading sensor data")

    # Must be overridden by subclass
    @abstractmethod
    async def write_data(self, key) -> bool:
        _LOGGER.debug("Write_Data: %s", key)

    # Must be overridden by subclass
    @abstractmethod
    async def read_configdata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading config data")