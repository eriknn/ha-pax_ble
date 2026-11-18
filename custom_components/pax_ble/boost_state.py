"""Boost/pause state mapping for Calima-family fans.

The Calima has no pause characteristic. The Pax app pauses the fan by
running boost at 0 rpm, so pause and boost share one characteristic and
one set of coordinator keys. Kept free of homeassistant imports so the
unit tests run without an HA runtime.
"""

from typing import Any

PAUSE_MIN_SECONDS = 60
# The fan rejects boost/pause writes longer than this.
PAUSE_MAX_SECONDS = 900
PAUSE_DEFAULT_SECONDS = 900

STATE_BOOST = "Boost"
STATE_PAUSE = "Pause"


def pause_seconds(value: Any) -> int:
    """Clamp the configured pause length to what the fan accepts."""
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        seconds = 0
    if seconds <= 0:
        seconds = PAUSE_DEFAULT_SECONDS
    return min(PAUSE_MAX_SECONDS, max(PAUSE_MIN_SECONDS, seconds))


def boost_read_state(
    on_off: Any, speed: int, seconds: int, fan_mode: str | None
) -> dict[str, Any]:
    """Map a boost characteristic read to coordinator state.

    A boost with speed 0 is a pause: it is reported as Pause, not Boost.
    """
    active = bool(on_off)
    paused = active and speed == 0
    state = fan_mode
    if paused and fan_mode == STATE_BOOST:
        state = STATE_PAUSE
    return {
        "state": state,
        "boostmode": int(active and not paused),
        "boostmodespeedread": speed,
        "boostmodesecread": seconds if active and not paused else 0,
        "pause": int(paused),
        "pausesecread": seconds if paused else 0,
    }


def _state_after_off(current_state: str | None, read_mode: str | None) -> str | None:
    """State after Boost or Pause is turned off.

    The fan picks the next mode itself (trickle, humidity, light...), so the
    coordinator reads it back right after the write. A read that still says
    Boost is the fan not having switched yet, and a failed read gives None:
    in both cases keep the current State until the next poll rather than
    reporting unknown.
    """
    if read_mode and read_mode != STATE_BOOST:
        return read_mode
    return current_state


def boost_write_state(
    on: Any, seconds: int, current_state: str | None, read_mode: str | None = None
) -> dict[str, Any]:
    """Coordinator state after a successful BoostMode write."""
    if int(on):
        return {
            "state": STATE_BOOST,
            "boostmode": 1,
            "boostmodesecread": int(seconds),
            "pause": 0,
            "pausesecread": 0,
        }
    return {
        "state": _state_after_off(current_state, read_mode),
        "boostmode": 0,
        "boostmodesecread": 0,
        "pause": 0,
        "pausesecread": 0,
    }


def pause_write_state(
    on: Any, seconds: int, current_state: str | None, read_mode: str | None = None
) -> dict[str, Any]:
    """Coordinator state after a successful Pause write."""
    if int(on):
        return {
            "state": STATE_PAUSE,
            "boostmode": 0,
            "boostmodesecread": 0,
            "pause": 1,
            "pausesecread": int(seconds),
        }
    return {
        "state": _state_after_off(current_state, read_mode),
        "boostmode": 0,
        "boostmodesecread": 0,
        "pause": 0,
        "pausesecread": 0,
    }
