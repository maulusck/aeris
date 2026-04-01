"""
AERIS · runtime configuration
All user-tunable knobs live here; import this module to override.
"""
from pathlib import Path

NMCLI: str = "nmcli"          # path to nmcli binary (or "./nmcli" for local stub)
CON_ID: str = "eth-operator"  # NetworkManager connection name
IFACE: str = "eth0"           # network interface
STATE_FILE: Path = Path.home() / ".rig-ip-switcher.json"
LOG_MAX_LINES: int = 200       # history kept in memory
LOG_PANEL_H: int = 7           # visible log panel height (border + rows)

PREDEFINED: list[dict] = [
    {"name": "Office",  "ip": "192.168.1.10/24"},
    {"name": "Lab",     "ip": "10.0.0.5/24"},
    {"name": "Test VM", "ip": "172.16.0.20/16"},
]
