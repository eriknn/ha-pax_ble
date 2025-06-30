import asyncio
import logging
import math

from .characteristics import *
from .base_device import BaseDevice

from collections import namedtuple
from struct import pack, unpack

_LOGGER = logging.getLogger(__name__)

AutomaticCycles = namedtuple("AutomaticCycles", "Active Hour TimeMin Speed")
ConstantOperation = namedtuple("ConstantOperation", "Active Speed")
FanState = namedtuple("FanState", "Humidity AirQuality Temp Light RPM Mode")
Humidity = namedtuple("Humidity", "Active Level Speed")
TimerFunctions = namedtuple("TimerFunctions", "PresenceTime TimeActive TimeMin Speed")
PresenceGas = namedtuple(
    "PresenceGas", "PresenceActive PresenceLevel GasActive GasLevel"
)
Pause = namedtuple(
    "Pause", "PauseActive PauseMinutes"
)


class Svensa(BaseDevice):
    def __init__(self, hass, mac, pin):
        super().__init__(hass, mac, pin)

        # Update characteristics used in base device
        self.chars.update(
            {
                CHARACTERISTIC_BOOST: "7c4adc07-2f33-11e7-93ae-92361f002671",
                CHARACTERISTIC_MODE: "7c4adc0d-2f33-11e7-93ae-92361f002671",
                CHARACTERISTIC_MODEL_NUMBER: "00002a24-0000-1000-8000-00805f9b34fb",  # Not used
            }
        )

        # Update charateristics used in this device
        self.chars.update(
            {
                CHARACTERISTIC_AUTOMATIC_CYCLES: "7c4adc05-2f33-11e7-93ae-92361f002671",
                CHARACTERISTIC_TIME_FUNCTIONS: "7c4adc04-2f33-11e7-93ae-92361f002671",
            }
        )

        # Add characteristics specific for Svensa
        self.chars.update(
            {
                CHARACTERISTIC_HUMIDITY: "7c4adc01-2f33-11e7-93ae-92361f002671",  # humActive, humLevel, fanSpeed
                CHARACTERISTIC_CONSTANT_OPERATION: "7c4adc03-2f33-11e7-93ae-92361f002671",
                CHARACTERISTIC_PRESENCE_GAS: "7c4adc02-2f33-11e7-93ae-92361f002671",
                CHARACTERISTIC_PAUSE: "7C4ADC06-2F33-11E7-93AE-92361F002671",
            }
        )

    # Override base method, this should return the correct pin
    async def pair(self) -> str:
        for _ in range(5):
            await self.setAuth(0)
            if (pin := await self.getAuth()) != 0:
                return str(pin)
            await asyncio.sleep(5)

        raise RuntimeError("Failed to retrieve a valid PIN after 5 attempts")

    ################################################
    ############## STATE / SENSOR DATA #############
    ################################################
    async def getState(self) -> FanState:
        # Byte  Byte    Short Short Short Short    Byte Byte Byte Byte  Byte
        # Trg1  Trg2    Hum   Gas   Light FanSpeed Tbd  Tbd  Tbd  Temp? Tbd
        v = unpack(
            "<2B4H5B", await self._readUUID(self.chars[CHARACTERISTIC_SENSOR_DATA])
        )
        _LOGGER.debug("Read Fan States: %s", v)

        # Found in package com.component.svara.views.calima.SkyModeView
        trigger = "No trigger"

        if v[1] & 0x10:
            # Check 5th-last bit (and remaining = 0)
            trigger = "Constant Speed"
        else:
            # Check last 4 bits
            trg_value = v[1] & 0x0F
            if trg_value != 11:
                match trg_value:
                    case 0:
                        trigger = "Idle"
                    case 1:
                        trigger = "Humidity"
                    case 2:
                        trigger = "Light"
                    case 3:
                        trigger = "Timer"
                    case 4:
                        trigger = "Air Quality Sensor"
                    case 5:
                        trigger = "Airing"
                    case 6:
                        trigger = "Pause"
                    case 7:
                        trigger = "Boost"
                    case _:
                        trigger = "Timer"
            else:
                trigger = "Timer"

        # FanState = namedtuple("FanState", "Humidity AirQuality Temp Light RPM Mode")
        return FanState(
            round(15 * math.log2(v[2]) - 75, 2) if v[2] > 35 else 0,
            v[3],
            v[9],
            v[4],
            v[5],
            trigger,
        )

    ################################################
    ############ CONFIGURATION FUNCTIONS ###########
    ################################################
    async def getAutomaticCycles(self) -> AutomaticCycles:
        # Active | Hour | TimeMin | Speed
        l = AutomaticCycles._make(
            unpack(
                "<3BH",
                await self._readUUID(self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES]),
            )
        )

        # We fix so that TimeMin = 0 if Active = 0
        return AutomaticCycles(l.Active, l.Hour, l.TimeMin if l.Active else 0, l.Speed)

    async def setAutomaticCycles(self, hour: int, timeMin: int, speed: int) -> None:
        await self._writeUUID(
            self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES],
            pack("<3BH", timeMin > 0, hour, timeMin, speed),
        )

    async def getConstantOperation(self) -> ConstantOperation:
        v = unpack(
            "<BH", await self._readUUID(self.chars[CHARACTERISTIC_CONSTANT_OPERATION])
        )
        _LOGGER.debug("Read Constant Operation settings: %s", v)

        # ConstantOperation = namedtuple("ConstantOperation", "Active Speed")
        return ConstantOperation(v[0], v[1])

    async def setConstantOperation(self, active: bool, speed: int) -> None:
        _LOGGER.debug("Write Constant Operation settings")

        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")
        if not active:
            speed = 0

        await self._writeUUID(
            self.chars[CHARACTERISTIC_CONSTANT_OPERATION], pack("<BH", active, speed)
        )

    async def getHumidity(self) -> Humidity:
        v = unpack("<BBH", await self._readUUID(self.chars[CHARACTERISTIC_HUMIDITY]))
        _LOGGER.debug("Read Fan Humidity settings: %s", v)

        # Humidity = namedtuple("Humidity", "Active Level Speed")
        return Humidity(v[0], v[1], v[2])

    async def setHumidity(self, active: bool, level: int, speed: int) -> None:
        _LOGGER.debug("Write Fan Humidity settings")

        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")
        if not active:
            level = 0
            speed = 0

        await self._writeUUID(
            self.chars[CHARACTERISTIC_HUMIDITY], pack("<BBH", active, level, speed)
        )

    async def getPresenceGas(self) -> PresenceGas:
        # Pres Active | Pres Sensitivity | Gas Active | Gas Sensitivity
        # We fix so that Sensitivity = 0 if active = 0
        l = PresenceGas._make(
            unpack("<4B", await self._readUUID(self.chars[CHARACTERISTIC_PRESENCE_GAS]))
        )

        return PresenceGas._make(
            unpack(
                "<4B",
                bytearray(
                    [
                        l.PresenceActive,
                        l.PresenceActive and l.PresenceLevel,
                        l.GasActive,
                        l.GasActive and l.GasLevel,
                    ]
                ),
            )
        )

    async def setPresenceGas(
        self,
        presence_active: bool,
        presence_level: int,
        gas_active: bool,
        gas_level: int,
    ) -> None:
        _LOGGER.debug("Write Fan Presence/Gas settings")

        if not presence_active:
            presence_level = 0
        if not gas_active:
            gas_level = 0

        await self._writeUUID(
            self.chars[CHARACTERISTIC_PRESENCE_GAS],
            pack("<4B", presence_active, presence_level, gas_active, gas_level),
        )

    async def getPause(self) -> Pause:
        # Pause Active | Pause Minutes
        # When paused, Minutes indicates how many minutes are remaining.
        # When not paused, Minutes indicates the saved pause length.
        v = unpack("<BB", await self._readUUID(self.chars[CHARACTERISTIC_PAUSE]))
        return Pause(v[0], v[1])

    async def setPause(
        self,
        active: bool,
        duration: int,
    ) -> None:
        v = pack("<BB", active, duration)
        _LOGGER.debug("Write Pause")

        await self._writeUUID(
            self.chars[CHARACTERISTIC_PAUSE],
            v,
        )

    async def getTimerFunctions(self) -> TimerFunctions:
        # PresenceTime | TimeActive | TimeMin | Speed, we fix so that TimeMin (Delay Time) = 0 if TimeActive = 0
        l = TimerFunctions._make(
            unpack(
                "<3BH", await self._readUUID(self.chars[CHARACTERISTIC_TIME_FUNCTIONS])
            )
        )
        return TimerFunctions(l.PresenceTime, l.TimeActive, int(l.TimeActive and l.TimeMin), l.Speed)

    async def setTimerFunctions(
        self, presenceTimeMin, timeActive: bool, timeMin: int, speed: int
    ) -> None:
        if presenceTimeMin not in (5, 10, 15, 30, 60):
            raise ValueError("presenceTime must be 5, 10, 15, 30 or 60 minutes")
        if timeMin not in (0, 2, 4):
            raise ValueError("timeActive must be 0, 2 or 4 minutes")
        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")

        await self._writeUUID(
            self.chars[CHARACTERISTIC_TIME_FUNCTIONS],
            pack("<3BH", presenceTimeMin, timeActive, timeMin, speed),
        )
