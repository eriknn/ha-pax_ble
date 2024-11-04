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

    @override
    async def getState(self) -> FanState:
        # FanState = namedtuple("FanState", "Humidity Temp Light RPM Mode")
        # We probably have to modify the FanState object as the fans have different sensors....
        # This also means we must vary which entities to create etc...


        # Byte  Byte    Short Short Short Short    Byte Byte Byte Byte  Byte
        # Trg1  Trg2    Hum   Gas   Light FanSpeed Tbd  Tbd  Tbd  Temp? Tbd
        v = unpack("<2B4HBBBBB", await self._readUUID(self.device.chars[CHARACTERISTIC_SENSOR_DATA]))
        _LOGGER.debug("Read Fan States: %s", v)

        # Needs to be figured out
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
            round(math.log2(v[2] - 30) * 10, 2) if v[2] > 30 else 0,
            v[9],
            v[4],
            v[5],
            trigger
        )