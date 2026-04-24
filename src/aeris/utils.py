"""AERIS · utility helpers"""

from __future__ import annotations

import ipaddress
from collections import deque
from datetime import datetime
from typing import Deque

from aeris.config import LOG_MAX_LINES

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
      --theme THEME       Colour theme: amber | matrix | mono
      --list-profiles     Print available profiles and exit
      --apply PROFILE     Headless: apply all IPs in PROFILE and exit

KEYBINDINGS
  ↑ / k        Move cursor up          D   Delete entry
  ↓ / j        Move cursor down        A   Apply selected IPs
  SPC          Toggle selection        R   Refresh live IPs
  N            Add IP entry            P   Profile manager
  E            Rename entry            C   Connection selector
  ?            Help popup              Q / ESC  Quit

DESCRIPTION
  Select, add, rename, and apply IPv4 addresses to the Ethernet interface.
  IPs are organised into profiles stored in ~/.config/aeris/profiles/.
  Live IPs are shown at the top; pending additions/removals are highlighted.

EXAMPLES
  aeris                          Launch TUI with last-used profile
  aeris -p bench                 Launch with 'bench' profile
  aeris -c eth-lab --theme mono  Custom connection + theme
  aeris --list-profiles          Print profiles and exit
  sudo aeris --apply production  Headless: apply 'production' IPs

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

LogDeque = Deque[tuple[str, str, str]]


def make_log() -> deque:
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
    log.append((kind, now_ts(), msg))
