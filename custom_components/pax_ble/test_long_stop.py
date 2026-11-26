"""Unit tests for long_stop (no Home Assistant runtime required)."""

import importlib.util
import pathlib
import unittest

_MODULE_PATH = pathlib.Path(__file__).with_name("long_stop.py")
_SPEC = importlib.util.spec_from_file_location("long_stop", _MODULE_PATH)
long_stop = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(long_stop)

LONG_STOP_KEYS = long_stop.LONG_STOP_KEYS
LONG_STOP_OFF = long_stop.LONG_STOP_OFF
saved_settings = long_stop.saved_settings
is_long_stopped = long_stop.is_long_stopped
long_stop_ended = long_stop.long_stop_ended

RUNNING = {
    "trickledays_weekdays": 1,
    "trickledays_weekends": 1,
    "sensitivity_humidity": 2,
    "sensitivity_light": 1,
    "automatic_cycles": 0,
}


class SavedSettingsTests(unittest.TestCase):
    def test_takes_only_long_stop_keys(self):
        state = dict(RUNNING, rpm=1200, fanspeed_trickle=900)
        self.assertEqual(saved_settings(state), RUNNING)

    def test_missing_key_is_none(self):
        state = dict(RUNNING)
        del state["automatic_cycles"]
        self.assertIsNone(saved_settings(state))

    def test_none_value_is_none(self):
        # Config not read yet: values are None in the coordinator state.
        self.assertIsNone(saved_settings(dict(RUNNING, sensitivity_light=None)))

    def test_restored_strings_become_ints(self):
        restored = {key: str(value) for key, value in RUNNING.items()}
        self.assertEqual(saved_settings(restored), RUNNING)

    def test_bools_become_ints(self):
        state = dict(RUNNING, trickledays_weekdays=True, trickledays_weekends=False)
        saved = saved_settings(state)
        self.assertEqual(saved["trickledays_weekdays"], 1)
        self.assertEqual(saved["trickledays_weekends"], 0)

    def test_garbage_is_none(self):
        self.assertIsNone(saved_settings(None))
        self.assertIsNone(saved_settings("{}"))
        self.assertIsNone(saved_settings(dict(RUNNING, automatic_cycles="Off")))
        self.assertIsNone(saved_settings(dict(RUNNING, automatic_cycles=-1)))


class IsLongStoppedTests(unittest.TestCase):
    def test_all_off(self):
        self.assertTrue(is_long_stopped(dict(LONG_STOP_OFF)))

    def test_one_on(self):
        for key in LONG_STOP_KEYS:
            with self.subTest(key=key):
                self.assertFalse(is_long_stopped(dict(LONG_STOP_OFF, **{key: 1})))

    def test_unknown_is_not_stopped(self):
        self.assertFalse(is_long_stopped({}))


class LongStopEndedTests(unittest.TestCase):
    def test_not_stopped_never_ends(self):
        self.assertFalse(long_stop_ended(0, RUNNING))

    def test_all_still_off(self):
        self.assertFalse(long_stop_ended(1, dict(LONG_STOP_OFF)))

    def test_setting_turned_back_on(self):
        for key in LONG_STOP_KEYS:
            with self.subTest(key=key):
                self.assertTrue(long_stop_ended(1, dict(LONG_STOP_OFF, **{key: 1})))

    def test_unread_values_do_not_end_it(self):
        # Before the first config read after a restart the values are None.
        self.assertFalse(long_stop_ended(1, {key: None for key in LONG_STOP_KEYS}))


if __name__ == "__main__":
    unittest.main()
