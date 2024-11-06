import logging
import math

from .characteristics import *
from .base_device import BaseDevice, FanState

from struct import pack, unpack
from typing import override

_LOGGER = logging.getLogger(__name__)

class Svensa(BaseDevice):
    def __init__(self, hass, mac, pin):
        super().__init__(hass, mac, pin)

        # Specific to Svansa
        self.chars.update({
            CHARACTERISTIC_AUTOMATIC_CYCLES: "7c4adc05-2f33-11e7-93ae-92361f002671",
            CHARACTERISTIC_BOOST: "7c4adc07-2f33-11e7-93ae-92361f002671",
            CHARACTERISTIC_MODE: "7c4adc0d-2f33-11e7-93ae-92361f002671",
            CHARACTERISTIC_MODEL_NUMBER: "00002a24-0000-1000-8000-00805f9b34fb"         # Not used
        })

    @override
    async def getState(self) -> FanState:
        # We probably have to modify the FanState object as the fans have different sensors....
        # This also means we must vary which entities to create etc...

        # Byte  Byte    Short Short Short Short    Byte Byte Byte Byte  Byte
        # Trg1  Trg2    Hum   Gas   Light FanSpeed Tbd  Tbd  Tbd  Temp? Tbd
        v = unpack("<2B4HBBBBB", await self._readUUID(self.chars[CHARACTERISTIC_SENSOR_DATA]))
        _LOGGER.debug("Read Fan States: %s", v)

        # Found in package com.component.svara.views.calima.SkyModeView
        trigger = "No trigger"
        trg_value = v[1] % 16
        if trg_value != 11:
            match trg_value:
                case 0:
                    trigger = "Constant Speed"
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

        # FanState = namedtuple("FanState", "Humidity Temp Light RPM Mode")
        return FanState(
            round(15*math.log2(v[2]) - 75, 2) if v[2] > 35 else 0,
            v[9],
            v[4],
            v[5],
            trigger
        )