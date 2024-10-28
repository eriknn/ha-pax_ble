from .characteristics import *
from .base_device import BaseDevice

class Svensa(BaseDevice):
    def __init__(self):
        super().__init__()

        # Specific to Svensa
        self.chars.update({
            # This is same as base class, just an example on how to update value
            CHARACTERISTIC_MODEL_NAME: "00002a00-0000-1000-8000-00805f9b34fb"
        })