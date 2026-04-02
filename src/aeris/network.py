"""
AERIS · nmcli wrappers
"""

import subprocess

from aeris.config import IFACE, NMCLI
from aeris.utils import log_append


def run_nmcli(args: list[str], timeout: int = 15) -> tuple[str, str, int]:
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


def get_active_ips(con_id: str) -> list[str]:
    out, _, code = run_nmcli(["con", "show", con_id], timeout=5)
    if code != 0:
        return []
    for line in out.splitlines():
        if line.startswith("ipv4.addresses"):
            raw = line.split(":", 1)[1]
            return [ip.strip() for ip in raw.split(",") if ip.strip()]
    return []


def ensure_con(con_id: str, iface: str, log: list) -> None:
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


def apply_ips(con_id: str, ips: list[str], log: list, iface: str = IFACE) -> list[str] | None:
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
