import datetime
import logging
import math

from .characteristics import *
from .base_device import BaseDevice

from collections import namedtuple
from struct import pack, unpack

_LOGGER = logging.getLogger(__name__)

Fanspeeds = namedtuple(
    "Fanspeeds", "Humidity Light Trickle", defaults=(2250, 1625, 1000)
)
FanState = namedtuple("FanState", "Humidity Temp Light RPM Mode")
HeatDistributorSettings = namedtuple(
    "HeatDistributorSettings", "TemperatureLimit FanSpeedBelow FanSpeedAbove"
)
LightSensorSettings = namedtuple("LightSensorSettings", "DelayedStart RunningTime")
Sensitivity = namedtuple("Sensitivity", "HumidityOn Humidity LightOn Light")
SilentHours = namedtuple(
    "SilentHours", "On StartingHour StartingMinute EndingHour EndingMinute"
)
TrickleDays = namedtuple("TrickleDays", "Weekdays Weekends")


class Calima(BaseDevice):
    def __init__(self, hass, mac, pin):
        super().__init__(hass, mac, pin)

        self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES] = (
            "f508408a-508b-41c6-aa57-61d1fd0d5c39"
        )
        self.chars[CHARACTERISTIC_BASIC_VENTILATION] = (
            "faa49e09-a79c-4725-b197-bdc57c67dc32"
        )
        self.chars[CHARACTERISTIC_LEVEL_OF_FAN_SPEED] = (
            "1488a757-35bc-4ec8-9a6b-9ecf1502778e"
        )
        self.chars[CHARACTERISTIC_NIGHT_MODE] = "b5836b55-57bd-433e-8480-46e4993c5ac0"
        self.chars[CHARACTERISTIC_SENSITIVITY] = "e782e131-6ce1-4191-a8db-f4304d7610f1"
        self.chars[CHARACTERISTIC_SENSOR_DATA] = "528b80e8-c47a-4c0a-bdf1-916a7748f412"
        self.chars[CHARACTERISTIC_TEMP_HEAT_DISTRIBUTOR] = (
            "a22eae12-dba8-49f3-9c69-1721dcff1d96"
        )
        self.chars[CHARACTERISTIC_TIME_FUNCTIONS] = (
            "49c616de-02b1-4b67-b237-90f66793a6f2"
        )

    ################################################
    ############## STATE / SENSOR DATA #############
    ################################################
    async def getState(self) -> FanState:
        # Short Short Short Short    Byte Short Byte
        # Hum   Temp  Light FanSpeed Mode Tbd   Tbd
        v = unpack(
            "<4HBHB", await self._readUUID(self.chars[CHARACTERISTIC_SENSOR_DATA])
        )
        _LOGGER.debug("Read Fan States: %s", v)

        trigger = "No trigger"
        if ((v[4] >> 4) & 1) == 1:
            trigger = "Boost"
        elif ((v[4] >> 6) & 3) == 3:
            trigger = "Switch"
        elif (v[4] & 3) == 1:
            trigger = "Trickle ventilation"
        elif (v[4] & 3) == 2:
            trigger = "Light ventilation"
        elif (
            v[4] & 3
        ) == 3:  # Note that the trigger might be active, but mode must be enabled to be activated
            trigger = "Humidity ventilation"

        return FanState(
            round(math.log2(v[0] - 30) * 10, 2) if v[0] > 30 else 0,
            v[1] / 4 - 2.6,
            v[2],
            v[3],
            trigger,
        )

    ################################################
    ############ CONFIGURATION FUNCTIONS ###########
    ################################################
    async def getAutomaticCycles(self) -> int:
        v = unpack(
            "<B", await self._readUUID(self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES])
        )
        return v[0]

    async def setAutomaticCycles(self, setting: int) -> None:
        if setting < 0 or setting > 3:
            raise ValueError("Setting must be between 0-3")

        await self._writeUUID(
            self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES], pack("<B", setting)
        )

    async def getFanSpeedSettings(self) -> Fanspeeds:
        return Fanspeeds._make(
            unpack(
                "<HHH",
                await self._readUUID(self.chars[CHARACTERISTIC_LEVEL_OF_FAN_SPEED]),
            )
        )

    async def setFanSpeedSettings(
        self, humidity=2250, light=1625, trickle=1000
    ) -> None:
        for val in (humidity, light, trickle):
            if val % 25 != 0:
                raise ValueError("Speeds should be multiples of 25")
            if val > 2500 or val < 0:
                raise ValueError("Speeds must be between 0 and 2500 rpm")

        _LOGGER.debug("Calima setFanSpeedSettings: %s %s %s", humidity, light, trickle)

        await self._writeUUID(
            self.chars[CHARACTERISTIC_LEVEL_OF_FAN_SPEED],
            pack("<HHH", humidity, light, trickle),
        )

    async def getHeatDistributor(self) -> HeatDistributorSettings:
        return HeatDistributorSettings._make(
            unpack(
                "<BHH",
                await self._readUUID(self.chars[CHARACTERISTIC_TEMP_HEAT_DISTRIBUTOR]),
            )
        )

    async def getSilentHours(self) -> SilentHours:
        return SilentHours._make(
            unpack("<5B", await self._readUUID(self.chars[CHARACTERISTIC_NIGHT_MODE]))
        )

    async def setSilentHours(
        self, on: bool, startingTime: datetime.time, endingTime: datetime.time
    ) -> None:
        _LOGGER.debug(
            "Writing silent hours %s %s %s %s",
            startingTime.hour,
            startingTime.minute,
            endingTime.hour,
            endingTime.minute,
        )
        value = pack(
            "<5B",
            int(on),
            startingTime.hour,
            startingTime.minute,
            endingTime.hour,
            endingTime.minute,
        )
        await self._writeUUID(self.chars[CHARACTERISTIC_NIGHT_MODE], value)

    async def getTrickleDays(self) -> TrickleDays:
        return TrickleDays._make(
            unpack(
                "<2B",
                await self._readUUID(self.chars[CHARACTERISTIC_BASIC_VENTILATION]),
            )
        )

    async def setTrickleDays(self, weekdays, weekends) -> None:
        await self._writeUUID(
            self.chars[CHARACTERISTIC_BASIC_VENTILATION],
            pack("<2B", weekdays, weekends),
        )

    async def getLightSensorSettings(self) -> LightSensorSettings:
        return LightSensorSettings._make(
            unpack(
                "<2B", await self._readUUID(self.chars[CHARACTERISTIC_TIME_FUNCTIONS])
            )
        )

    async def setLightSensorSettings(self, delayed, running) -> None:
        if delayed not in (0, 5, 10):
            raise ValueError("Delayed must be 0, 5 or 10 minutes")
        if running not in (5, 10, 15, 30, 60):
            raise ValueError("Running time must be 5, 10, 15, 30 or 60 minutes")

        await self._writeUUID(
            self.chars[CHARACTERISTIC_TIME_FUNCTIONS], pack("<2B", delayed, running)
        )

    async def getSensorsSensitivity(self) -> Sensitivity:
        # Hum Active | Hum Sensitivity | Light Active | Light Sensitivity
        # We fix so that Sensitivity = 0 if active = 0
        l = Sensitivity._make(
            unpack("<4B", await self._readUUID(self.chars[CHARACTERISTIC_SENSITIVITY]))
        )

        return Sensitivity._make(
            unpack(
                "<4B",
                bytearray(
                    [
                        l.HumidityOn,
                        l.HumidityOn and l.Humidity,
                        l.LightOn,
                        l.LightOn and l.Light,
                    ]
                ),
            )
        )

    async def setSensorsSensitivity(self, humidity, light) -> None:
        if humidity > 3 or humidity < 0:
            raise ValueError("Humidity sensitivity must be between 0-3")
        if light > 3 or light < 0:
            raise ValueError("Light sensitivity must be between 0-3")

        value = pack("<4B", bool(humidity), humidity, bool(light), light)
        await self._writeUUID(self.chars[CHARACTERISTIC_SENSITIVITY], value)
