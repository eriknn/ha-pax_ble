from .characteristics import *
from .base_device import BaseDevice

class Svara(BaseDevice):
    def __init__(self):
        super().__init__()

        # Specific to Svara
        self.chars.update({
            CHARACTERISTIC_MODEL_NAME: "updated-calima-led-uuid"
        })