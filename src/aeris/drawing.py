"""
AERIS · curses drawing primitives
"""

import curses


def sadd(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """Safe clipped addstr — never raises curses.error."""
    try:
        mh, mw = win.getmaxyx()
        if y < 0 or y >= mh or x < 0 or x >= mw:
            return
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
    """
    Draw a single-column scrollbar.

    Parameters
    ----------
    top     : first row of the scrollable area
    height  : number of rows in the area
    col     : column for the scrollbar character
    total   : total number of scrollable items
    offset  : current scroll offset (0 = top)
    attr    : curses attribute for the bar
    """
    if total <= height or height < 1:
        return
    max_off = max(1, total - height)
    thumb = int(offset / max_off * (height - 1))
    for i in range(height):
        ch = "\u2588" if i == thumb else "\u2591"
        sadd(win, top + i, col, ch, attr)
