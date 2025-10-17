import datetime as dt
import logging

from typing import Optional

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

    async def read_sensordata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading sensor data")
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                _LOGGER.warning("Cannot read sensor data: not connected to %s", self.devicename)
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
            _LOGGER.warning("Error reading sensor data from %s: %s", self.devicename, str(e))
            return False

    async def write_data(self, key) -> bool:
        _LOGGER.debug("Write_Data: %s", key)
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                _LOGGER.warning("Cannot write data: not connected to %s", self.devicename)
                return False

            # Authorize
            await self._fan.authorize()

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
            _LOGGER.warning("Error writing data to %s: %s", self.devicename, str(e))
            return False

    async def read_configdata(self, disconnect=False) -> bool:
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                _LOGGER.warning("Cannot read config data: not connected to %s", self.devicename)
                return False

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
            _LOGGER.warning("Error reading config data from %s: %s", self.devicename, str(e))
            return False
