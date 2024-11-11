import datetime as dt
import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .devices.calima import Calima

from .coordinator import PaxCoordinator

_LOGGER = logging.getLogger(__name__)


class CalimaCoordinator(PaxCoordinator):
    _fast_poll_enabled = False
    _fast_poll_count = 0
    _normal_poll_interval = 60
    _fast_poll_interval = 10

    _deviceInfoLoaded = False
    _last_config_timestamp = None

    def __init__(self, hass, device, model, mac, pin, scan_interval, scan_interval_fast):
        """Initialize coordinator parent"""
        super().__init__(hass, device, model, mac, pin, scan_interval, scan_interval_fast)

        # Initialize correct fan
        _LOGGER.debug("Initializing Calima!")
        self._fan = Calima(hass, mac, pin)

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
        await self._fan.authorize()

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
                case "fanspeed_humidity" | "fanspeed_light" | "fanspeed_trickle":
                    await self._fan.setFanSpeedSettings(
                        int(self._state["fanspeed_humidity"]),
                        int(self._state["fanspeed_light"]),
                        int(self._state["fanspeed_trickle"]),
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
        SilentHours = await self._fan.getSilentHours()  # Configuration
        TrickleDays = await self._fan.getTrickleDays()  # Configuration
        AutomaticCycles = await self._fan.getAutomaticCycles()  # Configuration

        if FanMode is None:
            _LOGGER.debug("Could not read config")
            return False
        else:
            self._state["mode"] = FanMode

            self._state["silenthours_on"] = SilentHours.On
            self._state["silenthours_starttime"] = dt.time(SilentHours.StartingHour, SilentHours.StartingMinute)
            self._state["silenthours_endtime"] = dt.time(SilentHours.EndingHour, SilentHours.EndingMinute)

            self._state["trickledays_weekdays"] = TrickleDays.Weekdays
            self._state["trickledays_weekends"] = TrickleDays.Weekends

            self._state["automatic_cycles"] = AutomaticCycles
            
        # Device specific configs
        FanSpeeds = await self._fan.getFanSpeedSettings()  # Configuration
        self._state["fanspeed_humidity"] = FanSpeeds.Humidity
        self._state["fanspeed_light"] = FanSpeeds.Light
        self._state["fanspeed_trickle"] = FanSpeeds.Trickle

        HeatDistributorSettings = await self._fan.getHeatDistributor()  # Configuration
        self._state["heatdistributorsettings_temperaturelimit"] = HeatDistributorSettings.TemperatureLimit
        self._state["heatdistributorsettings_fanspeedbelow"] = HeatDistributorSettings.FanSpeedBelow
        self._state["heatdistributorsettings_fanspeedabove"] = HeatDistributorSettings.FanSpeedAbove

        LightSensorSettings = await self._fan.getLightSensorSettings()  # Configuration
        self._state["lightsensorsettings_delayedstart"] = LightSensorSettings.DelayedStart
        self._state["lightsensorsettings_runningtime"] = LightSensorSettings.RunningTime

        Sensitivity = await self._fan.getSensorsSensitivity()  # Configuration
        self._state["sensitivity_humidity"] = Sensitivity.Humidity
        self._state["sensitivity_light"] = Sensitivity.Light

        if disconnect:
            await self._fan.disconnect()
        return True
