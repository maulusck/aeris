"""AERIS · curses drawing primitives"""

from __future__ import annotations

import curses


def sadd(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """Clipped addstr — never raises."""
    try:
        mh, mw = win.getmaxyx()
        if 0 <= y < mh and 0 <= x < mw:
            clip = text[: max(0, mw - x - 1)]
            if clip:
                win.addstr(y, x, clip, attr)
    except curses.error:
        pass


def hln(win, y: int, x: int, n: int, attr: int = 0) -> None:
    """Safe horizontal line."""
    try:
        mh, mw = win.getmaxyx()
        n = min(n, mw - x - 1)
        if n > 0 and 0 <= y < mh:
            win.hline(y, x, curses.ACS_HLINE, n, attr)
    except curses.error:
        pass


def draw_scrollbar(win, top: int, height: int, col: int, total: int, offset: int, attr: int) -> None:
    """Single-column scrollbar. No-op when all items fit."""
    if total <= height or height < 1:
        return
    max_off = max(1, total - height)
    thumb = int(offset / max_off * (height - 1))
    for i in range(height):
        sadd(win, top + i, col, "█" if i == thumb else "░", attr)
