"""Unit tests for PARTS_PER_MILLION compat shim (no full HA runtime)."""

import importlib.util
import pathlib
import re
import sys
import types
import unittest

_ENUM_SENTINEL = "from-enum"
_LEGACY_SENTINEL = "from-legacy"


def _load_parts_per_million(has_unit_of_ratio: bool) -> str:
    """Load const.PARTS_PER_MILLION with a mocked homeassistant.const."""
    tag = "ratio" if has_unit_of_ratio else "legacy"
    ha_const = types.ModuleType(f"homeassistant.const.{tag}")
    ha_const.CONCENTRATION_PARTS_PER_MILLION = _LEGACY_SENTINEL
    if has_unit_of_ratio:
        class UnitOfRatio:
            PARTS_PER_MILLION = _ENUM_SENTINEL

        ha_const.UnitOfRatio = UnitOfRatio

    class Platform:
        TIME = "time"
        SENSOR = "sensor"
        SWITCH = "switch"
        NUMBER = "number"
        SELECT = "select"

    ha_const.Platform = Platform

    ha = types.ModuleType(f"homeassistant.{tag}")
    ha.const = ha_const
    sys.modules[f"homeassistant.{tag}"] = ha
    sys.modules[f"homeassistant.const.{tag}"] = ha_const

    path = pathlib.Path(__file__).with_name("const.py")
    source = path.read_text().replace(
        "from homeassistant.const import Platform",
        f"from homeassistant.const.{tag} import Platform",
    )
    source = source.replace(
        "from homeassistant.const import UnitOfRatio",
        f"from homeassistant.const.{tag} import UnitOfRatio",
    )
    source = source.replace(
        "from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION",
        f"from homeassistant.const.{tag} import CONCENTRATION_PARTS_PER_MILLION",
    )

    module_name = f"pax_ble_const_{tag}"
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(source, module.__dict__)  # noqa: S102 - controlled test fixture source
    return module.PARTS_PER_MILLION


_SENSOR_UNIT_OF_RATIO_IMPORT = re.compile(
    r"from\s+homeassistant\.const\s+import\s+(?:UnitOfRatio|.*\bUnitOfRatio\b)"
)


class PartsPerMillionCompatTests(unittest.TestCase):
    def test_uses_unit_of_ratio_when_available(self):
        self.assertEqual(_load_parts_per_million(True), _ENUM_SENTINEL)

    def test_falls_back_without_unit_of_ratio(self):
        self.assertEqual(_load_parts_per_million(False), _LEGACY_SENTINEL)

    def test_sensor_does_not_import_unit_of_ratio_directly(self):
        """Regression guard for #142: sensor.py must use const.PARTS_PER_MILLION."""
        source = pathlib.Path(__file__).with_name("sensor.py").read_text()
        self.assertIsNone(_SENSOR_UNIT_OF_RATIO_IMPORT.search(source))
        self.assertIn("PARTS_PER_MILLION", source)


if __name__ == "__main__":
    unittest.main()
