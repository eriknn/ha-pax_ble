"""Unit tests for boost_state (no Home Assistant runtime required)."""

import importlib.util
import pathlib
import unittest

_MODULE_PATH = pathlib.Path(__file__).with_name("boost_state.py")
_SPEC = importlib.util.spec_from_file_location("boost_state", _MODULE_PATH)
boost_state = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(boost_state)

boost_read_state = boost_state.boost_read_state
boost_write_state = boost_state.boost_write_state
pause_write_state = boost_state.pause_write_state
pause_seconds = boost_state.pause_seconds


class BoostReadStateTests(unittest.TestCase):
    def test_zero_rpm_boost_is_pause(self):
        state = boost_read_state(1, 0, 845, "Boost")
        self.assertEqual(state["state"], "Pause")
        self.assertEqual(state["pause"], 1)
        self.assertEqual(state["pausesecread"], 845)
        self.assertEqual(state["boostmode"], 0)
        self.assertEqual(state["boostmodesecread"], 0)
        self.assertEqual(state["boostmodespeedread"], 0)

    def test_active_boost_is_not_pause(self):
        state = boost_read_state(1, 2400, 600, "Boost")
        self.assertEqual(state["state"], "Boost")
        self.assertEqual(state["boostmode"], 1)
        self.assertEqual(state["boostmodesecread"], 600)
        self.assertEqual(state["pause"], 0)
        self.assertEqual(state["pausesecread"], 0)

    def test_inactive_boost_with_zero_speed_is_not_pause(self):
        # After a pause ends the fan can still report speed 0 with boost off.
        state = boost_read_state(0, 0, 0, "Trickle ventilation")
        self.assertEqual(state["state"], "Trickle ventilation")
        self.assertEqual(state["pause"], 0)
        self.assertEqual(state["pausesecread"], 0)
        self.assertEqual(state["boostmode"], 0)
        self.assertEqual(state["boostmodesecread"], 0)

    def test_inactive_boost_ignores_leftover_seconds(self):
        state = boost_read_state(0, 2400, 300, "Humidity ventilation")
        self.assertEqual(state["boostmode"], 0)
        self.assertEqual(state["boostmodesecread"], 0)
        self.assertEqual(state["pause"], 0)

    def test_pause_keeps_other_fan_modes(self):
        # Only the Boost trigger is renamed; another reported mode is kept.
        state = boost_read_state(1, 0, 900, "Switch")
        self.assertEqual(state["state"], "Switch")
        self.assertEqual(state["pause"], 1)


class PauseWriteStateTests(unittest.TestCase):
    def test_pause_on_sets_state_and_remaining_time(self):
        state = pause_write_state(1, 900, "Trickle ventilation")
        self.assertEqual(state["state"], "Pause")
        self.assertEqual(state["pause"], 1)
        self.assertEqual(state["pausesecread"], 900)
        self.assertEqual(state["boostmode"], 0)
        self.assertEqual(state["boostmodesecread"], 0)

    def test_pause_on_ends_boost(self):
        state = pause_write_state(1, 120, "Boost")
        self.assertEqual(state["state"], "Pause")
        self.assertEqual(state["boostmode"], 0)
        self.assertEqual(state["boostmodesecread"], 0)

    def test_pause_off_clears_pause(self):
        state = pause_write_state(0, 900, "Pause", "Trickle ventilation")
        self.assertEqual(state["pause"], 0)
        self.assertEqual(state["pausesecread"], 0)
        self.assertEqual(state["state"], "Trickle ventilation")

    def test_pause_off_read_still_boost_keeps_state(self):
        # The fan has not switched yet: keep Pause until the next poll,
        # never report it as Boost or unknown.
        state = pause_write_state(0, 900, "Pause", "Boost")
        self.assertEqual(state["state"], "Pause")
        self.assertEqual(state["pause"], 0)

    def test_pause_off_failed_read_keeps_state(self):
        state = pause_write_state(0, 900, "Pause", None)
        self.assertEqual(state["state"], "Pause")

    def test_pause_off_keeps_unrelated_state(self):
        state = pause_write_state(0, 900, "Humidity ventilation")
        self.assertEqual(state["state"], "Humidity ventilation")


class BoostWriteStateTests(unittest.TestCase):
    def test_boost_on_clears_pause(self):
        state = boost_write_state(1, 600, "Pause")
        self.assertEqual(state["state"], "Boost")
        self.assertEqual(state["boostmode"], 1)
        self.assertEqual(state["boostmodesecread"], 600)
        self.assertEqual(state["pause"], 0)
        self.assertEqual(state["pausesecread"], 0)

    def test_boost_off_clears_boost(self):
        state = boost_write_state(0, 600, "Boost", "Humidity ventilation")
        self.assertEqual(state["boostmode"], 0)
        self.assertEqual(state["boostmodesecread"], 0)
        self.assertEqual(state["pause"], 0)
        self.assertEqual(state["state"], "Humidity ventilation")

    def test_boost_off_never_unknown(self):
        # Read still says Boost, or failed: keep the old State, not None.
        self.assertEqual(boost_write_state(0, 600, "Boost", "Boost")["state"], "Boost")
        self.assertEqual(boost_write_state(0, 600, "Boost", None)["state"], "Boost")

    def test_boost_on_ignores_read_mode(self):
        state = boost_write_state(1, 600, "Trickle ventilation", "Trickle ventilation")
        self.assertEqual(state["state"], "Boost")

    def test_boost_off_keeps_unrelated_state(self):
        state = boost_write_state(0, 600, "Light ventilation")
        self.assertEqual(state["state"], "Light ventilation")


class PauseSecondsTests(unittest.TestCase):
    def test_within_range(self):
        self.assertEqual(pause_seconds(120), 120)
        self.assertEqual(pause_seconds("900"), 900)

    def test_restored_float_string(self):
        self.assertEqual(pause_seconds("300.0"), 300)

    def test_clamped_to_fan_limits(self):
        self.assertEqual(pause_seconds(1800), 900)
        self.assertEqual(pause_seconds(10), 60)

    def test_missing_falls_back_to_default(self):
        self.assertEqual(pause_seconds(None), 900)
        self.assertEqual(pause_seconds(0), 900)
        self.assertEqual(pause_seconds("unknown"), 900)


if __name__ == "__main__":
    unittest.main()
