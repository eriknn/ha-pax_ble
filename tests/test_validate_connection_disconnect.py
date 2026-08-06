"""Regression tests for connection validation (#101 / PR #111).

Run: python3 tests/test_validate_connection_disconnect.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


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


class BleakError(Exception):
    pass


bleak_exc.BleakError = BleakError
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
CHARACTERISTIC_SENSOR_DATA = base_device.CHARACTERISTIC_SENSOR_DATA
SENSOR_UUID = "528b80e8-c47a-4c0a-bdf1-916a7748f412"
BaseDevice = base_device.BaseDevice


class FakeDevice(BaseDevice):
    """Concrete BaseDevice for unit tests."""

    def __init__(self):
        self._hass = MagicMock()
        self._mac = "aa:bb:cc:dd:ee:ff"
        self._pin = None
        self._connect_lock = asyncio.Lock()
        self._disconnect_callback = None
        self.chars = {CHARACTERISTIC_SENSOR_DATA: SENSOR_UUID}
        self._client = None


def _services_with_sensor(include: bool = True):
    services = MagicMock()
    services.get_characteristic = MagicMock(
        return_value=MagicMock() if include else None
    )
    return services


class ValidateConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_validate_success_checks_services_not_gatt_read(self):
        device = FakeDevice()
        client = MagicMock()
        client.is_connected = True
        client.services = _services_with_sensor(True)
        client.read_gatt_char = AsyncMock()
        client.disconnect = AsyncMock()
        device._client = client

        ok = await device.validate_connection()

        self.assertTrue(ok)
        client.services.get_characteristic.assert_called_once_with(SENSOR_UUID)
        client.read_gatt_char.assert_not_awaited()
        client.disconnect.assert_not_awaited()

    async def test_validate_missing_sensor_disconnects(self):
        device = FakeDevice()
        client = MagicMock()
        client.is_connected = True
        client.services = _services_with_sensor(False)
        client.disconnect = AsyncMock()
        device._client = client

        ok = await device.validate_connection()

        self.assertFalse(ok)
        client.disconnect.assert_awaited_once()
        self.assertIsNone(device._client)

    async def test_validate_stale_not_connected_disconnects(self):
        device = FakeDevice()
        client = MagicMock()
        client.is_connected = False
        client.disconnect = AsyncMock()
        device._client = client

        ok = await device.validate_connection()

        self.assertFalse(ok)
        client.disconnect.assert_awaited_once()
        self.assertIsNone(device._client)

    async def test_connect_cache_retry_under_lock(self):
        device = FakeDevice()
        stale = MagicMock()
        stale.is_connected = True
        stale.services = _services_with_sensor(False)
        stale.clear_cache = AsyncMock()
        stale.disconnect = AsyncMock()

        fresh = MagicMock()
        fresh.is_connected = True
        fresh.services = _services_with_sensor(True)
        fresh.disconnect = AsyncMock()

        calls = []

        async def fake_establish(*args, **kwargs):
            calls.append(kwargs["use_services_cache"])
            return stale if len(calls) == 1 else fresh

        with patch.object(
            base_device.bluetooth,
            "async_ble_device_from_address",
            return_value=MagicMock(),
        ), patch.object(
            base_device, "close_stale_connections", new=AsyncMock()
        ), patch.object(
            base_device, "establish_connection", side_effect=fake_establish
        ):
            ok = await device.connect()

        self.assertTrue(ok)
        self.assertEqual(calls, [True, False])
        stale.clear_cache.assert_awaited_once()
        stale.disconnect.assert_awaited_once()
        self.assertIs(device._client, fresh)

    async def test_connect_no_cache_retry_when_uncached_still_missing(self):
        device = FakeDevice()
        client = MagicMock()
        client.is_connected = True
        client.services = _services_with_sensor(False)
        client.clear_cache = AsyncMock()
        client.disconnect = AsyncMock()

        with patch.object(
            base_device.bluetooth,
            "async_ble_device_from_address",
            return_value=MagicMock(),
        ), patch.object(
            base_device, "close_stale_connections", new=AsyncMock()
        ), patch.object(
            base_device, "establish_connection", new=AsyncMock(return_value=client)
        ):
            ok = await device.connect(use_services_cache=False)

        self.assertFalse(ok)
        client.clear_cache.assert_not_awaited()
        client.disconnect.assert_awaited()
        self.assertIsNone(device._client)

    async def test_connect_early_return_when_already_connected_with_sensor(self):
        device = FakeDevice()
        client = MagicMock()
        client.is_connected = True
        client.services = _services_with_sensor(True)
        device._client = client

        with patch.object(
            base_device, "establish_connection", new=AsyncMock()
        ) as establish:
            ok = await device.connect()

        self.assertTrue(ok)
        establish.assert_not_awaited()
        self.assertIs(device._client, client)

    async def test_connect_reconnects_when_already_connected_missing_sensor(self):
        device = FakeDevice()
        stale = MagicMock()
        stale.is_connected = True
        stale.services = _services_with_sensor(False)
        stale.clear_cache = AsyncMock()
        stale.disconnect = AsyncMock()
        device._client = stale

        fresh = MagicMock()
        fresh.is_connected = True
        fresh.services = _services_with_sensor(True)
        fresh.disconnect = AsyncMock()

        with patch.object(
            base_device.bluetooth,
            "async_ble_device_from_address",
            return_value=MagicMock(),
        ), patch.object(
            base_device, "close_stale_connections", new=AsyncMock()
        ), patch.object(
            base_device, "establish_connection", new=AsyncMock(return_value=fresh)
        ):
            ok = await device.connect()

        self.assertTrue(ok)
        stale.clear_cache.assert_awaited_once()
        stale.disconnect.assert_awaited()
        self.assertIs(device._client, fresh)


if __name__ == "__main__":
    unittest.main()
