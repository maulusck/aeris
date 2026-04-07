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
CON_ID: str = os.getenv("AERIS_CON_ID", "eth-user")
IFACE: str = os.getenv("AERIS_IFACE", "eth0")

# ── UI ───────────────────────────────────────────────────────────────────────
LOG_MAX_LINES: int = int(os.getenv("AERIS_LOG_MAX", "200"))
LOG_PANEL_H: int = int(os.getenv("AERIS_LOG_H", "7"))

# Accepted values: "matrix" (retro phosphor, default) | "amber" (256-colour warm) | "mono" (8-colour fallback)
# Set AERIS_THEME=amber or AERIS_THEME=mono to switch.
THEME: str = os.getenv("AERIS_THEME", "matrix")

# ── persistence ───────────────────────────────────────────────────────────────
PROFILES_DIR: Path = Path(os.getenv("AERIS_PROFILES_DIR", str(Path.home() / ".config" / "aeris" / "profiles")))
STATE_FILE: Path = Path(os.getenv("AERIS_STATE_FILE", str(Path.home() / ".config" / "aeris" / "state.json")))

# ── built-in seed data ────────────────────────────────────────────────────────
DEFAULT_IPS: list[dict] = [
    # Management / control plane
    {"name": "GCS-Primary", "ip": "192.168.10.1/24"},
    {"name": "GCS-Backup", "ip": "192.168.10.2/24"},
    # Avionics data bus segments
    {"name": "Avionics-A", "ip": "10.10.1.10/24"},
    {"name": "Avionics-B", "ip": "10.10.2.10/24"},
    # Payload / sensor links
    {"name": "Payload-Ctrl", "ip": "172.20.0.10/24"},
    {"name": "Sensor-Hub", "ip": "172.20.0.20/24"},
    # Test & integration bench
    {"name": "Bench-Test", "ip": "10.99.0.5/24"},
    {"name": "Sim-Node", "ip": "10.99.0.6/24"},
]
