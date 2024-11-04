from .characteristics import *
from .base_device import BaseDevice

class Calima(BaseDevice):
    def __init__(self, hass, mac, pin):
        super().__init__(hass, mac, pin)
        
        # This is the same as the base device