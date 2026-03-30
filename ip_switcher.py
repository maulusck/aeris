#!/usr/bin/env python3
"""
rig-ip-switcher – NMCLI IP management TUI
Retro-terminal aesthetic, curses-based, persistent custom IPs with names.
"""
import curses
import subprocess
import traceback
import json
import time
from pathlib import Path
import ipaddress

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
NMCLI = "./nmcli"
CON_ID = "eth-operator"
STATE_FILE = Path.home() / ".rig-ip-switcher.json"
IFACE = "eth0"

# ─────────────────────────────────────────────
#  Color pair indices
# ─────────────────────────────────────────────
C_HEADER = 1  # title bar
C_SEL = 2  # highlighted row
C_ACTIVE = 3  # row whose IP is currently live
C_SEL_ACT = 4  # highlighted + active
C_SECTION = 5  # section labels
C_LOG_OK = 6  # log: success / info
C_LOG_ERR = 7  # log: error
C_LOG_CMD = 8  # log: nmcli command echo
C_HINT = 9  # keybind bar
C_DIFF_CUR = 10  # current IP line
C_DIFF_NEW = 11  # pending IP line
C_BORDER = 12  # box-drawing lines
C_INPUT = 13  # input box text

# ─────────────────────────────────────────────
#  Predefined devices
# ─────────────────────────────────────────────
PREDEFINED = [
    {"name": "Office", "ip": "192.168.1.10/24"},
    {"name": "Lab", "ip": "10.0.0.5/24"},
    {"name": "Test VM", "ip": "172.16.0.20/16"},
]


# ─────────────────────────────────────────────
#  Persistence
# ─────────────────────────────────────────────
def load_custom_ips():
    if not STATE_FILE.exists():
        return []
    try:
        data = json.loads(STATE_FILE.read_text())
        return data.get("custom_ips", [])
    except Exception:
        return []


def save_custom_ips(entries):
    custom = [
        {"name": e["name"], "ip": e["ip"]} for e in entries if e["type"] == "custom"
    ]
    STATE_FILE.write_text(json.dumps({"custom_ips": custom}, indent=2))


# ─────────────────────────────────────────────
#  NMCLI helpers
# ─────────────────────────────────────────────
def run_nmcli(args, log_lines=None):
    cmd_str = "nmcli " + " ".join(args)
    if log_lines is not None:
        log_lines.append(("CMD", f"$ {cmd_str}"))
    try:
        r = subprocess.run([NMCLI] + args, capture_output=True, text=True, timeout=15)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except FileNotFoundError:
        return "", f"{NMCLI}: not found", 1
    except subprocess.TimeoutExpired:
        return "", "nmcli timed out", 1


def get_active_ips(con_id):
    out, _, code = run_nmcli(["con", "show", con_id])
    if code != 0:
        return []
    for line in out.splitlines():
        if line.startswith("ipv4.addresses"):
            raw = line.split(":", 1)[1]
            return [ip.strip() for ip in raw.split(",") if ip.strip()]
    return []


def con_exists(con_id):
    _, _, code = run_nmcli(["con", "show", con_id])
    return code == 0


def create_con_if_missing(con_id, iface, log_lines):
    if not con_exists(con_id):
        log_lines.append(("INFO", f"Creating connection '{con_id}'"))
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
            ],
            log_lines,
        )


def apply_changes(con_id, entries, selected, log_lines, iface=IFACE):
    ips = [entries[i]["ip"] for i in sorted(selected)]
    if not ips:
        log_lines.append(("ERR", "No IPs selected – nothing to apply"))
        return None

    ip_str = ",".join(ips)
    create_con_if_missing(con_id, iface, log_lines)

    _, err, code = run_nmcli(
        ["con", "mod", con_id, "ipv4.addresses", ip_str, "ipv4.method", "manual"],
        log_lines,
    )
    if code != 0:
        log_lines.append(("ERR", f"mod failed: {err or 'unknown'}"))
        return None

    _, err, code = run_nmcli(["con", "up", con_id], log_lines)
    if code != 0:
        log_lines.append(("ERR", f"up failed: {err or 'unknown'}"))
        return None

    log_lines.append(("OK", f"Applied: {ip_str}"))
    _trim_log(log_lines)
    return ips


def _trim_log(log_lines, maxlen=20):
    if len(log_lines) > maxlen:
        log_lines[:] = log_lines[-maxlen:]


# ─────────────────────────────────────────────
#  IP validation
# ─────────────────────────────────────────────
def is_valid_ip(ip):
    try:
        ipaddress.IPv4Interface(ip)
        return True
    except ValueError:
        return False


