"""
AERIS · utility helpers
"""

from __future__ import annotations

import ipaddress
from collections import deque
from datetime import datetime
from typing import Deque

from aeris.config import LOG_MAX_LINES

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
