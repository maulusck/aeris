"""
AERIS · TUI draw layer
"""

import curses

from aeris.colors import (
    C_BORDER,
    C_CUR_LIVE,
    C_CUR_PADD,
    C_CUR_PDEL,
    C_CURSOR,
    C_DIM,
    C_HDR,
    C_HINT,
    C_LIVE,
    C_LOG_CMD,
    C_LOG_ERR,
    C_LOG_INFO,
    C_LOG_OK,
    C_PEND_ADD,
    C_PEND_DEL,
    C_SECTION,
    C_STAT_ADD,
    C_STAT_DEL,
    C_STAT_LIV,
)
from aeris.config import CON_ID, LOG_PANEL_H
from aeris.drawing import draw_scrollbar, hln, sadd
from aeris.utils import now_ts
from aeris.widgets import NAME_W

HINT = " jk/↑↓:move  SPC:toggle  N:add  E:rename  D:del" "  A:apply  R:refresh  P:profiles  [/]:log  ?:help  Q:quit"


_ROW_COLORS: dict[tuple[bool, str], tuple[int, bool]] = {
    (True, "live_sel"): (C_CUR_LIVE, True),
    (True, "live_desel"): (C_CUR_PDEL, True),
    (True, "dead_sel"): (C_CUR_PADD, True),
    (True, "dead_desel"): (C_CURSOR, True),
    (False, "live_sel"): (C_LIVE, True),
    (False, "live_desel"): (C_PEND_DEL, True),
    (False, "dead_sel"): (C_PEND_ADD, True),
    (False, "dead_desel"): (0, False),
}


def _row_attr(is_cursor: bool, is_live: bool, is_sel: bool) -> int:
    if is_live and is_sel:
        state = "live_sel"
    elif is_live:
        state = "live_desel"
    elif is_sel:
        state = "dead_sel"
    else:
        state = "dead_desel"
    pair, bold = _ROW_COLORS[(is_cursor, state)]
    attr = curses.color_pair(pair) if pair else 0
    if bold:
        attr |= curses.A_BOLD
    return attr


def draw_ui(
    stdscr,
    entries: list[dict],
    selected: set[int],
    cursor: int,
    entry_scroll: int,
    log: list,
    log_scroll: int,
    current_ips: list[str],
    status: str,
    active_profile: str = "default",
) -> tuple[int, int]:
    """
    Render the full TUI.  Returns (entry_scroll, log_scroll) after clamping.
    """
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    if h < 12 or w < 44:
        sadd(stdscr, 0, 0, f"Terminal too small ({w}×{h})", curses.A_BOLD)
        stdscr.noutrefresh()
        curses.doupdate()
        return entry_scroll, log_scroll

    title = f"  AERIS · {CON_ID}  ▸  profile: {active_profile}  "
    sadd(stdscr, 0, 0, title.ljust(w - 1), curses.color_pair(C_HDR) | curses.A_BOLD)
    ts = now_ts()
    sadd(stdscr, 0, w - len(ts) - 2, ts, curses.color_pair(C_HDR) | curses.A_DIM)

    sadd(stdscr, 1, 0, HINT[: w - 1], curses.color_pair(C_HINT))

    new_ips = [entries[i]["ip"] for i in sorted(selected)]
    pend_add = [ip for ip in new_ips if ip not in current_ips]
    pend_del = [ip for ip in current_ips if ip not in new_ips]

    row = 3
    sadd(
        stdscr,
        row,
        0,
        (" LIVE  : " + (", ".join(current_ips) or "—"))[: w - 1],
        curses.color_pair(C_STAT_LIV),
    )
    row += 1
    if pend_add:
        sadd(
            stdscr,
            row,
            0,
            (" + ADD : " + ", ".join(pend_add))[: w - 1],
            curses.color_pair(C_STAT_ADD) | curses.A_BOLD,
        )
        row += 1
    if pend_del:
        sadd(
            stdscr,
            row,
            0,
            (" - DEL : " + ", ".join(pend_del))[: w - 1],
            curses.color_pair(C_STAT_DEL) | curses.A_BOLD,
        )
        row += 1

    hln(stdscr, row, 0, w - 1, curses.color_pair(C_BORDER))
    row += 1
    list_top = row

    list_bot = h - LOG_PANEL_H - 1
    list_h = max(1, list_bot - list_top)

    entry_scroll = max(0, min(entry_scroll, max(0, len(entries) - list_h)))
    if cursor < entry_scroll:
        entry_scroll = cursor
    elif cursor >= entry_scroll + list_h:
        entry_scroll = cursor - list_h + 1

    visible = entries[entry_scroll : entry_scroll + list_h]
    rrow = list_top
    for rel, e in enumerate(visible):
        idx = entry_scroll + rel
        is_cur = idx == cursor
        is_live = e["ip"] in current_ips
        is_sel = idx in selected
        tick = "◉" if is_sel else "○"
        name = e["name"][:NAME_W].ljust(NAME_W)
        line = f"  {tick} {name}  {e['ip']}"
        sadd(stdscr, rrow, 0, line[: w - 1], _row_attr(is_cur, is_live, is_sel))
        rrow += 1

    draw_scrollbar(
        stdscr,
        list_top,
        list_h,
        w - 2,
        len(entries),
        entry_scroll,
        curses.color_pair(C_BORDER),
    )

    log_top = h - LOG_PANEL_H - 1
    log_rows = LOG_PANEL_H - 1

    hln(stdscr, log_top, 0, w - 1, curses.color_pair(C_BORDER))
    sadd(stdscr, log_top, 2, " LOG ", curses.color_pair(C_SECTION) | curses.A_BOLD)

    if log_scroll > 0:
        sadd(
            stdscr,
            log_top,
            8,
            f" ↑{log_scroll} ",
            curses.color_pair(C_STAT_DEL) | curses.A_BOLD,
        )

    log_max = max(0, len(log) - log_rows)
    log_scroll = max(0, min(log_scroll, log_max))

    if log_scroll == 0:
        visible_log = log[-log_rows:] if log else []
    else:
        start = log_max - log_scroll
        visible_log = log[start : start + log_rows]

    color_map = {
        "OK": (C_LOG_OK, True),
        "ERR": (C_LOG_ERR, False),
        "CMD": (C_LOG_CMD, False),
        "INFO": (C_LOG_INFO, False),
    }
    for i, (kind, stamp, msg) in enumerate(visible_log):
        pair, bold = color_map.get(kind, (C_LOG_INFO, False))
        attr = curses.color_pair(pair) | (curses.A_BOLD if bold else 0)
        sadd(stdscr, log_top + 1 + i, 1, f"[{stamp}] {msg}"[: w - 2], attr)

    draw_scrollbar(
        stdscr,
        log_top + 1,
        log_rows,
        w - 2,
        len(log),
        log_max - log_scroll,
        curses.color_pair(C_BORDER),
    )

    sadd(
        stdscr,
        h - 1,
        0,
        f"  {status:<{w - 3}}"[: w - 1],
        curses.color_pair(C_HINT) | curses.A_DIM,
    )

    stdscr.noutrefresh()
    curses.doupdate()
    return entry_scroll, log_scroll
