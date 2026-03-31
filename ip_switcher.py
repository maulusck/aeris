#!/usr/bin/env python3
"""
rig-ip-switcher  ·  Avionic Rig Operator Tool
Retro-amber curses TUI for nmcli IP management.
"""
import curses
import subprocess
import traceback
import json
import time
import ipaddress
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────
NMCLI      = "./nmcli"   # or "./nmcli" for testing
CON_ID     = "eth-operator"
IFACE      = "eth0"
STATE_FILE = Path.home() / ".rig-ip-switcher.json"

PREDEFINED = [
    {"name": "Office",  "ip": "192.168.1.10/24"},
    {"name": "Lab",     "ip": "10.0.0.5/24"},
    {"name": "Test VM", "ip": "172.16.0.20/16"},
]

# ─────────────────────────────────────────────────────────────
#  Color-pair indices  — semantic names only
# ─────────────────────────────────────────────────────────────
# Layout chrome
C_HDR      = 1   # amber title bar
C_HINT     = 2   # dark key-hint / status bar
C_BORDER   = 3   # dark-grey box lines
C_SECTION  = 4   # amber section labels
C_DIM      = 5   # mid-grey inactive text

# Entry row states         fg meaning
C_LIVE     = 6   # green   — IP is currently applied
C_PEND_ADD = 7   # cyan    — selected, not yet applied (will be added)
C_PEND_DEL = 8   # red     — live but deselected (will be removed)
C_CURSOR   = 9   # black/cyan bg  — cursor on neutral row
C_CUR_LIVE = 10  # black/green bg — cursor on live row
C_CUR_PADD = 11  # black/cyan bg  — cursor on pending-add row  (same as C_CURSOR visually)
C_CUR_PDEL = 12  # black/red bg   — cursor on pending-del row

# Status panel
C_STAT_LIV = 13  # live IPs line   (green dim)
C_STAT_ADD = 14  # pending add     (cyan)
C_STAT_DEL = 15  # pending remove  (red)

# Log
C_LOG_OK   = 16  # green
C_LOG_ERR  = 17  # red
C_LOG_CMD  = 18  # mid-grey
C_LOG_INFO = 19  # light-grey

# Input box
C_INPUT    = 20  # amber on near-black


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    bg = -1
    try:
        A   = 214   # amber
        CY  = 51    # cyan
        GR  = 82    # green
        RE  = 196   # red
        BLK = 16    # true black
        DGY = 236   # dark grey
        MGY = 242   # mid grey
        LGY = 248   # light grey

        curses.init_pair(C_HDR,      BLK, A)
        curses.init_pair(C_HINT,     MGY, DGY)
        curses.init_pair(C_BORDER,   DGY, bg)
        curses.init_pair(C_SECTION,  A,   bg)
        curses.init_pair(C_DIM,      MGY, bg)

        curses.init_pair(C_LIVE,     GR,  bg)
        curses.init_pair(C_PEND_ADD, CY,  bg)
        curses.init_pair(C_PEND_DEL, RE,  bg)
        curses.init_pair(C_CURSOR,   BLK, CY)
        curses.init_pair(C_CUR_LIVE, BLK, GR)
        curses.init_pair(C_CUR_PADD, BLK, CY)
        curses.init_pair(C_CUR_PDEL, BLK, RE)

        curses.init_pair(C_STAT_LIV, MGY, bg)
        curses.init_pair(C_STAT_ADD, CY,  bg)
        curses.init_pair(C_STAT_DEL, RE,  bg)

        curses.init_pair(C_LOG_OK,   GR,  bg)
        curses.init_pair(C_LOG_ERR,  RE,  bg)
        curses.init_pair(C_LOG_CMD,  MGY, bg)
        curses.init_pair(C_LOG_INFO, LGY, bg)

        curses.init_pair(C_INPUT,    A,   BLK)
    except Exception:
        # 8-colour fallback
        Y, C, G, R, W, K = (
            curses.COLOR_YELLOW, curses.COLOR_CYAN, curses.COLOR_GREEN,
            curses.COLOR_RED,    curses.COLOR_WHITE, curses.COLOR_BLACK,
        )
        curses.init_pair(C_HDR,      K, Y); curses.init_pair(C_HINT,     W, K)
        curses.init_pair(C_BORDER,   W, bg); curses.init_pair(C_SECTION, Y, bg)
        curses.init_pair(C_DIM,      W, bg)
        curses.init_pair(C_LIVE,     G, bg); curses.init_pair(C_PEND_ADD, C, bg)
        curses.init_pair(C_PEND_DEL, R, bg); curses.init_pair(C_CURSOR,  K, C)
        curses.init_pair(C_CUR_LIVE, K, G); curses.init_pair(C_CUR_PADD, K, C)
        curses.init_pair(C_CUR_PDEL, K, R)
        curses.init_pair(C_STAT_LIV, W, bg); curses.init_pair(C_STAT_ADD, C, bg)
        curses.init_pair(C_STAT_DEL, R, bg)
        curses.init_pair(C_LOG_OK,   G, bg); curses.init_pair(C_LOG_ERR,  R, bg)
        curses.init_pair(C_LOG_CMD,  W, bg); curses.init_pair(C_LOG_INFO, W, bg)
        curses.init_pair(C_INPUT,    Y, K)


