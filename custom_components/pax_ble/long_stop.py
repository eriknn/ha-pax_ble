"""Long stop for Calima-family fans.

The Calima has no off state, and a pause lasts at most 15 minutes. The fan
stays at 0 rpm for as long as nothing can start it: trickle ventilation on
weekdays and weekends, the humidity and light sensors and the automatic
airing cycles are all off. A long stop saves those settings, turns them all
off and writes them back on resume.

Kept free of homeassistant imports so the unit tests run without an HA
runtime.
"""

from typing import Any

# The settings that can start the fan, with the value that turns each one off.
LONG_STOP_KEYS = (
    "trickledays_weekdays",
    "trickledays_weekends",
    "sensitivity_humidity",
    "sensitivity_light",
    "automatic_cycles",
)
LONG_STOP_OFF = {key: 0 for key in LONG_STOP_KEYS}


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def saved_settings(values: Any) -> dict[str, int] | None:
    """Return the long stop settings in values, or None if any is missing.

    Accepts the coordinator state or a dict restored from Home Assistant,
    where the values may come back as strings.
    """
    if not isinstance(values, dict):
        return None
    saved = {}
    for key in LONG_STOP_KEYS:
        value = _as_int(values.get(key))
        if value is None or value < 0:
            return None
        saved[key] = value
    return saved


def is_long_stopped(state: dict[str, Any]) -> bool:
    """True if every setting that can start the fan is off."""
    return all(_as_int(state.get(key)) == 0 for key in LONG_STOP_KEYS)


def long_stop_ended(stopped: Any, state: dict[str, Any]) -> bool:
    """True if a long stop is on but one of its settings was turned back on.

    That happens when a setting is changed in the Pax app or on its own
    entity while the fan is stopped. The stop then counts as ended, so the
    switch does not claim the fan is stopped while it can start.
    """
    if not stopped:
        return False
    return any(
        (value := _as_int(state.get(key))) is not None and value != 0
        for key in LONG_STOP_KEYS
    )
