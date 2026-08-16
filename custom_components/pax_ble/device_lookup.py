"""Helpers for matching configured Pax devices by MAC address."""

from collections.abc import Callable
from typing import Any

# Literal matches const.CONF_MAC; kept here so unit tests avoid homeassistant imports.
_CONF_MAC = "mac"


def device_in_map(
    devices: dict[str, dict[str, Any]] | None,
    mac: str,
    format_mac: Callable[[str], str],
) -> bool:
    """Return True if mac matches a device dict key or stored CONF_MAC.

    Stored keys may use mixed-case MACs from manual setup; discovery uses
    dr.format_mac (lowercase). Compare normalized forms only — do not rewrite
    existing keys on load (device registry identifiers are case-sensitive).
    """
    if not devices:
        return False

    formatted = format_mac(mac)
    for key, cfg in devices.items():
        if format_mac(key) == formatted:
            return True
        stored_mac = cfg.get(_CONF_MAC)
        if stored_mac and format_mac(stored_mac) == formatted:
            return True
    return False
