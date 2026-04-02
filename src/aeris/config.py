"""
AERIS · runtime configuration
All user-tunable knobs live here; import this module to override.
"""

from pathlib import Path

NMCLI: str = "nmcli"
CON_ID: str = "eth-operator"
IFACE: str = "eth0"
LOG_MAX_LINES: int = 200
LOG_PANEL_H: int = 7


PROFILES_DIR: Path = Path.home() / ".config" / "aeris" / "profiles"
STATE_FILE: Path = Path.home() / ".config" / "aeris" / "state.json"


DEFAULT_IPS: list[dict] = [
    {"name": "Office", "ip": "192.168.1.10/24"},
    {"name": "Lab", "ip": "10.0.0.5/24"},
    {"name": "Test VM", "ip": "172.16.0.20/16"},
]