# ─────────────────────────────────────────────────────────────
#  Drawing primitives
# ─────────────────────────────────────────────────────────────
def sadd(win, y, x, text, attr=0):
    """Safe clipped addstr."""
    try:
        mh, mw = win.getmaxyx()
        if y < 0 or y >= mh or x < 0 or x >= mw:
            return
        clip = text[:max(0, mw - x - 1)]
        if clip:
            win.addstr(y, x, clip, attr)
    except curses.error:
        pass

def hln(win, y, x, n, attr=0):
    try:
        mh, mw = win.getmaxyx()
        n = min(n, mw - x - 1)
        if n > 0 and 0 <= y < mh:
            win.hline(y, x, curses.ACS_HLINE, n, attr)
    except curses.error:
        pass


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────
def now_ts():
    return datetime.now().strftime("%H:%M:%S")

def is_valid_ip(ip):
    try:
        ipaddress.IPv4Interface(ip)
        return True
    except ValueError:
        return False

def normalize_ip(ip):
    return str(ipaddress.IPv4Interface(ip))

def trim(lst, n=40):
    if len(lst) > n:
        lst[:] = lst[-n:]

def log_append(log, kind, msg):
    """Stamp log entries at insertion time."""
    log.append((kind, now_ts(), msg))
    trim(log)


# ─────────────────────────────────────────────────────────────
#  Persistence
# ─────────────────────────────────────────────────────────────
def load_custom():
    if not STATE_FILE.exists():
        return []
    try:
        raw = json.loads(STATE_FILE.read_text())
        recs = raw.get("custom_ips", [])
        out = []
        for r in recs:
            if isinstance(r, str):
                out.append({"name": r, "ip": r})
            elif isinstance(r, dict) and "ip" in r:
                out.append({"name": r.get("name", r["ip"]), "ip": r["ip"]})
        return out
    except Exception:
        return []

def save_custom(entries):
    data = [{"name": e["name"], "ip": e["ip"]}
            for e in entries if e["type"] == "custom"]
    try:
        STATE_FILE.write_text(json.dumps({"custom_ips": data}, indent=2))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
