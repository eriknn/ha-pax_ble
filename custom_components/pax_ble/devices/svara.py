from .characteristics import *
from .base_device import BaseDevice

class Svara(BaseDevice):
    def __init__(self, hass, mac, pin):
        super().__init__(hass, mac, pin)

        # Specific to Svara
        self.chars.update({
            # This is same as base class, just an example on how to update value
            CHARACTERISTIC_MODEL_NAME: "00002a00-0000-1000-8000-00805f9b34fb"
        })