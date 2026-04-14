"""
AERIS · Avionic Ethernet Rig IP Selector
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aeris")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

from aeris.app import main

__all__ = ["main"]
