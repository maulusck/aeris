#!/usr/bin/env python3
import curses, subprocess, json, time, traceback
from pathlib import Path
import ipaddress

NMCLI = "./nmcli"
CON_ID = "eth-operator"
IFACE = "eth0"
STATE_FILE = Path.home() / ".rig-ip-switcher.json"

PREDEFINED = [
    {"name": "Office", "ip": "192.168.1.10/24"},
    {"name": "Lab", "ip": "10.0.0.5/24"},
    {"name": "Test VM", "ip": "172.16.0.20/16"},
]


# ─────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────
def load_custom():
    try:
        return json.loads(STATE_FILE.read_text()).get("custom_ips", [])
    except Exception:
        return []


def save_custom(entries):
    STATE_FILE.write_text(
        json.dumps(
            {"custom_ips": [e for e in entries if e["type"] == "custom"]}, indent=2
        )
    )


# ─────────────────────────────────────────────
# NMCLI
# ─────────────────────────────────────────────
def nmcli(args):
    try:
        r = subprocess.run([NMCLI] + args, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), 1


def get_active():
    out, _, code = nmcli(["con", "show", CON_ID])
    if code != 0:
        return []
    for l in out.splitlines():
        if l.startswith("ipv4.addresses"):
            return [x.strip() for x in l.split(":", 1)[1].split(",") if x.strip()]
    return []


def apply_ips(entries, selected, log):
    ips = [entries[i]["ip"] for i in sorted(selected)]
    if not ips:
        log.append(("ERR", "No IPs selected"))
        return None

    ip_str = ",".join(ips)
    nmcli(["con", "mod", CON_ID, "ipv4.addresses", ip_str, "ipv4.method", "manual"])
    _, err, code = nmcli(["con", "up", CON_ID])
    if code != 0:
        log.append(("ERR", err))
        return None

    log.append(("OK", f"Applied {ip_str}"))
    return ips


# ─────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────
def valid_ip(ip):
    try:
        ipaddress.IPv4Interface(ip)
        return True
    except:
        return False


def norm(ip):
    return str(ipaddress.IPv4Interface(ip))


# ─────────────────────────────────────────────
# Colors (state-driven)
# ─────────────────────────────────────────────
def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)  # ACTIVE
    curses.init_pair(2, curses.COLOR_CYAN, -1)  # PENDING
    curses.init_pair(3, 242, -1)  # INACTIVE (grey)
    curses.init_pair(4, curses.COLOR_BLACK, 51)  # CURSOR


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
def draw(stdscr, entries, selected, cursor, active, log, status):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    stdscr.addstr(0, 0, f" RIG IP SWITCHER ▸ {CON_ID} ".ljust(w - 1), curses.A_BOLD)

    # status lines
    pending = [entries[i]["ip"] for i in selected]
    stdscr.addstr(2, 0, "LIVE : " + (", ".join(active) or "—"))
    stdscr.addstr(3, 0, "PEND : " + (", ".join(pending) or "—"), curses.color_pair(2))

    row = 5
    prev = None

    for i, e in enumerate(entries):
        if e["type"] != prev:
            stdscr.addstr(row, 0, f" {e['type'].upper()} ", curses.A_BOLD)
            row += 1
            prev = e["type"]

        is_active = e["ip"] in active
        is_pending = i in selected

        # state → color
        if is_active:
            attr = curses.color_pair(1)
        elif is_pending:
            attr = curses.color_pair(2)
        else:
            attr = curses.color_pair(3)

        if i == cursor:
            attr |= curses.A_REVERSE

        mark = "◉" if is_pending else "○"
        stdscr.addstr(row, 0, f" {mark} {e['name']:<12} {e['ip']}"[: w - 1], attr)
        row += 1
        if row >= h - 6:
            break

    # log
    for i, (k, m) in enumerate(log[-5:]):
        stdscr.addstr(h - 6 + i, 0, f"{k}: {m}"[: w - 1])

    stdscr.addstr(h - 1, 0, status[: w - 1], curses.A_DIM)
    stdscr.refresh()


# ─────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────
def prompt(stdscr, text):
    curses.echo()
    stdscr.addstr(0, 0, " " * 80)
    stdscr.addstr(0, 0, text)
    stdscr.refresh()
    val = stdscr.getstr(0, len(text)).decode()
    curses.noecho()
    return val.strip()


# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────
def ui(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    init_colors()

    entries = [
        {"name": x["name"], "ip": x["ip"], "type": "predefined"} for x in PREDEFINED
    ]
    entries += load_custom()

    active = get_active()
    selected = {i for i, e in enumerate(entries) if e["ip"] in active}

    cursor = 0
    log = []
    status = "Ready"

    while True:
        draw(stdscr, entries, selected, cursor, active, log, status)
        k = stdscr.getch()

        if k in (curses.KEY_UP, ord("k")):
            cursor = (cursor - 1) % len(entries)

        elif k in (curses.KEY_DOWN, ord("j")):
            cursor = (cursor + 1) % len(entries)

        elif k == ord(" "):
            selected.symmetric_difference_update({cursor})

        elif k == ord("n"):
            ip = prompt(stdscr, "IP: ")
            if not valid_ip(ip):
                status = "Invalid IP"
                continue
            if ip in {e["ip"] for e in entries}:
                status = "Duplicate"
                continue
            name = prompt(stdscr, "Name: ") or ip
            entries.append({"name": name, "ip": norm(ip), "type": "custom"})
            selected.add(len(entries) - 1)
            save_custom(entries)

        elif k == ord("d"):
            if entries[cursor]["type"] != "custom":
                status = "Protected"
                continue
            entries.pop(cursor)
            selected = {i for i in selected if i != cursor}
            save_custom(entries)

        elif k == ord("a"):
            res = apply_ips(entries, selected, log)
            if res:
                active = res
                status = "Applied"

        elif k == ord("r"):
            active = get_active()
            selected = {i for i, e in enumerate(entries) if e["ip"] in active}

        elif k in (ord("q"), 27):
            break


# ─────────────────────────────────────────────
def main():
    try:
        curses.wrapper(ui)
    except Exception:
        curses.endwin()
        traceback.print_exc()


if __name__ == "__main__":
    main()
