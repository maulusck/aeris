"""
AERIS · utility helpers
"""

import ipaddress
from datetime import datetime

from aeris.config import LOG_MAX_LINES


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


def log_append(log: list, kind: str, msg: str) -> None:
    """Stamp and append a log entry, then trim to LOG_MAX_LINES."""
    log.append((kind, now_ts(), msg))
    if len(log) > LOG_MAX_LINES:
        del log[: len(log) - LOG_MAX_LINES]
