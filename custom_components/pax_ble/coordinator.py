import async_timeout
import datetime as dt
import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .ble_fan import BleFan

_LOGGER = logging.getLogger(__name__)


class PaxCalimaCoordinator(DataUpdateCoordinator):
    _fast_poll_enabled = False
    _fast_poll_count = 0
    _normal_poll_interval = 60
    _fast_poll_interval = 10

    _deviceInfoLoaded = False
    _last_config_timestamp = None

    def __init__(self, hass, device, model, mac, pin, scan_interval, scan_interval_fast):
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
        self._mac = mac
        self._pin = pin
        self._fan = BleFan(hass, model, mac, pin)

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

    @property
    def mac(self):
        return self._mac

    @property
    def pin(self):
        return self._pin

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

    async def write_data(self, key) -> bool:
        _LOGGER.debug("Write_Data: %s", key)
        try:
            # Make sure we are connected
            if not await self._fan.connect():
                raise Exception("Not connected!")
        except Exception as e:
            _LOGGER.warning("Error when writing data: %s", str(e))
            return False

        # Authorize
        await self._fan.setAuth(self._pin)

        try:
            # Write data
            match key:
                case "automatic_cycles":
                    await self._fan.setAutomaticCycles(
                        int(self._state["automatic_cycles"])
                    )
                case "boostmode":
                    # Use default values if not set up
                    if int(self._state["boostmodesecwrite"]) == 0:
                        self._state["boostmodespeedwrite"] = 2400
                        self._state["boostmodesecwrite"] = 600
                    await self._fan.setBoostMode(
                        int(self._state["boostmode"]),
                        int(self._state["boostmodespeedwrite"]),
                        int(self._state["boostmodesecwrite"]),
                    )
                case "lightsensorsettings_delayedstart" | "lightsensorsettings_runningtime":
                    await self._fan.setLightSensorSettings(
                        int(self._state["lightsensorsettings_delayedstart"]),
                        int(self._state["lightsensorsettings_runningtime"]),
                    )
                case "sensitivity_humidity" | "sensitivity_light":
                    await self._fan.setSensorsSensitivity(
                        int(self._state["sensitivity_humidity"]),
                        int(self._state["sensitivity_light"]),
                    )
                case "trickledays_weekdays" | "trickledays_weekends":
                    await self._fan.setTrickleDays(
                        int(self._state["trickledays_weekdays"]),
                        int(self._state["trickledays_weekends"]),
                    )

                case "fanspeed_humidity" | "fanspeed_light" | "fanspeed_trickle":
                    await self._fan.setFanSpeedSettings(
                        int(self._state["fanspeed_humidity"]),
                        int(self._state["fanspeed_light"]),
                        int(self._state["fanspeed_trickle"]),
                    )
                case "heatdistributorsettings_temperaturelimit" | "heatdistributorsettings_fanspeedbelow" | "heatdistributorsettings_fanspeedabove":
                    """Not implemented"""
                case "silenthours_on" | "silenthours_starttime" | "silenthours_endtime":
                    await self._fan.setSilentHours(
                        bool(int(self._state["silenthours_on"])),
                        self._state["silenthours_starttime"],
                        self._state["silenthours_endtime"],
                    )

                case _:
                    return False
        except Exception as e:
            _LOGGER.debug("Not able to write command: %s", str(e))
            return False

        self.setFastPollMode()
        return True

    async def read_deviceinfo(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading device information")
        try:
            # Make sure we are connected
            if not await self._fan.connect():
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

    async def read_sensordata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading sensor data")
        try:
            # Make sure we are connected
            if not await self._fan.connect():
                raise Exception("Not connected!")
        except Exception as e:
            _LOGGER.warning("Error when fetching config data: %s", str(e))
            return False

        FanState = await self._fan.getState()  # Sensors
        BoostMode = await self._fan.getBoostMode()  # Sensors?

        if FanState is None:
            _LOGGER.debug("Could not read data")
            return False
        else:
            self._state["humidity"] = FanState.Humidity
            self._state["temperature"] = FanState.Temp
            self._state["light"] = FanState.Light
            self._state["rpm"] = FanState.RPM
            if FanState.RPM > 400:
                self._state["flow"] = int(FanState.RPM * 0.05076 - 14)
            else:
                self._state["flow"] = 0
            self._state["state"] = FanState.Mode

            self._state["boostmode"] = BoostMode.OnOff
            self._state["boostmodespeedread"] = BoostMode.Speed
            self._state["boostmodesecread"] = BoostMode.Seconds

        if disconnect:
            await self._fan.disconnect()
        return True

    async def read_configdata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading config data")
        try:
            # Make sure we are connected
            if not await self._fan.connect():
                raise Exception("Not connected!")
        except Exception as e:
            _LOGGER.warning("Error when fetching config data: %s", str(e))
            return False

        FanMode = await self._fan.getMode()  # Configuration
        FanSpeeds = await self._fan.getFanSpeedSettings()  # Configuration
        Sensitivity = await self._fan.getSensorsSensitivity()  # Configuration
        LightSensorSettings = await self._fan.getLightSensorSettings()  # Configuration
        HeatDistributorSettings = await self._fan.getHeatDistributor()  # Configuration
        SilentHours = await self._fan.getSilentHours()  # Configuration
        TrickleDays = await self._fan.getTrickleDays()  # Configuration
        AutomaticCycles = await self._fan.getAutomaticCycles()  # Configuration

        if FanMode is None:
            _LOGGER.debug("Could not read config")
            return False
        else:
            self._state["mode"] = FanMode

            self._state["fanspeed_humidity"] = FanSpeeds.Humidity
            self._state["fanspeed_light"] = FanSpeeds.Light
            self._state["fanspeed_trickle"] = FanSpeeds.Trickle

            self._state["sensitivity_humidity"] = Sensitivity.Humidity
            self._state["sensitivity_light"] = Sensitivity.Light

            self._state[
                "lightsensorsettings_delayedstart"
            ] = LightSensorSettings.DelayedStart
            self._state[
                "lightsensorsettings_runningtime"
            ] = LightSensorSettings.RunningTime

            self._state[
                "heatdistributorsettings_temperaturelimit"
            ] = HeatDistributorSettings.TemperatureLimit
            self._state[
                "heatdistributorsettings_fanspeedbelow"
            ] = HeatDistributorSettings.FanSpeedBelow
            self._state[
                "heatdistributorsettings_fanspeedabove"
            ] = HeatDistributorSettings.FanSpeedAbove

            self._state["silenthours_on"] = SilentHours.On
            self._state["silenthours_starttime"] = dt.time(SilentHours.StartingHour, SilentHours.StartingMinute)
            self._state["silenthours_endtime"] = dt.time(SilentHours.EndingHour, SilentHours.EndingMinute)

            self._state["trickledays_weekdays"] = TrickleDays.Weekdays
            self._state["trickledays_weekends"] = TrickleDays.Weekends

            self._state["automatic_cycles"] = AutomaticCycles

        if disconnect:
            await self._fan.disconnect()
        return True
