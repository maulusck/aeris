"""
AERIS · runtime configuration
All user-tunable knobs live here.
Environment variables override defaults at startup — no restart needed
when wrapping AERIS in a script.

User-home resolution
--------------------
When AERIS is invoked via ``sudo aeris``, os.path.expanduser / Path.home()
resolve to /root, which is wrong — profiles would land there and be
inaccessible to the real user.

We detect the real caller via the ``SUDO_USER`` environment variable that
sudo sets automatically, look up their home directory from the passwd
database (so it works even if $HOME was overridden), and use that as the
base for all config paths.

File ownership
--------------
Any config file or directory created while running as root is immediately
chowned back to the real user via _chown_to_real_user(), called from
persistence.py after every write.  This means ``sudo aeris`` and ``aeris``
(with sudoers rule) both leave files owned by the human user.
"""

from __future__ import annotations

import os
import pwd
from pathlib import Path

# ── Real-user resolution ─────────────────────────────────────────────────────


def _real_user() -> tuple[str, int, int, Path]:
    """
    Return (username, uid, gid, home) for the invoking human user.

    Priority:
      1. SUDO_USER env var  — set by sudo, most reliable
      2. LOGNAME / USER     — fallback for non-sudo su-style escalation
      3. Current process    — already the right user (no escalation)
    """
    for var in ("SUDO_USER", "LOGNAME", "USER"):
        name = os.environ.get(var)
        if name and name != "root":
            try:
                pw = pwd.getpwnam(name)
                return pw.pw_name, pw.pw_uid, pw.pw_gid, Path(pw.pw_dir)
            except KeyError:
                pass
    # Fallback: whoever owns the process
    pw = pwd.getpwuid(os.getuid())
    return pw.pw_name, pw.pw_uid, pw.pw_gid, Path(pw.pw_dir)


REAL_USER, REAL_UID, REAL_GID, REAL_HOME = _real_user()


def chown_to_real_user(path: Path) -> None:
    """
    Chown *path* to the real (non-root) user if we are currently root.
    Safe to call when not root — does nothing.
    Also fixes the ownership of every missing parent that we just created.
    """
    if os.geteuid() != 0 or REAL_UID == 0:
        return
    # Walk up and fix any directories we created that are still owned by root
    for p in [path, *path.parents]:
        try:
            st = p.stat()
        except OSError:
            break
        if st.st_uid == 0:
            os.chown(p, REAL_UID, REAL_GID)
        else:
            break  # hit a pre-existing directory — stop


# ── nmcli / network ──────────────────────────────────────────────────────────
NMCLI: str = os.getenv("AERIS_NMCLI", "nmcli")
CON_ID: str = os.getenv("AERIS_CON_ID", "eth-user")
IFACE: str = os.getenv("AERIS_IFACE", "eth0")

# ── UI ───────────────────────────────────────────────────────────────────────
LOG_MAX_LINES: int = int(os.getenv("AERIS_LOG_MAX", "200"))
LOG_PANEL_H: int = int(os.getenv("AERIS_LOG_H", "7"))

# Accepted values: "amber" | "matrix" | "mono"
THEME: str = os.getenv("AERIS_THEME", "amber")

# ── persistence ───────────────────────────────────────────────────────────────
PROFILES_DIR: Path = Path(os.getenv("AERIS_PROFILES_DIR", str(REAL_HOME / ".config" / "aeris" / "profiles")))
STATE_FILE: Path = Path(os.getenv("AERIS_STATE_FILE", str(REAL_HOME / ".config" / "aeris" / "state.json")))

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
