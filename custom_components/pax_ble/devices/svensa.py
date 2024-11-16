import logging
import math

from .characteristics import *
from .base_device import BaseDevice

from collections import namedtuple
from struct import pack, unpack
from typing import override

_LOGGER = logging.getLogger(__name__)

# Tuples specifically For Svensa
AutomaticCycles = namedtuple("AutomaticCycles", "Active Hour TimeMin Speed")
ConstantOperation = namedtuple("ConstantOperation", "Active Speed")
FanState = namedtuple("FanState", "Humidity AirQuality Temp Light RPM Mode")
Humidity = namedtuple("Humidity", "Active Level Speed")
TimeFunctions = namedtuple("TimeFunctions", "PresenceTime TimeActive TimeMin Speed")
PresenceGas = namedtuple("PresenceGas", "PresenceActive PresenceLevel GasActive GasLevel")

class Svensa(BaseDevice):
    def __init__(self, hass, mac, pin):
        super().__init__(hass, mac, pin)

        # Update characteristics used in base device
        self.chars.update({
            CHARACTERISTIC_BOOST: "7c4adc07-2f33-11e7-93ae-92361f002671",
            CHARACTERISTIC_MODE: "7c4adc0d-2f33-11e7-93ae-92361f002671",
            CHARACTERISTIC_MODEL_NUMBER: "00002a24-0000-1000-8000-00805f9b34fb",         # Not used
        })

        # Update charateristics used in this file
        self.chars.update({
            CHARACTERISTIC_AUTOMATIC_CYCLES: "7c4adc05-2f33-11e7-93ae-92361f002671",
            CHARACTERISTIC_TIME_FUNCTIONS: "7c4adc04-2f33-11e7-93ae-92361f002671"
        })

        # Add characteristics secific for Svensa
        self.chars.update({
            CHARACTERISTIC_HUMIDITY: "7c4adc01-2f33-11e7-93ae-92361f002671",             # humActive, humLevel, fanSpeed
            CHARACTERISTIC_CONSTANT_OPERATION: "7c4adc03-2f33-11e7-93ae-92361f002671",
            CHARACTERISTIC_PRESENCE_GAS: "7c4adc02-2f33-11e7-93ae-92361f002671"
        })        

    ################################################
    ############## STATE / SENSOR DATA #############
    ################################################
    async def getState(self) -> FanState:
        # Byte  Byte    Short Short Short Short    Byte Byte Byte Byte  Byte
        # Trg1  Trg2    Hum   Gas   Light FanSpeed Tbd  Tbd  Tbd  Temp? Tbd
        v = unpack("<2B4HBBBBB", await self._readUUID(self.chars[CHARACTERISTIC_SENSOR_DATA]))
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
            round(15*math.log2(v[2]) - 75, 2) if v[2] > 35 else 0,
            v[3],
            v[9],
            v[4],
            v[5],
            trigger
        )

    ################################################
    ############ CONFIGURATION FUNCTIONS ###########
    ################################################
    async def getAutomaticCycles(self) -> AutomaticCycles:
        return AutomaticCycles._make(
            unpack("<3BH", await self._readUUID(self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES]))
        )

    async def setAutomaticCycles(self, active:bool, hour:int, timeMin:int, speed:int) -> None:
        if timeMin < 0 or timeMin > 3:
            raise ValueError("Setting must be between 0-3")

        await self._writeUUID(self.chars[CHARACTERISTIC_AUTOMATIC_CYCLES], pack("<3BH", active, hour, timeMin, speed))

    async def getConstantOperation(self) -> ConstantOperation:
        v = unpack("<BH", await self._readUUID(self.chars[CHARACTERISTIC_CONSTANT_OPERATION]))
        _LOGGER.debug("Read Constant Operation settings: %s", v)

        #ConstantOperation = namedtuple("ConstantOperation", "Active Speed")
        return ConstantOperation(v[0], v[1])
    
    async def setConstantOperation(self, active:bool, speed:int) -> None:
        _LOGGER.debug("Write Constant Operation settings")

        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")
        if not active:
            speed = 0

        await self._writeUUID(self.chars[CHARACTERISTIC_CONSTANT_OPERATION], pack("<BH", active, speed))

    async def getHumidity(self) -> Humidity:
        v = unpack("<BBH", await self._readUUID(self.chars[CHARACTERISTIC_HUMIDITY]))
        _LOGGER.debug("Read Fan Humidity settings: %s", v)

        # Humidity = namedtuple("Humidity", "Active Level Speed")
        return Humidity(v[0], v[1], v[2])
    
    async def setHumidity(self, active:bool, level:int, speed:int) -> None:
        _LOGGER.debug("Write Fan Humidity settings")

        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")
        if not active:
            level = 0
            speed = 0

        await self._writeUUID(self.chars[CHARACTERISTIC_HUMIDITY], pack("<BBH", active, level, speed))
    
    async def getPresenceGas(self) -> PresenceGas:
        # Pres Active | Pres Sensitivity | Gas Active | Gas Sensitivity
        # We fix so that Sensitivity = 0 if active = 0
        l = PresenceGas._make(unpack("<4B", await self._readUUID(self.chars[CHARACTERISTIC_PRESENCE_GAS])))

        return PresenceGas._make(
            unpack( "<4B",bytearray([
                l.PresenceActive,
                l.PresenceActive and l.PresenceLevel,
                l.GasActive,
                l.GasActive and l.GasLevel]),
            )
        )

    async def setPresenceGas(self, presence_active:bool, presence_level:int, gas_active:bool, gas_level:int) -> None:
        _LOGGER.debug("Write Fan Presence/Gas settings")

        if not presence_active:
            presence_level = 0
        if not gas_active:
            gas_level = 0

        await self._writeUUID(self.chars[CHARACTERISTIC_PRESENCE_GAS], pack("<4B", presence_active, presence_level, gas_active, gas_level))

    async def getTimeFunctions(self) -> TimeFunctions:
        return TimeFunctions._make(
            unpack("<3BH", await self._readUUID(self.chars[CHARACTERISTIC_TIME_FUNCTIONS]))
        )

    async def setTimeFunctions(self, presenceTime, timeActive, timeMin, speed) -> None:
        if presenceTime not in (0, 5, 10):
            raise ValueError("presenceTime must be 0, 5 or 10 minutes")
        if timeActive not in (5, 10, 15, 30, 60):
            raise ValueError("timeActive must be 5, 10, 15, 30 or 60 minutes")
        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")

        await self._writeUUID(
            self.chars[CHARACTERISTIC_TIME_FUNCTIONS], pack("<3BH", presenceTime, timeActive, timeMin, speed)
        )