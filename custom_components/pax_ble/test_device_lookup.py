"""Unit tests for device_lookup (no Home Assistant runtime required)."""

import importlib.util
import pathlib
import unittest

_MODULE_PATH = pathlib.Path(__file__).with_name("device_lookup.py")
_SPEC = importlib.util.spec_from_file_location("device_lookup", _MODULE_PATH)
device_lookup = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(device_lookup)

device_in_map = device_lookup.device_in_map
_CONF_MAC = device_lookup._CONF_MAC


def _format_mac(mac: str) -> str:
    """Minimal stand-in for homeassistant.helpers.device_registry.format_mac."""
    return mac.lower()


class DeviceInMapTests(unittest.TestCase):
    def test_empty_devices(self):
        self.assertFalse(device_in_map(None, "aa:bb:cc:dd:ee:ff", _format_mac))
        self.assertFalse(device_in_map({}, "aa:bb:cc:dd:ee:ff", _format_mac))

    def test_matches_dict_key_case_insensitive(self):
        devices = {
            "AA:BB:CC:DD:EE:FF": {_CONF_MAC: "AA:BB:CC:DD:EE:FF", "name": "Fan"},
        }
        self.assertTrue(device_in_map(devices, "aa:bb:cc:dd:ee:ff", _format_mac))

    def test_matches_stored_conf_mac_when_key_differs(self):
        devices = {
            "legacy-key": {_CONF_MAC: "AA:BB:CC:DD:EE:FF", "name": "Fan"},
        }
        self.assertTrue(device_in_map(devices, "aa:bb:cc:dd:ee:ff", _format_mac))

    def test_no_match(self):
        devices = {
            "AA:BB:CC:DD:EE:01": {_CONF_MAC: "AA:BB:CC:DD:EE:01", "name": "Fan"},
        }
        self.assertFalse(device_in_map(devices, "aa:bb:cc:dd:ee:02", _format_mac))


if __name__ == "__main__":
    unittest.main()