#  NMCLI
# ─────────────────────────────────────────────────────────────
def run_nmcli(args, timeout=15):
    try:
        r = subprocess.run(
            [NMCLI] + args, capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except FileNotFoundError:
        return "", f"{NMCLI}: not found", 1
    except subprocess.TimeoutExpired:
        return "", "nmcli: timed out", 1

def get_active_ips(con_id):
    out, _, code = run_nmcli(["con", "show", con_id], timeout=5)
    if code != 0:
        return []
    for line in out.splitlines():
        if line.startswith("ipv4.addresses"):
            raw = line.split(":", 1)[1]
            return [ip.strip() for ip in raw.split(",") if ip.strip()]
    return []

def ensure_con(con_id, iface, log):
    """Create the nmcli connection if it does not exist."""
    _, _, code = run_nmcli(["con", "show", con_id], timeout=5)
    if code != 0:
        log_append(log, "INFO", f"Creating connection '{con_id}'")
        run_nmcli([
            "con", "add", "type", "ethernet",
            "con-name", con_id, "ifname", iface,
            "ipv4.method", "manual",
        ])

def apply_ips(con_id, ips, log, iface=IFACE):
    """mod + up with full log output. Returns list of applied IPs or None."""
    if not ips:
        log_append(log, "ERR", "Nothing selected")
        return None

    ip_str = ",".join(ips)
    ensure_con(con_id, iface, log)

    log_append(log, "CMD", f"$ nmcli con mod {con_id} ipv4.addresses {ip_str}")
    _, err, code = run_nmcli([
        "con", "mod", con_id,
        "ipv4.addresses", ip_str, "ipv4.method", "manual",
    ])
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


# ─────────────────────────────────────────────────────────────
#  Input box
# ─────────────────────────────────────────────────────────────
def curses_input(stdscr, prompt, prefill="", maxlen=40):
    """
    Floating amber input box. Full cursor editing.
    Returns stripped string or None on Esc.
    """
    curses.curs_set(1)
    h, w = stdscr.getmaxyx()
    box_w = min(w - 4, len(prompt) + maxlen + 8)
    box_y = max(1, h // 2 - 1)
    box_x = (w - box_w) // 2

    try:
        win = curses.newwin(3, box_w, box_y, box_x)
    except curses.error:
        curses.curs_set(0)
        return None

    inp_a = curses.color_pair(C_INPUT) | curses.A_BOLD
    lbl_a = curses.color_pair(C_SECTION) | curses.A_BOLD

    win.attron(inp_a)
    win.border()
    win.attroff(inp_a)

    label   = f" {prompt} "
    field_x = 2 + len(label)
    field_w = max(4, box_w - field_x - 3)
    sadd(win, 1, 2, label, lbl_a)

    buf  = list(prefill[:maxlen])
    cpos = len(buf)

    def redraw():
        start = max(0, cpos - field_w + 1)
        view  = "".join(buf)[start: start + field_w]
        sadd(win, 1, field_x, view.ljust(field_w), inp_a)
        try:
            win.move(1, field_x + (cpos - start))
        except curses.error:
            pass
        win.refresh()

    while True:
        redraw()
        ch = stdscr.getch()
        if ch in (10, 13):
            curses.curs_set(0)
            return "".join(buf).strip()
        elif ch == 27:
            curses.curs_set(0)
            return None
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if cpos > 0:
                buf.pop(cpos - 1); cpos -= 1
        elif ch == curses.KEY_DC:
            if cpos < len(buf): buf.pop(cpos)
        elif ch == curses.KEY_LEFT:  cpos = max(0, cpos - 1)
        elif ch == curses.KEY_RIGHT: cpos = min(len(buf), cpos + 1)
        elif ch == curses.KEY_HOME:  cpos = 0
        elif ch == curses.KEY_END:   cpos = len(buf)
        elif 32 <= ch <= 126 and len(buf) < maxlen:
            buf.insert(cpos, chr(ch)); cpos += 1


# ─────────────────────────────────────────────────────────────
#  Confirm dialog
# ─────────────────────────────────────────────────────────────
def confirm_dialog(stdscr, removing, adding):
    h, w = stdscr.getmaxyx()
    rows = [("  CONFIRM APPLY  ", curses.color_pair(C_CURSOR) | curses.A_BOLD)]
    for ip in removing: rows.append((f"  - {ip}", curses.color_pair(C_PEND_DEL)))
    for ip in adding:   rows.append((f"  + {ip}", curses.color_pair(C_PEND_ADD) | curses.A_BOLD))
    if not removing and not adding:
        rows.append(("  (no diff)", curses.color_pair(C_DIM)))
    rows += [("", 0), ("  [Y] apply   [N] cancel",
               curses.color_pair(C_SECTION) | curses.A_BOLD)]

    box_h = len(rows) + 2
    box_w = min(w - 6, max(len(t) for t, _ in rows) + 4)
    try:
        win = curses.newwin(box_h, box_w, h // 2 - box_h // 2, (w - box_w) // 2)
    except curses.error:
        return True

    win.attron(curses.color_pair(C_CURSOR) | curses.A_BOLD)
    win.border()
    win.attroff(curses.color_pair(C_CURSOR) | curses.A_BOLD)
    for i, (text, attr) in enumerate(rows):
        sadd(win, i + 1, 1, text[:box_w - 2], attr)
    win.refresh()

    while True:
        ch = stdscr.getch()
        if ch in (ord("y"), ord("Y"), 10, 13): return True
        if ch in (ord("n"), ord("N"), 27):     return False


# ─────────────────────────────────────────────────────────────
#  TUI draw
# ─────────────────────────────────────────────────────────────
HINT = " jk/↑↓:move  SPC:toggle  N:add  E:rename  D:del  A:apply  R:refresh  Q:quit"
NAME_W = 13

# Entry-row color matrix: (is_cursor, state) -> color_pair_index, bold
#   state: "live_sel"   = live + selected (no change)
#          "live_desel" = live + deselected (pending removal)
#          "dead_sel"   = not live + selected (pending add)
#          "dead_desel" = not live + deselected (neutral)
_ROW_COLORS = {
    # (cursor, state)          pair        bold
    (True,  "live_sel"):   (C_CUR_LIVE,  True),
    (True,  "live_desel"): (C_CUR_PDEL,  True),
    (True,  "dead_sel"):   (C_CUR_PADD,  True),
    (True,  "dead_desel"): (C_CURSOR,    True),
    (False, "live_sel"):   (C_LIVE,      True),
    (False, "live_desel"): (C_PEND_DEL,  True),
    (False, "dead_sel"):   (C_PEND_ADD,  True),
    (False, "dead_desel"): (0,            False),
}

def _row_attr(is_cursor, is_live, is_sel):
    if is_live and is_sel:   state = "live_sel"
    elif is_live:            state = "live_desel"
    elif is_sel:             state = "dead_sel"
    else:                    state = "dead_desel"
    pair, bold = _ROW_COLORS[(is_cursor, state)]
    attr = (curses.color_pair(pair) if pair else 0)
    if bold: attr |= curses.A_BOLD
    return attr


def draw_ui(stdscr, entries, selected, cursor, entry_scroll,
            log, log_scroll, current_ips, status):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    if h < 12 or w < 44:
        sadd(stdscr, 0, 0, f"Terminal too small ({w}x{h})", curses.A_BOLD)
        stdscr.noutrefresh(); curses.doupdate(); return

    # ── Title bar ──────────────────────────────
    title = f"  RIG IP SWITCHER  \u25b8  {CON_ID}  "
    sadd(stdscr, 0, 0, title.ljust(w - 1),
         curses.color_pair(C_HDR) | curses.A_BOLD)
    ts = now_ts()
    sadd(stdscr, 0, w - len(ts) - 2, ts,
         curses.color_pair(C_HDR) | curses.A_DIM)

    # ── Key hint bar ───────────────────────────
    sadd(stdscr, 1, 0, HINT[:w - 1], curses.color_pair(C_HINT))

    # ── Status panel: LIVE / ADD / DEL ─────────
    new_ips     = [entries[i]["ip"] for i in sorted(selected)]
    pend_add    = [ip for ip in new_ips    if ip not in current_ips]
    pend_del    = [ip for ip in current_ips if ip not in new_ips]
    live_stable = [ip for ip in current_ips if ip in new_ips]

    row = 3
    sadd(stdscr, row, 0,
         (" LIVE  : " + (", ".join(current_ips) or "\u2014"))[:w - 1],
         curses.color_pair(C_STAT_LIV))
    row += 1
    if pend_add:
        sadd(stdscr, row, 0,
             (" + ADD : " + ", ".join(pend_add))[:w - 1],
             curses.color_pair(C_STAT_ADD) | curses.A_BOLD)
        row += 1
    if pend_del:
        sadd(stdscr, row, 0,
             (" - DEL : " + ", ".join(pend_del))[:w - 1],
             curses.color_pair(C_STAT_DEL) | curses.A_BOLD)
        row += 1

    hln(stdscr, row, 0, w - 1, curses.color_pair(C_BORDER))
    row += 1
    list_top = row

    # ── Entry list ─────────────────────────────
    # Reserve bottom rows: 1 border + log_visible + 1 status
    LOG_PANEL_H = 7   # lines reserved for log (border + entries)
    list_bot    = h - LOG_PANEL_H - 1   # exclusive
    list_h      = max(1, list_bot - list_top)

    # Build flat render list with section headers injected
    render = []  # each item: ("header", label) | ("entry", idx)
    prev_type = None
    for idx, e in enumerate(entries):
        if e["type"] != prev_type:
            render.append(("header", e["type"]))
            prev_type = e["type"]
        render.append(("entry", idx))

    # Clamp scroll so cursor's entry row stays visible
    # First find cursor's render index
    cursor_render = next(
        (ri for ri, item in enumerate(render)
         if item[0] == "entry" and item[1] == cursor),
        0,
    )
    # entry_scroll is in render-lines; clamp it
    entry_scroll = max(0, min(entry_scroll, max(0, len(render) - list_h)))
    # Auto-scroll to keep cursor visible
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
            idx = item[1]
            e   = entries[idx]
            is_cur  = idx == cursor
            is_live = e["ip"] in current_ips
            is_sel  = idx in selected
            tick    = "\u25c9" if is_sel else "\u25cb"
            name    = e["name"][:NAME_W].ljust(NAME_W)
            line    = f"  {tick} {name}  {e['ip']}"
            sadd(stdscr, rrow, 0, line[:w - 1], _row_attr(is_cur, is_live, is_sel))
        rrow += 1

    # Scroll indicator (right margin)
    if len(render) > list_h:
        pct = int(entry_scroll / max(1, len(render) - list_h) * (list_h - 1))
        for li in range(list_h):
            ch = "\u2588" if li == pct else "\u2591"
            sadd(stdscr, list_top + li, w - 2,
                 ch, curses.color_pair(C_BORDER))

    # ── Log panel ──────────────────────────────
    log_top = h - LOG_PANEL_H - 1
    hln(stdscr, log_top, 0, w - 1, curses.color_pair(C_BORDER))
    sadd(stdscr, log_top, 2, " LOG ",
         curses.color_pair(C_SECTION) | curses.A_BOLD)

    log_rows  = LOG_PANEL_H - 1   # usable lines inside panel
    log_max   = max(0, len(log) - log_rows)
    log_scroll = max(0, min(log_scroll, log_max))
    # Default: pin to bottom (newest)
    if log_scroll == 0:
        visible_log = log[-log_rows:]
    else:
        start = log_max - log_scroll
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
        sadd(stdscr, log_top + 1 + i, 1,
             f"[{stamp}] {msg}"[:w - 2], attr)

    # Scroll indicator for log
    if len(log) > log_rows:
        pct = int((1 - log_scroll / max(1, log_max)) * (log_rows - 1))
        for li in range(log_rows):
            ch = "\u2588" if li == pct else "\u2591"
            sadd(stdscr, log_top + 1 + li, w - 2,
                 ch, curses.color_pair(C_BORDER))

    # ── Status bar ─────────────────────────────
    sadd(stdscr, h - 1, 0, f"  {status:<{w - 3}}"[:w - 1],
         curses.color_pair(C_HINT) | curses.A_DIM)

    stdscr.noutrefresh()
    curses.doupdate()


# ─────────────────────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────────────────────
def ui_loop(stdscr):
    init_colors()
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(500)   # tick for clock refresh

    entries = [
        {"name": d["name"], "ip": d["ip"], "type": "predefined"}
        for d in PREDEFINED
    ]
    for rec in load_custom():
        entries.append({"name": rec["name"], "ip": rec["ip"], "type": "custom"})

    current_ips  = get_active_ips(CON_ID)
    selected     = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
    cursor       = 0
    entry_scroll = 0
    log          = []       # (kind, timestamp, msg)
    log_scroll   = 0        # 0 = pinned to bottom; N = scrolled back N steps
    status       = "Ready"

    while True:
        # Auto-recompute entry_scroll to keep cursor in view (draw_ui handles it,
        # but we pass it in and get it back via the clamp logic there)
        draw_ui(stdscr, entries, selected, cursor, entry_scroll,
                log, log_scroll, current_ips, status)

        key = stdscr.getch()
        if key == -1:
            continue   # timer tick

        # ── Navigation ────────────────────────
        if key in (curses.KEY_UP, ord("k"), ord("K")):
            cursor = (cursor - 1) % max(1, len(entries))
            status = ""

        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            cursor = (cursor + 1) % max(1, len(entries))
            status = ""

        # ── Entry list scroll (Ctrl-U / Ctrl-D style, or PgUp/PgDn) ──
        elif key in (curses.KEY_PPAGE,):
            entry_scroll = max(0, entry_scroll - 5)
        elif key in (curses.KEY_NPAGE,):
            entry_scroll += 5   # clamped in draw_ui

        # ── Log scroll ([ and ] or Alt-j/k) ──
        elif key == ord("["):
            log_scroll = min(max(0, len(log) - 1), log_scroll + 1)
        elif key == ord("]"):
            log_scroll = max(0, log_scroll - 1)

        # ── Toggle ────────────────────────────
        elif key == ord(" "):
            selected.symmetric_difference_update({cursor})
            ip = entries[cursor]["ip"]
            status = f"{ip} {'selected' if cursor in selected else 'deselected'}"

        # ── Add custom IP ─────────────────────
        elif key in (ord("n"), ord("N")):
            ip = curses_input(stdscr, "New IP (x.x.x.x/prefix):")
            if ip is None:
                status = "Cancelled"
            elif not is_valid_ip(ip):
                log_append(log, "ERR", f"Invalid IP: {ip}")
                status = "Invalid IP"
            else:
                ip = normalize_ip(ip)
                if ip in {e["ip"] for e in entries}:
                    log_append(log, "ERR", f"Duplicate: {ip}")
                    status = "Duplicate"
                else:
                    name = curses_input(stdscr, "Label (blank = use IP):",
                                        prefill="", maxlen=NAME_W) or ip
                    entries.append({"name": name, "ip": ip, "type": "custom"})
                    selected.add(len(entries) - 1)
                    save_custom(entries)
                    log_append(log, "OK", f"Added {name} ({ip})")
                    status = f"Added {name}"

        # ── Rename custom ─────────────────────
        elif key in (ord("e"), ord("E")):
            e = entries[cursor]
            if e["type"] != "custom":
                log_append(log, "ERR", "Predefined labels are fixed")
                status = "Cannot rename predefined"
            else:
                new_name = curses_input(stdscr, "New label:",
                                        prefill=e["name"], maxlen=NAME_W)
                if new_name is None:
                    status = "Cancelled"
                elif new_name:
                    old = e["name"]
                    e["name"] = new_name
                    save_custom(entries)
                    log_append(log, "OK", f"Renamed: {old} -> {new_name}")
                    status = f"Renamed to {new_name}"
                else:
                    status = "Empty label — no change"

        # ── Delete custom ─────────────────────
        elif key in (ord("d"), ord("D")):
            e = entries[cursor]
            if e["type"] != "custom":
                log_append(log, "ERR", "Cannot delete predefined entry")
                status = "Predefined — protected"
            else:
                entries.pop(cursor)
                selected = {i if i < cursor else i - 1
                            for i in selected if i != cursor}
                save_custom(entries)
                cursor = max(0, min(cursor, len(entries) - 1))
                log_append(log, "OK", f"Deleted {e['name']} ({e['ip']})")
                status = f"Deleted {e['name']}"

        # ── Apply ─────────────────────────────
        elif key in (ord("a"), ord("A")):
            new_ips = [entries[i]["ip"] for i in sorted(selected)]
            if not new_ips:
                log_append(log, "ERR", "Nothing selected")
                status = "Select IPs first"
            else:
                removing = [ip for ip in current_ips if ip not in new_ips]
                adding   = [ip for ip in new_ips    if ip not in current_ips]
                if confirm_dialog(stdscr, removing, adding):
                    status = "Applying..."
                    draw_ui(stdscr, entries, selected, cursor, entry_scroll,
                            log, log_scroll, current_ips, status)
                    result = apply_ips(CON_ID, new_ips, log)
                    if result:
                        current_ips = result
                        status = "Applied OK"
                    else:
                        status = "Apply FAILED — see log"
                else:
                    log_append(log, "INFO", "Apply cancelled")
                    status = "Cancelled"

        # ── Refresh ───────────────────────────
        elif key in (ord("r"), ord("R")):
            current_ips = get_active_ips(CON_ID)
            selected    = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
            log_append(log, "INFO", f"Refreshed: {', '.join(current_ips) or '—'}")
            status = "Refreshed"

        # ── Quit ──────────────────────────────
        elif key in (ord("q"), ord("Q"), 27):
            break


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────
def main():
    try:
        curses.wrapper(ui_loop)
    except KeyboardInterrupt:
        print("\nExited.")
    except Exception:
        curses.endwin()
        traceback.print_exc()

if __name__ == "__main__":
    main()