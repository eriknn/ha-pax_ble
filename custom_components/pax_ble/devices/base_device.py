from .characteristics import *

from homeassistant.components import bluetooth
from struct import pack, unpack
import datetime
from bleak import BleakClient
from bleak.exc import BleakError
import binascii
from collections import namedtuple
import logging

_LOGGER = logging.getLogger(__name__)

Time = namedtuple("Time", "DayOfWeek Hour Minute Second")
BoostMode = namedtuple("BoostMode", "OnOff Speed Seconds")

class BaseDevice():
    def __init__(self, hass, mac, pin):
        self._hass = hass
        self._mac = mac
        self._pin = pin
        self._dev = None

        self.chars = {
            CHARACTERISTIC_APPEARANCE: "00002a01-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_BOOST: "118c949c-28c8-4139-b0b3-36657fd055a9",
            CHARACTERISTIC_CLOCK: "6dec478e-ae0b-4186-9d82-13dda03c0682",
            CHARACTERISTIC_DEVICE_NAME: "00002a00-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_FACTORY_SETTINGS_CHANGED: "63b04af9-24c0-4e5d-a69c-94eb9c5707b4",
            CHARACTERISTIC_FAN_DESCRIPTION: "b85fa07a-9382-4838-871c-81d045dcc2ff",
            CHARACTERISTIC_FIRMWARE_REVISION: "00002a26-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_HARDWARE_REVISION: "00002a27-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_SOFTWARE_REVISION: "00002a28-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_LED: "8b850c04-dc18-44d2-9501-7662d65ba36e",
            CHARACTERISTIC_MANUFACTURER_NAME: "00002a29-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_MODE: "90cabcd1-bcda-4167-85d8-16dcd8ab6a6b",
            CHARACTERISTIC_MODEL_NUMBER: "00002a24-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_PIN_CODE: "4cad343a-209a-40b7-b911-4d9b3df569b2",
            CHARACTERISTIC_PIN_CONFIRMATION: "d1ae6b70-ee12-4f6d-b166-d2063dcaffe1",
            CHARACTERISTIC_RESET: "ff5f7c4f-2606-4c69-b360-15aaea58ad5f",
            CHARACTERISTIC_SENSOR_DATA: "528b80e8-c47a-4c0a-bdf1-916a7748f412",
            CHARACTERISTIC_SERIAL_NUMBER: "00002a25-0000-1000-8000-00805f9b34fb",  # Not used
            CHARACTERISTIC_STATUS: "25a824ad-3021-4de9-9f2f-60cf8d17bded",
        }

    async def authorize(self):
        await self.setAuth(self._pin)

    async def connect(self, retries=3) -> bool:
        if self.isConnected():
            return True

        tries = 0

        _LOGGER.debug("Connecting to %s", self._mac)
        while tries < retries:
            tries += 1

            try:
                d = bluetooth.async_ble_device_from_address(
                    self._hass, self._mac.upper()
                )
                if not d:
                    raise BleakError(
                        f"A device with address {self._mac} could not be found."
                    )
                self._dev = BleakClient(d)
                ret = await self._dev.connect()
                if ret:
                    _LOGGER.debug("Connected to %s", self._mac)
                    break
            except Exception as e:
                if tries == retries:
                    _LOGGER.info("Not able to connect to %s! %s", self._mac, str(e))
                else:
                    _LOGGER.debug("Retrying %s", self._mac)

        return self.isConnected()

    async def disconnect(self) -> None:
        if self._dev is not None:
            try:
                await self._dev.disconnect()
            except Exception as e:
                _LOGGER.info("Error disconnecting from %s! %s", self._mac, str(e))
            self._dev = None

    async def pair(self) -> str:
        raise NotImplementedError("Pairing not availiable for this device type.")

    def isConnected(self) -> bool:
        return self._dev is not None and self._dev.is_connected

    def _bToStr(self, val) -> str:
        return binascii.b2a_hex(val).decode("utf-8")

    async def _readUUID(self, uuid) -> bytearray:
        val = await self._dev.read_gatt_char(uuid)
        return val

    async def _readHandle(self, handle) -> bytearray:
        val = await self._dev.read_gatt_char(char_specifier=handle)
        return val

    async def _writeUUID(self, uuid, val) -> None:
        await self._dev.write_gatt_char(char_specifier=uuid, data=val, response=True)

    # --- Generic GATT Characteristics
    async def getDeviceName(self) -> str:
        #return (await self._readHandle(0x2)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_DEVICE_NAME])).decode("ascii")

    async def getModelNumber(self) -> str:
        #return (await self._readHandle(0xD)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_MODEL_NUMBER])).decode("ascii")

    async def getSerialNumber(self) -> str:
        #return (await self._readHandle(0xB)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_SERIAL_NUMBER])).decode("ascii")

    async def getHardwareRevision(self) -> str:
        #return (await self._readHandle(0xF)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_HARDWARE_REVISION])).decode("ascii")

    async def getFirmwareRevision(self) -> str:
        #return (await self._readHandle(0x11)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_FIRMWARE_REVISION])).decode("ascii")

    async def getSoftwareRevision(self) -> str:
        #return (await self._readHandle(0x13)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_SOFTWARE_REVISION])).decode("ascii")

    async def getManufacturer(self) -> str:
        #return (await self._readHandle(0x15)).decode("ascii")
        return (await self._readUUID(self.chars[CHARACTERISTIC_MANUFACTURER_NAME])).decode("ascii")

    # --- Onwards to PAX characteristics
    async def setAuth(self, pin) -> None:
        _LOGGER.debug(f"Connecting with pin: {pin}")
        await self._writeUUID(self.chars[CHARACTERISTIC_PIN_CODE], pack("<I", int(pin)))

        result = await self.checkAuth()
        _LOGGER.debug(f"Authorized: {result}")

    async def checkAuth(self) -> bool:
        v = unpack("<b", await self._readUUID(self.chars[CHARACTERISTIC_PIN_CONFIRMATION]))
        return bool(v[0])

    async def setAlias(self, name) -> None:
        await self._writeUUID(
            self.chars[CHARACTERISTIC_FAN_DESCRIPTION], pack("20s", bytearray(name, "utf-8"))
        )

    async def getAlias(self)-> str:
        return await self._readUUID(self.chars[CHARACTERISTIC_FAN_DESCRIPTION]).decode("utf-8")

    async def getIsClockSet(self) -> str:
        return self._bToStr(await self._readUUID(self.chars[CHARACTERISTIC_STATUS]))

    async def getFactorySettingsChanged(self) -> bool:
        v = unpack("<?", await self._readUUID(self.chars[CHARACTERISTIC_FACTORY_SETTINGS_CHANGED]))
        return v[0]

    async def getLed(self) -> str:
        return self._bToStr(await self._readUUID(self.chars[CHARACTERISTIC_LED]))

    async def setTime(self, dayofweek, hour, minute, second) -> None:
        await self._writeUUID(
            self.chars[CHARACTERISTIC_CLOCK], pack("<4B", dayofweek, hour, minute, second)
        )

    async def getTime(self) -> Time:
        return Time._make(unpack("<BBBB", await self._readUUID(self.chars[CHARACTERISTIC_CLOCK])))

    async def setTimeToNow(self) -> None:
        now = datetime.datetime.now()
        await self.setTime(now.isoweekday(), now.hour, now.minute, now.second)

    async def getReset(self):  # Should be write
        return await self._readUUID(self.chars[CHARACTERISTIC_RESET])

    async def resetDevice(self):  # Dangerous
        await self._writeUUID(self.chars[CHARACTERISTIC_RESET], pack("<I", 120))

    async def resetValues(self):  # Dangerous
        await self._writeUUID(self.chars[CHARACTERISTIC_RESET], pack("<I", 85))

    ####################################
    #### COMMON FAN SPECIFIC VALUES ####
    ####################################
    async def getBoostMode(self) -> BoostMode:
        v = unpack("<BHH", await self._readUUID(self.chars[CHARACTERISTIC_BOOST]))
        return BoostMode._make(v)

    async def setBoostMode(self, on, speed, seconds) -> None:
        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")
        if not on:
            speed = 0
            seconds = 0

        await self._writeUUID(self.chars[CHARACTERISTIC_BOOST], pack("<BHH", on, speed, seconds))

    async def getMode(self) -> str:
        v = unpack("<B", await self._readUUID(self.chars[CHARACTERISTIC_MODE]))
        if v[0] == 0:
            return "MultiMode"
        elif v[0] == 1:
            return "DraftShutterMode"
        elif v[0] == 2:
            return "WallSwitchExtendedRuntimeMode"
        elif v[0] == 3:
            return "WallSwitchNoExtendedRuntimeMode"
        elif v[0] == 4:
            return "HeatDistributionMode"
        else:
            return "Unknown: " + str(v[0])