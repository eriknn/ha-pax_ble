import asyncio
import datetime as dt
import logging

from typing import Optional

from homeassistant.util import dt as dt_util

from .coordinator import BaseCoordinator
from .devices.calima import Calima

_LOGGER = logging.getLogger(__name__)


class CalimaCoordinator(BaseCoordinator):
    _fan: Optional[Calima] = None  # This is basically a type hint

    def __init__(
        self, hass, device, model, mac, pin, scan_interval, scan_interval_fast
    ):
        """Initialize coordinator parent"""
        super().__init__(
            hass, device, model, scan_interval, scan_interval_fast
        )

        # Initialize correct fan
        _LOGGER.debug("Initializing Calima!")
        self._fan = Calima(hass, mac, pin)

        # Set up disconnect callback
        self._fan.set_disconnect_callback(self._on_device_disconnect)
        self._last_clock_sync_check: Optional[dt.datetime] = None
        self._operation_lock = asyncio.Lock()

    async def _async_update_data(self):
        async with self._operation_lock:
            return await super()._async_update_data()

    async def read_sensordata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading sensor data")
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                _LOGGER.debug("Cannot read sensor data: not connected to %s", self.devicename)
                return False

            if (
                not await self._sync_clock_if_needed()
                and not await self._safe_connect()
            ):
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

        except Exception as e:
            _LOGGER.debug("Error reading sensor data from %s: %s", self.devicename, str(e))
            return False

    async def _sync_clock_if_needed(self, force: bool = False) -> bool:
        now = dt_util.now()
        if (
            not force
            and self._last_clock_sync_check is not None
            and now - self._last_clock_sync_check < dt.timedelta(minutes=10)
        ):
            return True

        try:
            fan_time = await self._fan.getTime()
            current_seconds = (
                (now.isoweekday() - 1) * 86400
                + now.hour * 3600
                + now.minute * 60
                + now.second
            )
            if (
                1 <= fan_time.DayOfWeek <= 7
                and 0 <= fan_time.Hour <= 23
                and 0 <= fan_time.Minute <= 59
                and 0 <= fan_time.Second <= 59
            ):
                fan_seconds = (
                    (fan_time.DayOfWeek - 1) * 86400
                    + fan_time.Hour * 3600
                    + fan_time.Minute * 60
                    + fan_time.Second
                )
                time_delta = abs(current_seconds - fan_seconds)
                time_delta = min(time_delta, 7 * 86400 - time_delta)

                if time_delta <= 120:
                    self._last_clock_sync_check = now
                    return True

            await self._fan.authorize()
            await self._fan.setTime(
                now.isoweekday(),
                now.hour,
                now.minute,
                now.second,
            )
            self._last_clock_sync_check = now
            _LOGGER.info(
                "Synced clock for %s from day=%s %02d:%02d:%02d to day=%s %02d:%02d:%02d",
                self.devicename,
                fan_time.DayOfWeek,
                fan_time.Hour,
                fan_time.Minute,
                fan_time.Second,
                now.isoweekday(),
                now.hour,
                now.minute,
                now.second,
            )
            return True
        except Exception as e:
            _LOGGER.warning("Unable to sync clock for %s: %s", self.devicename, str(e))
            return False

    async def write_data(self, key) -> bool:
        requested_value = self._state.get(key)
        async with self._operation_lock:
            return await self._write_data(key, requested_value)

    async def _write_data(self, key, requested_value) -> bool:
        _LOGGER.debug("Write_Data: %s", key)
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                _LOGGER.debug("Cannot write data: not connected to %s", self.devicename)
                return False

            if (
                not await self._sync_clock_if_needed()
                and not await self._safe_connect()
            ):
                return False

            # Authorize
            await self._fan.authorize()
            required_config_keys = {
                "fanspeed_humidity": (
                    "fanspeed_humidity",
                    "fanspeed_light",
                    "fanspeed_trickle",
                ),
                "fanspeed_light": (
                    "fanspeed_humidity",
                    "fanspeed_light",
                    "fanspeed_trickle",
                ),
                "fanspeed_trickle": (
                    "fanspeed_humidity",
                    "fanspeed_light",
                    "fanspeed_trickle",
                ),
                "lightsensorsettings_delayedstart": (
                    "lightsensorsettings_delayedstart",
                    "lightsensorsettings_runningtime",
                ),
                "lightsensorsettings_runningtime": (
                    "lightsensorsettings_delayedstart",
                    "lightsensorsettings_runningtime",
                ),
                "sensitivity_humidity": ("sensitivity_humidity", "sensitivity_light"),
                "sensitivity_light": ("sensitivity_humidity", "sensitivity_light"),
                "trickledays_weekdays": (
                    "trickledays_weekdays",
                    "trickledays_weekends",
                ),
                "trickledays_weekends": (
                    "trickledays_weekdays",
                    "trickledays_weekends",
                ),
                "silenthours_on": (
                    "silenthours_on",
                    "silenthours_starttime",
                    "silenthours_endtime",
                ),
                "silenthours_starttime": (
                    "silenthours_on",
                    "silenthours_starttime",
                    "silenthours_endtime",
                ),
                "silenthours_endtime": (
                    "silenthours_on",
                    "silenthours_starttime",
                    "silenthours_endtime",
                ),
                "heatdistributorsettings_temperaturelimit": (
                    "heatdistributorsettings_temperaturelimit",
                    "heatdistributorsettings_fanspeedbelow",
                    "heatdistributorsettings_fanspeedabove",
                ),
                "heatdistributorsettings_fanspeedbelow": (
                    "heatdistributorsettings_temperaturelimit",
                    "heatdistributorsettings_fanspeedbelow",
                    "heatdistributorsettings_fanspeedabove",
                ),
                "heatdistributorsettings_fanspeedabove": (
                    "heatdistributorsettings_temperaturelimit",
                    "heatdistributorsettings_fanspeedbelow",
                    "heatdistributorsettings_fanspeedabove",
                ),
            }

            if dependencies := required_config_keys.get(key):
                if not await self._ensure_config_keys(*dependencies):
                    return False
            self._state[key] = requested_value

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
                case "fanspeed_humidity" | "fanspeed_light" | "fanspeed_trickle":
                    await self._fan.setFanSpeedSettings(
                        int(self._state["fanspeed_humidity"]),
                        int(self._state["fanspeed_light"]),
                        int(self._state["fanspeed_trickle"]),
                    )
                case (
                    "lightsensorsettings_delayedstart"
                    | "lightsensorsettings_runningtime"
                ):
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
                case "silenthours_on" | "silenthours_starttime" | "silenthours_endtime":
                    await self._fan.setSilentHours(
                        bool(self._state["silenthours_on"]),
                        self._state["silenthours_starttime"],
                        self._state["silenthours_endtime"],
                    )
                case "heatdistributorsettings_temperaturelimit" | "heatdistributorsettings_fanspeedbelow" | "heatdistributorsettings_fanspeedabove":
                    await self._fan.setHeatDistributor(
                        int(self._state["heatdistributorsettings_temperaturelimit"]),
                        int(self._state["heatdistributorsettings_fanspeedbelow"]),
                        int(self._state["heatdistributorsettings_fanspeedabove"]),
                    )
                case _:
                    return False

            self.setFastPollMode()
            return True

        except Exception as e:
            _LOGGER.debug("Error writing data to %s: %s", self.devicename, str(e))
            return False
        finally:
            await self._fan.disconnect()

    async def _ensure_config_keys(self, *keys: str) -> bool:
        try:
            match keys[0]:
                case "fanspeed_humidity":
                    settings = await self._fan.getFanSpeedSettings()
                    self._state["fanspeed_humidity"] = settings.Humidity
                    self._state["fanspeed_light"] = settings.Light
                    self._state["fanspeed_trickle"] = settings.Trickle
                case "lightsensorsettings_delayedstart":
                    settings = await self._fan.getLightSensorSettings()
                    self._state["lightsensorsettings_delayedstart"] = (
                        settings.DelayedStart
                    )
                    self._state["lightsensorsettings_runningtime"] = (
                        settings.RunningTime
                    )
                case "sensitivity_humidity":
                    settings = await self._fan.getSensorsSensitivity()
                    self._state["sensitivity_humidity"] = settings.Humidity
                    self._state["sensitivity_light"] = settings.Light
                case "trickledays_weekdays":
                    settings = await self._fan.getTrickleDays()
                    self._state["trickledays_weekdays"] = settings.Weekdays
                    self._state["trickledays_weekends"] = settings.Weekends
                case "silenthours_on":
                    settings = await self._fan.getSilentHours()
                    self._state["silenthours_on"] = settings.On
                    self._state["silenthours_starttime"] = dt.time(
                        settings.StartingHour, settings.StartingMinute
                    )
                    self._state["silenthours_endtime"] = dt.time(
                        settings.EndingHour, settings.EndingMinute
                    )
                case "heatdistributorsettings_temperaturelimit":
                    settings = await self._fan.getHeatDistributor()
                    self._state["heatdistributorsettings_temperaturelimit"] = (
                        settings.TemperatureLimit
                    )
                    self._state["heatdistributorsettings_fanspeedbelow"] = (
                        settings.FanSpeedBelow
                    )
                    self._state["heatdistributorsettings_fanspeedabove"] = (
                        settings.FanSpeedAbove
                    )
                case _:
                    return False
        except Exception as e:
            _LOGGER.debug(
                "Error refreshing config group for %s: %s",
                self.devicename,
                str(e),
            )
            return False

        missing = [key for key in keys if self._state.get(key) is None]
        if missing:
            _LOGGER.warning(
                "Missing config values for %s after refresh: %s",
                self.devicename,
                ", ".join(missing),
            )
            return False
        return True

    async def read_configdata(self, disconnect=False) -> bool:
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                raise Exception("Not connected!")

            if (
                not await self._sync_clock_if_needed(force=True)
                and not await self._safe_connect()
            ):
                raise Exception("Not connected after clock sync failure")

            AutomaticCycles = await self._fan.getAutomaticCycles()  # Configuration
            self._state["automatic_cycles"] = AutomaticCycles

            FanMode = await self._fan.getMode()  # Configurations
            self._state["mode"] = FanMode

            FanSpeeds = await self._fan.getFanSpeedSettings()  # Configuration
            self._state["fanspeed_humidity"] = FanSpeeds.Humidity
            self._state["fanspeed_light"] = FanSpeeds.Light
            self._state["fanspeed_trickle"] = FanSpeeds.Trickle

            HeatDistributorSettings = await self._fan.getHeatDistributor()  # Configuration
            self._state["heatdistributorsettings_temperaturelimit"] = (
                HeatDistributorSettings.TemperatureLimit
            )
            self._state["heatdistributorsettings_fanspeedbelow"] = (
                HeatDistributorSettings.FanSpeedBelow
            )
            self._state["heatdistributorsettings_fanspeedabove"] = (
                HeatDistributorSettings.FanSpeedAbove
            )

            LightSensorSettings = await self._fan.getLightSensorSettings()  # Configuration
            self._state["lightsensorsettings_delayedstart"] = (
                LightSensorSettings.DelayedStart
            )
            self._state["lightsensorsettings_runningtime"] = LightSensorSettings.RunningTime

            Sensitivity = await self._fan.getSensorsSensitivity()  # Configuration
            self._state["sensitivity_humidity"] = Sensitivity.Humidity
            self._state["sensitivity_light"] = Sensitivity.Light

            SilentHours = await self._fan.getSilentHours()  # Configuration
            self._state["silenthours_on"] = SilentHours.On
            self._state["silenthours_starttime"] = dt.time(
                SilentHours.StartingHour, SilentHours.StartingMinute
            )
            self._state["silenthours_endtime"] = dt.time(
                SilentHours.EndingHour, SilentHours.EndingMinute
            )

            TrickleDays = await self._fan.getTrickleDays()  # Configuration
            self._state["trickledays_weekdays"] = TrickleDays.Weekdays
            self._state["trickledays_weekends"] = TrickleDays.Weekends

            if disconnect:
                await self._fan.disconnect()
            return True

        except Exception as e:
            _LOGGER.debug("Error reading config data from %s: %s", self.devicename, str(e))
            return False
