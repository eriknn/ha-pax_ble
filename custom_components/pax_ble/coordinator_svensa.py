import logging

from typing import Optional

from .coordinator import BaseCoordinator
from .devices.svensa import Svensa

_LOGGER = logging.getLogger(__name__)


class SvensaCoordinator(BaseCoordinator):
    _fan: Optional[Svensa] = None  # This is basically a type hint

    def __init__(
        self, hass, device, model, mac, pin, scan_interval, scan_interval_fast
    ):
        """Initialize coordinator parent"""
        super().__init__(
            hass, device, model, mac, pin, scan_interval, scan_interval_fast
        )

        # Initialize correct fan
        _LOGGER.debug("Initializing Svensa!")
        self._fan = Svensa(hass, mac, pin)

    async def read_sensordata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading sensor data")
        try:
            # Make sure we are connected
            if not await self._safe_connect():
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
            self._state["airquality"] = FanState.AirQuality
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

    async def write_data(self, key) -> bool:
        _LOGGER.debug("Write_Data: %s", key)
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                raise Exception("Not connected!")
        except Exception as e:
            _LOGGER.warning("Error when writing data: %s", str(e))
            return False

        # Authorize
        await self._fan.authorize()

        try:
            # Write data
            match key:
                case "airing" | "fanspeed_airing":
                    await self._fan.setAutomaticCycles(
                        26,
                        int(self._state["airing"]),
                        int(self._state["fanspeed_airing"]),
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
                case "sensitivity_humidity" | "fanspeed_humidity":
                    await self._fan.setHumidity(
                        int(self._state["sensitivity_humidity"]) != 0,
                        int(self._state["sensitivity_humidity"]),
                        int(self._state["fanspeed_humidity"]),
                    )
                case "sensitivity_presence" | "sensitivity_gas":
                    await self._fan.setPresenceGas(
                        int(self._state["sensitivity_presence"]) != 0,
                        int(self._state["sensitivity_presence"]),
                        int(self._state["sensitivity_gas"]) != 0,
                        int(self._state["sensitivity_gas"]),
                    )
                case "timer_runtime" | "timer_delay" | "fanspeed_sensor":
                    await self._fan.setTimerFunctions(
                        int(self._state["timer_runtime"]),
                        int(self._state["timer_delay"]) != 0,
                        int(self._state["timer_delay"]),
                        int(self._state["fanspeed_sensor"]),
                    )
                case "trickle_on" | "fanspeed_trickle":
                    await self._fan.setConstantOperation(
                        bool(self._state["trickle_on"]),
                        int(self._state["fanspeed_trickle"]),
                    )
                case "sensitivity_light":
                    # Should we do anything here?
                    pass

                case _:
                    return False

        except Exception as e:
            _LOGGER.debug("Not able to write command: %s", str(e))
            return False

        self.setFastPollMode()
        return True

    async def read_configdata(self, disconnect=False) -> bool:
        try:
            # Make sure we are connected
            if not await self._safe_connect():
                raise Exception("Not connected!")
        except Exception as e:
            _LOGGER.warning("Error when fetching config data: %s", str(e))
            return False

        AutomaticCycles = await self._fan.getAutomaticCycles()  # Configuration
        self._state["airing"] = AutomaticCycles.TimeMin
        self._state["fanspeed_airing"] = AutomaticCycles.Speed
        _LOGGER.debug(f"Automatic cycles: {AutomaticCycles}")

        ConstantOperation = await self._fan.getConstantOperation()  # Configuration
        self._state["trickle_on"] = ConstantOperation.Active
        self._state["fanspeed_trickle"] = ConstantOperation.Speed
        _LOGGER.debug(f"Constant Op: {ConstantOperation}")

        FanMode = await self._fan.getMode()  # Configurations
        self._state["mode"] = FanMode
        _LOGGER.debug(f"FanMode: {FanMode}")

        Humidity = await self._fan.getHumidity()  # Configuration
        self._state["fanspeed_humidity"] = Humidity.Speed
        self._state["sensitivity_humidity"] = Humidity.Level
        _LOGGER.debug(f"Humidity: {Humidity}")

        PresenceGas = await self._fan.getPresenceGas()  # Configuration
        self._state["sensitivity_presence"] = PresenceGas.PresenceLevel
        self._state["sensitivity_gas"] = PresenceGas.GasLevel
        _LOGGER.debug(f"PresenceGas: {PresenceGas}")

        TimeFunctions = await self._fan.getTimerFunctions()  # Configuration
        self._state["timer_runtime"] = TimeFunctions.PresenceTime
        self._state["timer_delay"] = TimeFunctions.TimeMin
        self._state["fanspeed_sensor"] = TimeFunctions.Speed
        _LOGGER.debug(f"Time Functions: {TimeFunctions}")

        if disconnect:
            await self._fan.disconnect()
        return True
