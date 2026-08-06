"""Regression test for issue #101: validation failure must disconnect.

Run: python3 tests/test_validate_connection_disconnect.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


ROOT = Path(__file__).resolve().parents[1]

# Minimal stubs so base_device imports without Home Assistant installed.
homeassistant = types.ModuleType("homeassistant")
homeassistant.__path__ = []
components = types.ModuleType("homeassistant.components")
components.__path__ = []
bluetooth = types.ModuleType("homeassistant.components.bluetooth")
bluetooth.async_ble_device_from_address = MagicMock()
sys.modules.update(
    {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.bluetooth": bluetooth,
    }
)

brc = types.ModuleType("bleak_retry_connector")
brc.BleakClientWithServiceCache = object
brc.close_stale_connections = AsyncMock()
brc.establish_connection = AsyncMock()
sys.modules["bleak_retry_connector"] = brc

bleak = types.ModuleType("bleak")
bleak_exc = types.ModuleType("bleak.exc")
bleak_exc.BleakError = Exception
sys.modules["bleak"] = bleak
sys.modules["bleak.exc"] = bleak_exc

# Namespace packages so we can load devices modules without pax_ble/__init__.py.
for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.pax_ble", ROOT / "custom_components/pax_ble"),
    ("custom_components.pax_ble.devices", ROOT / "custom_components/pax_ble/devices"),
):
    mod = types.ModuleType(name)
    mod.__path__ = [str(path)]
    sys.modules[name] = mod


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "custom_components/pax_ble" / relative
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("custom_components.pax_ble.devices.characteristics", "devices/characteristics.py")
base_device = _load(
    "custom_components.pax_ble.devices.base_device", "devices/base_device.py"
)
CHARACTERISTIC_DEVICE_NAME = base_device.CHARACTERISTIC_DEVICE_NAME
BaseDevice = base_device.BaseDevice


class FakeDevice(BaseDevice):
    """Concrete BaseDevice for unit tests."""

    def __init__(self):
        self._hass = MagicMock()
        self._mac = "aa:bb:cc:dd:ee:ff"
        self._pin = None
        self._connect_lock = asyncio.Lock()
        self._disconnect_callback = None
        self.chars = {CHARACTERISTIC_DEVICE_NAME: CHARACTERISTIC_DEVICE_NAME}
        self._client = None


class ValidateConnectionDisconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_failure_calls_disconnect(self):
        device = FakeDevice()
        client = MagicMock()
        client.is_connected = True
        client.read_gatt_char = AsyncMock(
            side_effect=Exception("Characteristic not found")
        )
        client.disconnect = AsyncMock()
        device._client = client

        ok = await device.validate_connection()

        self.assertFalse(ok)
        client.disconnect.assert_awaited_once()
        self.assertIsNone(device._client)

    async def test_validation_success_keeps_client(self):
        device = FakeDevice()
        client = MagicMock()
        client.is_connected = True
        client.read_gatt_char = AsyncMock(return_value=b"Vent-Axia Svara")
        client.disconnect = AsyncMock()
        device._client = client

        ok = await device.validate_connection()

        self.assertTrue(ok)
        client.disconnect.assert_not_awaited()
        self.assertIs(device._client, client)


if __name__ == "__main__":
    unittest.main()
