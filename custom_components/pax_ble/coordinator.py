import logging
import async_timeout

from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .calima import Calima

_LOGGER = logging.getLogger(__name__)

class PaxCalimaCoordinator(DataUpdateCoordinator):
    _fast_poll_enabled = False
    _fast_poll_count = 0
    _normal_poll_interval = 60
    _fast_poll_interval = 10
    
    def __init__(self, hass, devicename, mac, pin, scanInterval, scanIntervalFast):
        """Initialize coordinator parent"""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Pax Calima",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=scanInterval),
        )

        self._normal_poll_interval = scanInterval
        self._fast_poll_interval = scanIntervalFast

        self._devicename = devicename
        self._mac = mac
        self._pin = pin
        self._state = {}
        self._fan = Calima(hass, mac, pin)

    def setFastPollMode(self):
        _LOGGER.debug("Enabling fast poll mode")
        self._fast_poll_enabled = True
        self._fast_poll_count = 0
        self.update_interval=timedelta(seconds=self._fast_poll_interval)
        self._schedule_refresh()

    def setNormalPollMode(self):
        _LOGGER.debug("Enabling normal poll mode")
        self._fast_poll_enabled = False
        self.update_interval=timedelta(seconds=self._normal_poll_interval)

    async def disconnect(self):
        await self._fan.disconnect()

    async def _async_update_data(self):
        _LOGGER.debug("Coordinator updating data!!")

        """ Counter for fast polling """
        if self._fast_poll_enabled:
            self._fast_poll_count += 1
            if self._fast_poll_count > 10:
                self.setNormalPollMode()

        """ Fetch data from device. """
        try:
            async with async_timeout.timeout(30):
                await self.async_fetch_data(disconnect=not self._fast_poll_enabled)
        except Exception as err:
            _LOGGER.debug("Failed when fetching sensordata: " + str(err))

    def get_data(self, key):
        if key in self._state:
            return self._state[key]
        return None

    def set_data(self, key, value):
        _LOGGER.debug("Set_Data: %s %s", key, value)
        self._state[key] = value

    async def write_data(self, key):
        _LOGGER.debug("Write_Data: %s", key)

        try:
            # Make sure we are connected and authorized
            if not await self._fan.connect():
                raise Exception("Not connected!")
            await self._fan.authorize()

            # Write data
            match key:
                case "automatic_cycles":
                    await self._fan.setAutomaticCycles(
                        int(self._state["automatic_cycles"])
                    )
                case "boostmode":
                    # Use default values if not set up
                    if int(self._state["boostmodesec"]) == 0:
                        self._state["boostmodespeed"] = 2400
                        self._state["boostmodesec"] = 600
                    await self._fan.setBoostMode(
                        int(self._state["boostmode"]),
                        int(self._state["boostmodespeed"]),
                        int(self._state["boostmodesec"]),
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
                case "silenthours_on" | "silenthours_startinghour" | "silenthours_startingminute" | "silenthours_endinghour" | "silenthours_endingminute":
                    await self._fan.setSilentHours(
                        int(self._state["silenthours_on"]),
                        int(self._state["silenthours_startinghour"]),
                        int(self._state["silenthours_startingminute"]),
                        int(self._state["silenthours_endinghour"]),
                        int(self._state["silenthours_endingminute"]),
                    )

                case _:
                    return False
        except Exception as e:
            _LOGGER.debug("Not able to write command: " + str(e))
            return False
            
        self.setFastPollMode()
        return True

    @property
    def devicename(self):
        return self._devicename

    @property
    def mac(self):
        return self._mac

    @property
    def pin(self):
        return self._pin

    async def read_deviceinfo(self, disconnect=True) -> bool:
        _LOGGER.debug("Reading device information")
        try:
            # Make sure we are connected
            if not await self._fan.connect():
                raise Exception("Not connected!")

            # Fetch data. Some data may not be availiable, that's okay.
            try:
                self._state["manufacturer"] = await self._fan.getManufacturer()
            except Exception as err:
                _LOGGER.debug("Couldn't read manufacturer! " + str(err))
            try:
                self._state["model"] = await self._fan.getDeviceName()
            except Exception as err:
                _LOGGER.debug("Couldn't read device name! " + str(err))
            try:
                self._state["fw_rev"] = await self._fan.getFirmwareRevision()
            except Exception as err:
                _LOGGER.debug("Couldn't read firmware revision! " + str(err))
            try:
                self._state["hw_rev"] = await self._fan.getHardwareRevision()
            except Exception as err:
                _LOGGER.debug("Couldn't read hardware revision! " + str(err))
            try:
                self._state["sw_rev"] = await self._fan.getSoftwareRevision()
            except Exception as err:
                _LOGGER.debug("Couldn't read software revision! " + str(err))

            _LOGGER.debug("Device information read successfully!")
            return True
        except Exception as e:
            _LOGGER.warning("Error when fetching Device information: " + str(e))
            return False
        finally:
            if disconnect:
                await self._fan.disconnect()

    async def read_sensordata(self):
        FanState = await self._fan.getState()  # Sensors
        BoostMode = await self._fan.getBoostMode()  # Sensors?

        if FanState is None:
            _LOGGER.debug("Could not read data")
        else:
            self._state["humidity"] = FanState.Humidity
            self._state["temperature"] = FanState.Temp
            self._state["light"] = FanState.Light
            self._state["rpm"] = FanState.RPM
            if FanState.RPM > 400:
                self._state["flow"] = int(FanState.RPM*0.05076 - 14)
            else:
                self._state["flow"] = 0
            self._state["state"] = FanState.Mode

            self._state["boostmode"] = BoostMode.OnOff
            self._state["boostmodespeed"] = BoostMode.Speed
            self._state["boostmodesec"] = BoostMode.Seconds

    async def read_configdata(self):
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
            self._state["silenthours_startinghour"] = SilentHours.StartingHour
            self._state["silenthours_startingminute"] = SilentHours.StartingMinute
            self._state["silenthours_endinghour"] = SilentHours.EndingHour
            self._state["silenthours_endingminute"] = SilentHours.EndingMinute

            self._state["trickledays_weekdays"] = TrickleDays.Weekdays
            self._state["trickledays_weekends"] = TrickleDays.Weekends

            self._state["automatic_cycles"] = AutomaticCycles

    async def async_fetch_data(self, disconnect=True) -> bool:
        try:
            # Make sure we are connected
            if not await self._fan.connect():
                raise Exception("Not connected!")

            # Fetch data and config
            await self.read_sensordata()
            await self.read_configdata()
            return True
        except Exception as e:
            _LOGGER.warning("Error when fetching data: " + str(e))
            return False
        finally:
            if disconnect:
                await self._fan.disconnect()
