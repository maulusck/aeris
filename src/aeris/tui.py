"""
AERIS · TUI draw layer
"""
import curses
from aeris.colors import (
    C_HDR, C_HINT, C_BORDER, C_SECTION, C_DIM,
    C_LIVE, C_PEND_ADD, C_PEND_DEL,
    C_CURSOR, C_CUR_LIVE, C_CUR_PADD, C_CUR_PDEL,
    C_STAT_LIV, C_STAT_ADD, C_STAT_DEL,
    C_LOG_OK, C_LOG_ERR, C_LOG_CMD, C_LOG_INFO,
)
from aeris.drawing import sadd, hln, draw_scrollbar
from aeris.utils import now_ts
from aeris.config import CON_ID, LOG_PANEL_H
from aeris.widgets import NAME_W

HINT = (
    " jk/↑↓:move  SPC:toggle  N:add  E:rename  D:del"
    "  A:apply  R:refresh  [/]:log scroll  ?:help  Q:quit"
)

# ── Entry-row colour matrix ──────────────────────────────────
_ROW_COLORS: dict[tuple[bool, str], tuple[int, bool]] = {
    (True,  "live_sel"):   (C_CUR_LIVE, True),
    (True,  "live_desel"): (C_CUR_PDEL, True),
    (True,  "dead_sel"):   (C_CUR_PADD, True),
    (True,  "dead_desel"): (C_CURSOR,   True),
    (False, "live_sel"):   (C_LIVE,     True),
    (False, "live_desel"): (C_PEND_DEL, True),
    (False, "dead_sel"):   (C_PEND_ADD, True),
    (False, "dead_desel"): (0,          False),
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


def _build_render(entries: list[dict]) -> list[tuple]:
    """Build flat render list with injected section headers."""
    render: list[tuple] = []
    prev_type = None
    for idx, e in enumerate(entries):
        if e["type"] != prev_type:
            render.append(("header", e["type"]))
            prev_type = e["type"]
        render.append(("entry", idx))
    return render


def draw_ui(
    stdscr,
    entries:      list[dict],
    selected:     set[int],
    cursor:       int,
    entry_scroll: int,
    log:          list,
    log_scroll:   int,          # 0 = pinned to bottom; > 0 = scrolled up by N lines
    current_ips:  list[str],
    status:       str,
) -> tuple[int, int]:
    """
    Render the full TUI.  Returns (entry_scroll, log_scroll) after clamping,
    so the main loop can update its own state variables.

    log_scroll semantics
    --------------------
    0            → always show the *newest* (bottom) lines — auto-follow mode.
    N > 0        → the user has scrolled the log up by N lines; the newest N
                   lines are hidden.  New log entries do NOT move the viewport,
                   so the user keeps reading history undisturbed.
    """
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    if h < 12 or w < 44:
        sadd(stdscr, 0, 0, f"Terminal too small ({w}×{h})", curses.A_BOLD)
        stdscr.noutrefresh()
        curses.doupdate()
        return entry_scroll, log_scroll

    # ── Title bar ──────────────────────────────────────────────
    title = f"  AERIS · Avionic Ethernet Rig IP Selector  ▸  {CON_ID}  "
    sadd(stdscr, 0, 0, title.ljust(w - 1),
         curses.color_pair(C_HDR) | curses.A_BOLD)
    ts = now_ts()
    sadd(stdscr, 0, w - len(ts) - 2, ts,
         curses.color_pair(C_HDR) | curses.A_DIM)

    # ── Key hint bar ───────────────────────────────────────────
    sadd(stdscr, 1, 0, HINT[: w - 1], curses.color_pair(C_HINT))

    # ── Status panel: LIVE / ADD / DEL ─────────────────────────
    new_ips   = [entries[i]["ip"] for i in sorted(selected)]
    pend_add  = [ip for ip in new_ips    if ip not in current_ips]
    pend_del  = [ip for ip in current_ips if ip not in new_ips]

    row = 3
    sadd(stdscr, row, 0,
         (" LIVE  : " + (", ".join(current_ips) or "—"))[: w - 1],
         curses.color_pair(C_STAT_LIV))
    row += 1
    if pend_add:
        sadd(stdscr, row, 0,
             (" + ADD : " + ", ".join(pend_add))[: w - 1],
             curses.color_pair(C_STAT_ADD) | curses.A_BOLD)
        row += 1
    if pend_del:
        sadd(stdscr, row, 0,
             (" - DEL : " + ", ".join(pend_del))[: w - 1],
             curses.color_pair(C_STAT_DEL) | curses.A_BOLD)
        row += 1

    hln(stdscr, row, 0, w - 1, curses.color_pair(C_BORDER))
    row += 1
    list_top = row

    # ── Entry list ─────────────────────────────────────────────
    list_bot = h - LOG_PANEL_H - 1       # exclusive bottom edge
    list_h   = max(1, list_bot - list_top)

    render = _build_render(entries)

    # Locate where the cursor entry falls in the render list
    cursor_render = next(
        (ri for ri, item in enumerate(render)
         if item[0] == "entry" and item[1] == cursor),
        0,
    )

    # Clamp then auto-scroll so cursor stays visible
    entry_scroll = max(0, min(entry_scroll, max(0, len(render) - list_h)))
    if cursor_render < entry_scroll:
        entry_scroll = cursor_render
    elif cursor_render >= entry_scroll + list_h:
        entry_scroll = cursor_render - list_h + 1

    visible = render[entry_scroll: entry_scroll + list_h]
    rrow = list_top
    for item in visible:
        if item[0] == "header":
            label = " PREDEFINED" if item[1] == "predefined" else " CUSTOM"
            sadd(stdscr, rrow, 0, label,
                 curses.color_pair(C_SECTION) | curses.A_BOLD | curses.A_UNDERLINE)
        else:
            idx    = item[1]
            e      = entries[idx]
            is_cur  = idx == cursor
            is_live = e["ip"] in current_ips
            is_sel  = idx in selected
            tick    = "◉" if is_sel else "○"
            name    = e["name"][:NAME_W].ljust(NAME_W)
            line    = f"  {tick} {name}  {e['ip']}"
            sadd(stdscr, rrow, 0, line[: w - 1],
                 _row_attr(is_cur, is_live, is_sel))
        rrow += 1

    # Entry-list scrollbar
    draw_scrollbar(
        stdscr, list_top, list_h, w - 2,
        len(render), entry_scroll,
        curses.color_pair(C_BORDER),
    )

    # ── Log panel ──────────────────────────────────────────────
    log_top  = h - LOG_PANEL_H - 1
    log_rows = LOG_PANEL_H - 1      # usable lines inside the panel

    hln(stdscr, log_top, 0, w - 1, curses.color_pair(C_BORDER))
    sadd(stdscr, log_top, 2, " LOG ",
         curses.color_pair(C_SECTION) | curses.A_BOLD)

    # Scroll indicator in header
    if log_scroll > 0:
        scroll_hint = f" ↑{log_scroll} "
        sadd(stdscr, log_top, 8, scroll_hint,
             curses.color_pair(C_STAT_DEL) | curses.A_BOLD)

    log_max = max(0, len(log) - log_rows)

    # ── Auto-follow (pin-to-bottom) logic ──────────────────────
    # log_scroll == 0 means "follow mode": always show newest entries.
    # log_scroll > 0 means user scrolled up; we leave them there and
    # only clamp to valid range — new lines do NOT push the viewport.
    log_scroll = max(0, min(log_scroll, log_max))

    if log_scroll == 0:
        # Follow mode — slice the newest log_rows entries
        visible_log = log[-log_rows:] if log else []
    else:
        # Historical view — log_scroll lines from the bottom are hidden
        start       = log_max - log_scroll
        visible_log = log[start: start + log_rows]

    color_map = {
        "OK":   (C_LOG_OK,   True),
        "ERR":  (C_LOG_ERR,  False),
        "CMD":  (C_LOG_CMD,  False),
        "INFO": (C_LOG_INFO, False),
    }
    for i, (kind, stamp, msg) in enumerate(visible_log):
        pair, bold = color_map.get(kind, (C_LOG_INFO, False))
        attr = curses.color_pair(pair) | (curses.A_BOLD if bold else 0)
        sadd(stdscr, log_top + 1 + i,
             1, f"[{stamp}] {msg}"[: w - 2], attr)

    # Log scrollbar (total items, offset from bottom)
    draw_scrollbar(
        stdscr, log_top + 1, log_rows, w - 2,
        len(log), log_max - log_scroll,   # convert "from-bottom" to "from-top"
        curses.color_pair(C_BORDER),
    )

    # ── Status bar ─────────────────────────────────────────────
    sadd(stdscr, h - 1, 0,
         f"  {status:<{w - 3}}"[: w - 1],
         curses.color_pair(C_HINT) | curses.A_DIM)

    stdscr.noutrefresh()
    curses.doupdate()
    return entry_scroll, log_scroll
