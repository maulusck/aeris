"""
AERIS · runtime configuration
All user-tunable knobs live here.
Environment variables override defaults at startup — no restart needed
when wrapping AERIS in a script.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── nmcli / network ──────────────────────────────────────────────────────────
NMCLI: str = os.getenv("AERIS_NMCLI", "nmcli")
CON_ID: str = os.getenv("AERIS_CON_ID", "eth-operator")
IFACE: str = os.getenv("AERIS_IFACE", "eth0")

# ── UI ───────────────────────────────────────────────────────────────────────
LOG_MAX_LINES: int = int(os.getenv("AERIS_LOG_MAX", "200"))
LOG_PANEL_H: int = int(os.getenv("AERIS_LOG_H", "7"))

# ── theming ───────────────────────────────────────────────────────────────────
# Accepted values: "amber" (default 256-colour) | "mono" (8-colour fallback)
# Set AERIS_THEME=mono to force the 8-colour palette on any terminal.
THEME: str = os.getenv("AERIS_THEME", "amber")

# ── persistence ───────────────────────────────────────────────────────────────
PROFILES_DIR: Path = Path(os.getenv("AERIS_PROFILES_DIR", str(Path.home() / ".config" / "aeris" / "profiles")))
STATE_FILE: Path = Path(os.getenv("AERIS_STATE_FILE", str(Path.home() / ".config" / "aeris" / "state.json")))

# ── built-in seed data ────────────────────────────────────────────────────────
DEFAULT_IPS: list[dict] = [
    {"name": "Office", "ip": "192.168.1.10/24"},
    {"name": "Lab", "ip": "10.0.0.5/24"},
    {"name": "Test VM", "ip": "172.16.0.20/16"},
]
