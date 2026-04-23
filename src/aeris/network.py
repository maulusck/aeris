"""
AERIS · nmcli wrappers

Uses `nmcli -g` (machine-readable, tab-separated) for field extraction
instead of parsing human-readable output — this is stable across nmcli
versions and locale settings.
"""

from __future__ import annotations

import subprocess
from collections import deque
from typing import List, Optional, Tuple

from aeris.config import IFACE, NMCLI
from aeris.utils import log_append


def run_nmcli(args: List[str], timeout: int = 15) -> Tuple[str, str, int]:
    try:
        r = subprocess.run(
            [NMCLI] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except FileNotFoundError:
        return "", f"{NMCLI}: not found", 1
    except subprocess.TimeoutExpired:
        return "", "nmcli: timed out", 1


def list_connections() -> List[dict]:
    """
    Return all nmcli connections as a list of dicts:
      {name, uuid, type, device, state}

    Uses `nmcli -g` (machine-readable) for locale-stable output.
    Returns [] if nmcli is unavailable or returns no connections.
    """
    fields = "NAME,UUID,TYPE,DEVICE,STATE"
    out, _, code = run_nmcli(["-g", fields, "con", "show"], timeout=5)
    if code != 0 or not out:
        return []
    result = []
    for line in out.splitlines():
        # nmcli -g separates fields with colons; colons inside values are
        # escaped as \:  — we split on unescaped colons only.
        parts = _split_nmcli_fields(line, n=5)
        if len(parts) < 5:
            continue
        result.append(
            {
                "name": parts[0],
                "uuid": parts[1],
                "type": parts[2],
                "device": parts[3] or "--",
                "state": parts[4] or "disconnected",
            }
        )
    return result


def _split_nmcli_fields(line: str, n: int) -> List[str]:
    """Split a nmcli -g output line on unescaped colons into at most n fields."""
    parts: List[str] = []
    current: List[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == ":":
            current.append(":")
            i += 2
        elif ch == ":" and len(parts) < n - 1:
            parts.append("".join(current))
            current = []
            i += 1
        else:
            current.append(ch)
            i += 1
    parts.append("".join(current))
    return parts


def get_active_ips(con_id: str) -> List[str]:
    """
    Return the list of IPv4 addresses currently assigned to *con_id*.

    Uses `nmcli -g ipv4.addresses con show <id>` for machine-readable
    output that is stable across nmcli versions and locale settings.
    """
    out, _, code = run_nmcli(
        ["-g", "ipv4.addresses", "con", "show", con_id],
        timeout=5,
    )
    if code != 0 or not out:
        return []
    # nmcli -g outputs comma-separated values (may be pipe-separated on
    # older versions); handle both delimiters defensively.
    for sep in (",", "|"):
        if sep in out:
            return [ip.strip() for ip in out.split(sep) if ip.strip()]
    return [out] if out else []


def ensure_con(con_id: str, iface: str, log: deque) -> None:
    """Create the nmcli connection profile if it does not yet exist."""
    _, _, code = run_nmcli(["con", "show", con_id], timeout=5)
    if code != 0:
        log_append(log, "INFO", f"Creating connection '{con_id}'")
        run_nmcli(
            [
                "con",
                "add",
                "type",
                "ethernet",
                "con-name",
                con_id,
                "ifname",
                iface,
                "ipv4.method",
                "manual",
            ]
        )


def apply_ips(
    con_id: str,
    ips: List[str],
    log: deque,
    iface: str = IFACE,
) -> Optional[List[str]]:
    """
    Apply *ips* to *con_id* via nmcli mod + up.
    Returns the applied IP list on success, None on failure.
    """
    if not ips:
        log_append(log, "ERR", "Nothing selected")
        return None

    ip_str = ",".join(ips)
    ensure_con(con_id, iface, log)

    log_append(log, "CMD", f"$ nmcli con mod {con_id} ipv4.addresses {ip_str}")
    _, err, code = run_nmcli(
        [
            "con",
            "mod",
            con_id,
            "ipv4.addresses",
            ip_str,
            "ipv4.method",
            "manual",
        ]
    )
    if code != 0:
        log_append(log, "ERR", f"mod: {err or 'unknown'}")
        return None

    log_append(log, "CMD", f"$ nmcli con up {con_id}")
    _, err, code = run_nmcli(["con", "up", con_id])
    if code != 0:
        log_append(log, "ERR", f"up: {err or 'unknown'}")
        return None

    log_append(log, "OK", f"Applied: {ip_str}")
    return ips
