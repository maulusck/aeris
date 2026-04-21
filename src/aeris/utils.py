"""
AERIS · utility helpers
"""

from __future__ import annotations

import ipaddress
from collections import deque
from datetime import datetime
from typing import Deque

from aeris.config import LOG_MAX_LINES

# ── Canonical help text ───────────────────────────────────────────────────────
# Single source of truth: printed verbatim by `aeris --help` and rendered
# inside the TUI help popup (help_popup in widgets.py).
#
# Styling cues recognised by help_popup:
#   Line 0             → title  (C_HDR | BOLD)
#   ALL-CAPS word line → section header (C_SECTION | BOLD)
#   "PRESS …"          → close hint (C_PEND_DEL | BOLD)
#   ASCII-art lines    → art colour (C_PEND_ADD), centred
#   everything else    → body (C_DIM | BOLD)

HELP_TEXT = """\
AERIS · Avionic Ethernet Rig IP Selector
─────────────────────────────────────────────

USAGE
  aeris [OPTIONS]

OPTIONS
  -h, --help              Show this help and exit
  -v, --version           Show version and exit
  -p, --profile NAME      Start with named profile (default: last used)
  -c, --con-id ID         Override saved connection for this session
                          (use C inside TUI to switch and persist)
      --theme THEME       Colour theme: amber | matrix | mono
                          (overrides AERIS_THEME)
      --list-profiles     Print available profiles and exit
      --apply PROFILE     Headless: apply all IPs in PROFILE and exit

KEYBINDINGS
  ↑ / k        Move cursor up          D   Delete entry
  ↓ / j        Move cursor down        A   Apply selected IPs
  SPC          Toggle selection        R   Refresh live IPs
  N            Add IP entry            P   Profile manager
  E            Rename entry            C   Connection selector
  ?            Help popup              Q/ESC  Quit

DESCRIPTION
  Select, add, rename, and apply IPv4 addresses to the Ethernet interface.
  IPs are organised into profiles stored in ~/.config/aeris/profiles/.
  The active profile is shown in the title bar.
  Live IPs are displayed at the top; pending additions/removals are
  highlighted in colour.

EXAMPLES
  aeris                          Launch TUI with last-used profile
  aeris -p bench                 Launch TUI with 'bench' profile
  aeris -c eth-lab --theme mono  Custom connection + theme
  aeris --list-profiles          Print profiles and exit
  sudo aeris --apply production  Headless: apply 'production' IPs
  Toggle multiple IPs with SPC, press A to apply.
  Use R to refresh after changes made outside AERIS.

NOTES
  All IPs within a profile are equal and fully editable.
  The default profile is recreated from built-in defaults if deleted.
  Scroll lists with ↑/↓ or j/k.

ENVIRONMENT
  AERIS_CON_ID        NetworkManager connection ID  (default: eth-user)
  AERIS_NMCLI         Path to nmcli binary          (default: nmcli)
  AERIS_IFACE         Interface name                (default: eth0)
  AERIS_THEME         Colour theme                  (default: amber)
  AERIS_LOG_H         Log panel height              (default: 7)
  AERIS_LOG_MAX       Max log lines kept            (default: 200)
  AERIS_PROFILES_DIR  Profile directory
  AERIS_STATE_FILE    State file path

FILES
  ~/.config/aeris/profiles/   Profile JSON files
  ~/.config/aeris/state.json  Last active profile\
"""

# ── Type alias ───────────────────────────────────────────────────────────────
# A log entry is a 3-tuple: (kind, timestamp, message)
LogEntry = tuple  # tuple[str, str, str]
LogDeque = Deque  # Deque[LogEntry]


def make_log() -> deque:
    """Return a new bounded log deque."""
    return deque(maxlen=LOG_MAX_LINES)


def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.IPv4Interface(ip)
        return True
    except ValueError:
        return False


def normalize_ip(ip: str) -> str:
    return str(ipaddress.IPv4Interface(ip))


def log_append(log: deque, kind: str, msg: str) -> None:
    """
    Stamp and append a log entry.

    The deque is created with maxlen=LOG_MAX_LINES so eviction is O(1)
    and automatic — no manual trimming needed.
    """
    log.append((kind, now_ts(), msg))
