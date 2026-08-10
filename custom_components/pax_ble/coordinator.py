import asyncio
import async_timeout
import datetime as dt
import logging

from abc import ABC, abstractmethod
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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

    # Error tracking for rate limiting
    _consecutive_failures = 0
    _last_error_log_time = None
    _error_backoff_delay = 0  # seconds

    # Should be set by a child class
    _fan: Optional[BaseDevice] = None  # This is basically a type hint

    def __init__(
        self,
        hass,
        device: DeviceEntry,
        model: str,
        scan_interval: int,
        scan_interval_fast: int,
    ):
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

        self._fan: Optional[BaseDevice] = None  # Base class for Calima/Svensa
        self._device = device
        self._model = model

        # Connection management
        self._connection_failures = 0
        self._max_connection_failures = 5
        # Report failures to the coordinator once this many consecutive
        # polls have failed - deliberately below _max_connection_failures so
        # the outage is visible while reconnection is still being attempted.
        self._failure_report_threshold = 3
        # After giving up, let one probe attempt through every this-many
        # skipped polls (counted at the normal interval; see _async_update_data).
        self._recovery_probe_skips = 6
        self._recovery_skips = 0  # polls skipped since giving up (see _async_update_data)
        self._max_backoff = 300  # 5 minutes max backoff
        self._backoff_multiplier = 2
        self._reconnection_task = None

        # Initialize state in case of new integration
        self._state = {}
        self._state["boostmodespeedwrite"] = 2400
        self._state["boostmodesecwrite"] = 600

        # Note: disconnect callback will be set up in child classes after _fan is initialized

    @property
    def fan(self) -> BaseDevice:
        return self._fan

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
        """Enable fast polling only if device is connected."""
        if not self._fan or not self._fan.isConnected():
            _LOGGER.debug("Cannot enable fast poll mode - device not connected")
            return

        _LOGGER.debug("Enabling fast poll mode")
        self._fast_poll_enabled = True
        self._fast_poll_count = 0
        self.update_interval = dt.timedelta(seconds=self._fast_poll_interval)

        # Assigning update_interval only stores the value - the coordinator's
        # setter does not re-arm the already-scheduled refresh, so the next poll
        # still lands at the old interval (up to scan_interval away) and values
        # just written to the device keep reading stale.
        self._schedule_refresh()

    def setNormalPollMode(self):
        _LOGGER.debug("Enabling normal poll mode")
        self._fast_poll_enabled = False
        # Use adaptive interval based on connection health
        interval = self._normal_poll_interval
        if self._connection_failures > 0:
            interval = min(self._normal_poll_interval * (2 ** self._connection_failures), self._max_backoff)
        self.update_interval = dt.timedelta(seconds=interval)

        # Same re-arm as setFastPollMode(): assigning update_interval only
        # stores the value, so the pending tick would still fire once at
        # the old (fast) interval before the normal interval takes effect.
        self._schedule_refresh()

    async def disconnect(self):
        """Safely disconnect from device."""
        # Cancel any pending reconnection task
        if self._reconnection_task and not self._reconnection_task.done():
            self._reconnection_task.cancel()
            self._reconnection_task = None

        if self._fan:
            await self._fan.disconnect()

    async def _on_device_disconnect(self):
        """Called when device disconnects unexpectedly."""
        _LOGGER.warning("Device %s disconnected unexpectedly", self.devicename)
        self._connection_failures += 1

        # Disable fast polling immediately
        if self._fast_poll_enabled:
            self.setNormalPollMode()

        # Start background reconnection if not already running
        if not self._reconnection_task or self._reconnection_task.done():
            self._reconnection_task = asyncio.create_task(self._background_reconnect())

    async def _background_reconnect(self):
        """Background task to reconnect to device with exponential backoff."""
        while self._connection_failures > 0 and self._connection_failures < self._max_connection_failures:
            backoff_time = min(
                self._fast_poll_interval * (self._backoff_multiplier ** (self._connection_failures - 1)),
                self._max_backoff
            )
            _LOGGER.debug("Attempting reconnection to %s in %d seconds (attempt %d)",
                         self.devicename, backoff_time, self._connection_failures)

            await asyncio.sleep(backoff_time)

            try:
                if await self._safe_connect():
                    _LOGGER.info("Successfully reconnected to %s", self.devicename)
                    self._connection_failures = 0
                    self.setNormalPollMode()
                    # Trigger immediate data refresh
                    await self._async_update_data()
                    return
                else:
                    self._connection_failures += 1
            except Exception as e:
                _LOGGER.debug("Reconnection attempt failed: %s", e)
                self._connection_failures += 1

        if self._connection_failures >= self._max_connection_failures:
            _LOGGER.error("Failed to reconnect to %s after %d attempts, giving up",
                         self.devicename, self._max_connection_failures)

    async def _safe_connect(self) -> bool:
        """
        Try to connect with improved error handling and validation.
        """
        if not self._fan:
            return False

        # Check if we're already connected and validate the connection
        if self._fan.isConnected():
            if await self._fan.validate_connection():
                # Reset failure count on successful validation
                if self._connection_failures > 0:
                    _LOGGER.info("Connection to %s validated, resetting failure count", self.devicename)
                    self._connection_failures = 0
                return True
            else:
                _LOGGER.debug("Existing connection failed validation, reconnecting")

        try:
            # Use longer timeout for ESP32 proxies
            timeout = 45 if self._connection_failures > 2 else 30
            if await self._fan.connect(timeout=timeout):
                # Validate the new connection
                if await self._fan.validate_connection():
                    self._connection_failures = 0
                    return True
                else:
                    _LOGGER.warning("New connection failed validation")
                    return False
            else:
                return False
        except Exception as e:
            _LOGGER.debug("Connection attempt failed: %s", e)
            return False

    async def _async_update_data(self):
        _LOGGER.debug("Coordinator updating data!!")

        """ Counter for fast polling """
        self._update_poll_counter()

        # Periodically let a given-up-on device try again.
        #
        # Once _connection_failures reaches _max_connection_failures the
        # branch below stops polling entirely, and _background_reconnect has
        # already exited (its loop runs only while failures < max), so
        # nothing retries and the device stays dead until the integration is
        # reloaded. Measured: a fan audible at -75 dBm, well inside working
        # range, sat unavailable with no connection attempt made at all.
        #
        # Stepping the counter back to one below the limit lets exactly one
        # attempt through. Success resets it to 0; failure pushes it back
        # over the limit, so a device that is genuinely gone costs one
        # connection attempt per probe rather than one per poll.
        #
        # The interval is deliberately long: a failing connect runs to a
        # 30-45s timeout while holding a BLE proxy connection slot, and that
        # blocking can stop every other device from being polled. Recovery
        # should be cheap, not fast.
        if self._connection_failures >= self._max_connection_failures:
            # Anchor the probe cadence to the normal interval: if fast poll
            # was still armed when the device gave up, the skip counter
            # would otherwise run at the fast interval and probe within
            # seconds rather than the intended half hour.
            if self._fast_poll_enabled:
                self.setNormalPollMode()
            self._recovery_skips += 1
            if self._recovery_skips >= self._recovery_probe_skips:
                self._recovery_skips = 0
                self._connection_failures = self._max_connection_failures - 1
                _LOGGER.info(
                    "Retrying %s after giving up - one probe attempt",
                    self.devicename,
                )
        elif self._recovery_skips:
            self._recovery_skips = 0

        # Skip updates if we have too many connection failures.
        #
        # Raise rather than return: returning is how a DataUpdateCoordinator
        # reports a SUCCESSFUL poll, so a bare `return` here leaves
        # last_update_success True and every entity "available", still
        # showing the value it last managed to read - indefinitely, because
        # this branch never retries either. A device the integration has
        # stopped polling must not keep presenting a stale reading as if it
        # were current.
        if self._connection_failures >= self._max_connection_failures:
            raise UpdateFailed(
                "Not polling %s: %d consecutive failures (limit %d)"
                % (
                    self.devicename,
                    self._connection_failures,
                    self._max_connection_failures,
                )
            )

        # Early return on cancellation to avoid blocking HA startup
        try:
            # Check if we're being cancelled early
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            _LOGGER.debug("Update cancelled before starting")
            raise

        """ Fetch device info if not already fetched """
        if not self._deviceInfoLoaded:
            try:
                async with async_timeout.timeout(45):
                    if await self.read_deviceinfo(disconnect=False):
                        await self._async_update_device_info()
                        self._deviceInfoLoaded = True
            except asyncio.CancelledError:
                _LOGGER.debug("Device info loading was cancelled")
                raise  # Re-raise cancellation to handle it properly
            except Exception as err:
                _LOGGER.debug("Failed when loading device information: %s", str(err))
                self._connection_failures += 1

        """ Fetch config data if we have no/old values """
        if dt.datetime.now().date() != self._last_config_timestamp:
            try:
                async with async_timeout.timeout(45):
                    if await self.read_configdata(disconnect=False):
                        self._last_config_timestamp = dt.datetime.now().date()
            except asyncio.CancelledError:
                _LOGGER.debug("Config data loading was cancelled")
                raise  # Re-raise cancellation to handle it properly
            except Exception as err:
                _LOGGER.debug("Failed when loading config data: %s", str(err))
                self._connection_failures += 1

        """ Fetch sensor data """
        try:
            async with async_timeout.timeout(30):
                success = await self.read_sensordata(disconnect=not self._fast_poll_enabled)
                if success:
                    # Reset connection failures on successful data read
                    if self._connection_failures > 0:
                        _LOGGER.debug("Successful data read, resetting connection failures")
                        self._connection_failures = 0
                        self.setNormalPollMode()
                else:
                    self._connection_failures += 1
        except asyncio.CancelledError:
            _LOGGER.debug("Sensor data loading was cancelled")
            raise  # Re-raise cancellation to handle it properly
        except Exception as err:
            _LOGGER.debug("Failed when fetching sensordata: %s", str(err))
            self._connection_failures += 1

        # Report a sustained inability to read the device.
        #
        # Every failure path above only increments a counter and falls
        # through, and returning normally is how this coordinator signals a
        # SUCCESSFUL poll - so without this, last_update_success stays True
        # and the entities keep publishing the value they last managed to
        # read. A running fan can sit on screen at "Idle / 0 rpm" for hours
        # with nothing marked unavailable.
        #
        # A threshold rather than the first failure: an occasional missed
        # poll is normal for BLE and self-corrects on the next cycle, and
        # flapping every entity unavailable on one blip would make the
        # signal worthless. The default (3) is ~15 min at the default 300s
        # scan_interval and sits below _max_connection_failures on purpose,
        # so the outage is visible while reconnection is still attempted.
        if self._connection_failures >= self._failure_report_threshold:
            raise UpdateFailed(
                "No successful read from %s in %d consecutive attempts"
                % (self.devicename, self._connection_failures)
            )

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

        # Publish straight away. Callers set the value here and only tell Home
        # Assistant after the device write returns, which leaves the state
        # machine reporting the old value for the whole duration of that write.
        self.async_update_listeners()

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
