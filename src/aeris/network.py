"""AERIS · nmcli wrappers — machine-readable (-g) for locale stability"""

from __future__ import annotations

import subprocess
from collections import deque
from typing import Optional

from aeris.config import IFACE, NMCLI
from aeris.utils import log_append


def _run(args: list[str], timeout: int = 15) -> tuple[str, str, int]:
    try:
        r = subprocess.run([NMCLI] + args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except FileNotFoundError:
        return "", f"{NMCLI}: not found", 1
    except subprocess.TimeoutExpired:
        return "", "nmcli: timed out", 1


def _split_fields(line: str, n: int) -> list[str]:
    """Split nmcli -g line on unescaped colons into at most n fields."""
    parts, cur, i = [], [], 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line) and line[i + 1] == ":":
            cur.append(":")
            i += 2
        elif line[i] == ":" and len(parts) < n - 1:
            parts.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(line[i])
            i += 1
    parts.append("".join(cur))
    return parts


def list_connections() -> list[dict]:
    """Return all nmcli connections as {name, uuid, type, device, state}."""
    out, _, code = _run(["-g", "NAME,UUID,TYPE,DEVICE,STATE", "con", "show"], timeout=5)
    if code != 0 or not out:
        return []
    result = []
    for line in out.splitlines():
        p = _split_fields(line, 5)
        if len(p) == 5:
            result.append({"name": p[0], "uuid": p[1], "type": p[2], "device": p[3] or "--", "state": p[4] or "disconnected"})
    return result


def get_active_ips(con_id: str) -> list[str]:
    """Return IPv4 addresses currently assigned to con_id."""
    out, _, code = _run(["-g", "ipv4.addresses", "con", "show", con_id], timeout=5)
    if code != 0 or not out:
        return []
    for sep in (",", "|"):
        if sep in out:
            return [ip.strip() for ip in out.split(sep) if ip.strip()]
    return [out]


def _ensure_con(con_id: str, iface: str, log: deque) -> None:
    _, _, code = _run(["con", "show", con_id], timeout=5)
    if code != 0:
        log_append(log, "INFO", f"Creating connection '{con_id}'")
        _run(["con", "add", "type", "ethernet", "con-name", con_id, "ifname", iface, "ipv4.method", "manual"])


def apply_ips(con_id: str, ips: list[str], log: deque, iface: str = IFACE) -> Optional[list[str]]:
    """Apply ips to con_id via nmcli mod + up. Returns ip list on success."""
    if not ips:
        log_append(log, "ERR", "Nothing selected")
        return None

    ip_str = ",".join(ips)
    _ensure_con(con_id, iface, log)

    log_append(log, "CMD", f"$ nmcli con mod {con_id} ipv4.addresses {ip_str}")
    _, err, code = _run(["con", "mod", con_id, "ipv4.addresses", ip_str, "ipv4.method", "manual"])
    if code != 0:
        log_append(log, "ERR", f"mod: {err or 'unknown'}")
        return None

    log_append(log, "CMD", f"$ nmcli con up {con_id}")
    _, err, code = _run(["con", "up", con_id])
    if code != 0:
        log_append(log, "ERR", f"up: {err or 'unknown'}")
        return None

    log_append(log, "OK", f"Applied: {ip_str}")
    return ips
