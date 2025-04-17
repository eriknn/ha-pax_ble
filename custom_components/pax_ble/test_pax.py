import asyncio
import platform
import sys
import logging
from struct import pack, unpack
from bleak import BleakClient

CHARACTERISTIC_DEVICE_NAME = "00002a00-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_FAN_DESCRIPTION = "b85fa07a-9382-4838-871c-81d045dcc2ff"
CHARACTERISTIC_FIRMWARE_REVISION = "00002a26-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_HARDWARE_REVISION = "00002a27-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_SOFTWARE_REVISION = "00002a28-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_MODEL_NAME = "00002a00-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_MODEL_NUMBER = "00002a24-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_SENSOR_DATA = "528b80e8-c47a-4c0a-bdf1-916a7748f412"

logger = logging.getLogger(__name__)
ADDRESS = "58:2b:db:c8:f3:8a"


async def main():
    async with BleakClient(ADDRESS) as client:
        result = bytes(await client.read_gatt_char(CHARACTERISTIC_SENSOR_DATA))
        print(len(result))
        v = unpack("<" + str(len(result)) + "B", result)
        print(v)
        v = unpack("<4HBHB", result)
        print(v)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