def normalize_ip(ip):
    return str(ipaddress.IPv4Interface(ip))


# ─────────────────────────────────────────────
#  Color init
# ─────────────────────────────────────────────
def init_colors():
    curses.start_color()
    curses.use_default_colors()
    try:
        curses.init_pair(C_HEADER, curses.COLOR_BLACK, 214)  # amber bar
        curses.init_pair(C_SEL, curses.COLOR_BLACK, 51)  # cyan sel
        curses.init_pair(C_ACTIVE, 82, -1)  # green fg
        curses.init_pair(C_SEL_ACT, curses.COLOR_BLACK, 82)
        curses.init_pair(C_SECTION, 214, -1)
        curses.init_pair(C_LOG_OK, 82, -1)
        curses.init_pair(C_LOG_ERR, 196, -1)
        curses.init_pair(C_LOG_CMD, 242, -1)
        curses.init_pair(C_HINT, curses.COLOR_BLACK, 236)
        curses.init_pair(C_DIFF_CUR, 242, -1)
        curses.init_pair(C_DIFF_NEW, 51, -1)
        curses.init_pair(C_BORDER, 236, -1)
        curses.init_pair(C_INPUT, 214, 232)
    except Exception:
        curses.init_pair(C_HEADER, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(C_SEL, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(C_ACTIVE, curses.COLOR_GREEN, -1)
        curses.init_pair(C_SEL_ACT, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(C_SECTION, curses.COLOR_YELLOW, -1)
        curses.init_pair(C_LOG_OK, curses.COLOR_GREEN, -1)
        curses.init_pair(C_LOG_ERR, curses.COLOR_RED, -1)
        curses.init_pair(C_LOG_CMD, curses.COLOR_WHITE, -1)
        curses.init_pair(C_HINT, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(C_DIFF_CUR, curses.COLOR_WHITE, -1)
        curses.init_pair(C_DIFF_NEW, curses.COLOR_CYAN, -1)
        curses.init_pair(C_BORDER, curses.COLOR_WHITE, -1)
        curses.init_pair(C_INPUT, curses.COLOR_YELLOW, curses.COLOR_BLACK)


# ─────────────────────────────────────────────
#  Safe addstr helper
# ─────────────────────────────────────────────
def safe_add(win, y, x, text, attr=0):
    try:
        h, w = win.getmaxyx()
        if y < 0 or y >= h or x >= w:
            return
        clip = text[: max(0, w - x - 1)]
        if clip:
            win.addstr(y, x, clip, attr)
    except curses.error:
        pass


def hline(win, y, x, ch, n, attr=0):
    try:
        win.hline(y, x, ch, n, attr)
    except curses.error:
        pass


# ─────────────────────────────────────────────
#  Input box
# ─────────────────────────────────────────────
def curses_input(stdscr, prompt, maxlen=40):
    curses.curs_set(1)
    h, w = stdscr.getmaxyx()
    box_w = min(w - 4, maxlen + len(prompt) + 6)
    box_x = (w - box_w) // 2
    box_y = h - 6
    try:
        win = curses.newwin(3, box_w, box_y, box_x)
    except curses.error:
        curses.curs_set(0)
        return None

    inp_attr = curses.color_pair(C_INPUT) | curses.A_BOLD
    brd_attr = curses.color_pair(C_BORDER)

    win.attron(inp_attr)
    win.border()
    win.attroff(inp_attr)
    label = f" {prompt} "
    safe_add(win, 1, 2, label, curses.color_pair(C_SECTION) | curses.A_BOLD)
    field_x = 2 + len(label)
    field_w = box_w - field_x - 2
    win.refresh()
    buffer = ""
    while True:
        field_str = (buffer + " " * field_w)[:field_w]
        safe_add(win, 1, field_x, field_str, inp_attr)
        try:
            win.move(1, field_x + len(buffer))
        except curses.error:
            pass
        win.refresh()
        ch = stdscr.getch()
        if ch in (10, 13):  # Enter
            curses.curs_set(0)
            del win
            stdscr.touchwin()
            stdscr.refresh()
            return buffer.strip()
        elif ch == 27:  # Esc
            curses.curs_set(0)
            del win
            stdscr.touchwin()
            stdscr.refresh()
            return None
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            buffer = buffer[:-1]
        elif 32 <= ch <= 126 and len(buffer) < maxlen:
            buffer += chr(ch)


# ─────────────────────────────────────────────
#  TUI Draw
# ─────────────────────────────────────────────
KEYS_HINT = "↑↓/jk:move  SPC:toggle  N:add  E:edit  D:del  A:apply  R:refresh  Q:quit"


def draw_ui(stdscr, entries, selected, cursor, log_lines, current_ips, status_msg):
    """
    Draw the full TUI:
    - LIVE / PEND / REMOVE shows only actual pending changes
    - Entry list highlights active, selected, pending removal
    - Log and status bar
    """
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # ─── Title & key hint ───
    safe_add(stdscr, 0, 0, f"  RIG IP SWITCHER ▸ {CON_ID}  ".ljust(w-1),
             curses.color_pair(C_HEADER)|curses.A_BOLD)
    safe_add(stdscr, 1, 0, KEYS_HINT.ljust(w-1), curses.color_pair(C_HINT))

    # ─── Compute pending changes ───
    new_ips = [entries[i]["ip"] for i in sorted(selected)]
    pending_add = [ip for ip in new_ips if ip not in current_ips]
    pending_remove = [ip for ip in current_ips if ip not in new_ips]
    live_display = [ip for ip in current_ips if ip not in pending_remove]

    # ─── LIVE / PEND / REMOVE panel ───
    safe_add(stdscr, 3, 0, " LIVE  : " + (", ".join(live_display) or "—")[:w-1], curses.color_pair(C_DIFF_CUR))
    safe_add(stdscr, 4, 0, " PEND  : " + (", ".join(pending_add) or "—")[:w-1], curses.color_pair(C_DIFF_NEW)|curses.A_BOLD)
    if pending_remove:
        safe_add(stdscr, 5, 0, "REMOVE : " + ", ".join(pending_remove)[:w-1], curses.color_pair(C_LOG_ERR)|curses.A_BOLD)
        hline_row = 6
    else:
        hline_row = 5

    hline(stdscr, hline_row, 0, curses.ACS_HLINE, w-1, curses.color_pair(C_BORDER))

    # ─── Entry list ───
    row = hline_row + 1
    prev_type = None
    for idx, e in enumerate(entries):
        if e["type"] != prev_type:
            label = " PREDEFINED" if e["type"]=="predefined" else " CUSTOM"
            safe_add(stdscr, row, 0, label, curses.color_pair(C_SECTION)|curses.A_BOLD|curses.A_UNDERLINE)
            row += 1
            prev_type = e["type"]

        if row >= h-8:
            safe_add(stdscr, row, 0, "  … (more entries)", curses.color_pair(C_LOG_CMD))
            row += 1
            break

        # ─── State flags ───
        is_cur = idx == cursor
        ip = e["ip"]
        is_live = ip in current_ips
        is_sel = idx in selected
        pending_disable = is_live and not is_sel
        tick = "◉" if is_sel else "○"

        # ─── Determine color ───
        if is_cur and is_live:
            attr = curses.color_pair(C_SEL_ACT) | curses.A_BOLD
        elif is_cur:
            attr = curses.color_pair(C_SEL) | curses.A_BOLD
        elif pending_disable:
            attr = curses.color_pair(C_LOG_ERR) | curses.A_BOLD
        elif is_live:
            attr = curses.color_pair(C_ACTIVE) | curses.A_BOLD
        elif is_sel:
            attr = curses.color_pair(C_DIFF_NEW)
        else:
            attr = 0

        # ─── Line text ───
        name = e["name"][:12]  # truncate
        line = f"  {tick} {name:<12} {ip}"
        safe_add(stdscr, row, 0, line[:w-1], attr)
        row += 1

    # ─── Log panel ───
    log_h = min(8, len(log_lines) + 2)
    log_top = h - log_h - 1
    hline(stdscr, log_top, 0, curses.ACS_HLINE, w-1, curses.color_pair(C_BORDER))
    safe_add(stdscr, log_top, 2, " LOG ", curses.color_pair(C_SECTION)|curses.A_BOLD)
    visible = log_lines[-(log_h-1):]
    for i, (kind, msg) in enumerate(visible):
        ts = time.strftime("%H:%M:%S")
        msg_ts = f"[{ts}] {msg}"
        if kind == "ERR": attr = curses.color_pair(C_LOG_ERR)
        elif kind == "OK": attr = curses.color_pair(C_LOG_OK)|curses.A_BOLD
        elif kind == "CMD": attr = curses.color_pair(C_LOG_CMD)
        else: attr = curses.color_pair(C_DIFF_CUR)
        safe_add(stdscr, log_top + 1 + i, 2, msg_ts[:w-3], attr)

    # ─── Status bar ───
    status = f" {status_msg:<{w-12}} {time.strftime('%H:%M:%S')} "
    safe_add(stdscr, h-1, 0, status[:w-1], curses.color_pair(C_HINT)|curses.A_DIM)

    stdscr.noutrefresh()
    curses.doupdate()

# ─────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────
def ui_loop(stdscr):
    init_colors()
    curses.curs_set(0)
    stdscr.keypad(True)
    entries = [
        {"name": d["name"], "ip": d["ip"], "type": "predefined"} for d in PREDEFINED
    ]
    for e in load_custom_ips():
        entries.append(
            {"name": e.get("name", e["ip"]), "ip": e["ip"], "type": "custom"}
        )
    current_ips = get_active_ips(CON_ID)
    selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
    cursor = 0
    log_lines = []
    status_msg = "Ready"

    while True:
        draw_ui(stdscr, entries, selected, cursor, log_lines, current_ips, status_msg)
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k"), ord("K")):
            cursor = (cursor - 1) % len(entries)
            status_msg = ""
        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            cursor = (cursor + 1) % len(entries)
            status_msg = ""
        elif key == ord(" "):
            selected.symmetric_difference_update({cursor})
            ip = entries[cursor]["ip"]
            state = "selected" if cursor in selected else "deselected"
            status_msg = f"{ip} {state}"
        elif key in (ord("n"), ord("N")):
            ip = curses_input(stdscr, "New IP (x.x.x.x/xx):")
            if ip is None:
                log_lines.append(("INFO", "Add cancelled"))
                status_msg = "Cancelled"
            elif not is_valid_ip(ip):
                log_lines.append(("ERR", f"Invalid IP: {ip}"))
                status_msg = "Invalid IP"
            else:
                ip = normalize_ip(ip)
                if ip in {e["ip"] for e in entries}:
                    log_lines.append(("ERR", f"Duplicate: {ip}"))
                    status_msg = "Duplicate IP"
                else:
                    name = curses_input(stdscr, f"Name for {ip}:") or ip
                    entries.append({"name": name, "ip": ip, "type": "custom"})
                    selected.add(len(entries) - 1)
                    save_custom_ips(entries)
                    log_lines.append(("OK", f"Added {ip} ({name})"))
                    status_msg = f"Added {ip}"
            _trim_log(log_lines)
        elif key in (ord("e"), ord("E")):
            e = entries[cursor]
            if e["type"] != "custom":
                log_lines.append(("ERR", "Cannot rename predefined IP"))
                status_msg = "Predefined – protected"
            else:
                name = curses_input(stdscr, f"Name for {e['ip']}:")
                if name:
                    e["name"] = name
                    save_custom_ips(entries)
                    log_lines.append(("OK", f"Renamed to {name}"))
                    status_msg = f"Renamed to {name}"
        elif key in (ord("d"), ord("D")):
            e = entries[cursor]
            if e["type"] != "custom":
                log_lines.append(("ERR", "Cannot delete predefined entry"))
                status_msg = "Predefined – protected"
            else:
                log_lines.append(("OK", f"Deleted {e['ip']} ({e['name']})"))
                entries.pop(cursor)
                selected = {i if i < cursor else i - 1 for i in selected if i != cursor}
                save_custom_ips(entries)
                cursor = max(0, min(cursor, len(entries) - 1))
                status_msg = f"Deleted {e['ip']}"
            _trim_log(log_lines)
        elif key in (ord("a"), ord("A")):
            status_msg = "Applying…"
            draw_ui(
                stdscr, entries, selected, cursor, log_lines, current_ips, status_msg
            )
            result = apply_changes(CON_ID, entries, selected, log_lines)
            if result:
                current_ips = result
                status_msg = "Applied OK"
            else:
                status_msg = "Apply FAILED – see log"
            _trim_log(log_lines)
        elif key in (ord("r"), ord("R")):
            current_ips = get_active_ips(CON_ID)
            selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
            log_lines.append(("INFO", f"Refreshed: {', '.join(current_ips) or '—'}"))
            status_msg = "Refreshed"
            _trim_log(log_lines)
        elif key in (ord("q"), ord("Q"), 27):
            break


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
def main():
    try:
        curses.wrapper(ui_loop)
    except KeyboardInterrupt:
        print("\nExited cleanly.")
    except Exception:
        curses.endwin()
        traceback.print_exc()


if __name__ == "__main__":
    main()
