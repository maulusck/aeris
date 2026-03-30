#!/usr/bin/env python3
import curses
import subprocess
import traceback
import json
from pathlib import Path
import ipaddress

# -----------------------
# Config
# -----------------------
NMCLI = "./nmcli"  # Change to "/usr/bin/nmcli" in production
CON_ID = "eth-operator"
STATE_FILE = Path.home() / ".rig-ip-switcher.json"

# -----------------------
# Predefined devices
# -----------------------
predefined_devices = [
    {"name": "Office", "ip": "192.168.1.10/24"},
    {"name": "Lab", "ip": "10.0.0.5/24"},
    {"name": "Test VM", "ip": "172.16.0.20/16"},
]

# -----------------------
# Persistence
# -----------------------
def load_custom_ips():
    if not STATE_FILE.exists():
        return []
    try:
        data = json.loads(STATE_FILE.read_text())
        return data.get("custom_ips", [])
    except:
        return []

def save_custom_ips(entries):
    custom_ips = [e["ip"] for e in entries if e["type"] == "custom"]
    STATE_FILE.write_text(json.dumps({"custom_ips": custom_ips}, indent=2))

# -----------------------
# NMCLI interaction
# -----------------------
def run_nmcli(args):
    try:
        result = subprocess.run([NMCLI]+args, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except FileNotFoundError:
        return "", f"{NMCLI} not found", 1

def get_active_ips(con_id):
    out, _, code = run_nmcli(["con", "show", con_id])
    if code != 0:
        return []
    for line in out.splitlines():
        if "ipv4.addresses" in line:
            return [ip.strip() for ip in line.split(":",1)[1].split(",") if ip.strip()]
    return []

def apply_changes(con_id, entries, selected, log_lines):
    ips = [entries[i]["ip"] for i in selected]
    ip_str = ",".join(ips)

    run_nmcli(["con","mod",con_id,"ipv4.addresses",ip_str])
    log_lines.append(f"[MOD] {ip_str}")

    run_nmcli(["con","up",con_id])
    log_lines.append(f"[UP] {con_id}")

    if len(log_lines) > 12:
        log_lines[:] = log_lines[-12:]
    return ips

# -----------------------
# Helpers
# -----------------------
def is_valid_ip(ip):
    try:
        ipaddress.IPv4Interface(ip)
        return True
    except ValueError:
        return False

def normalize_ip(ip):
    return str(ipaddress.IPv4Interface(ip))

def curses_input(stdscr, prompt, maxlen=32):
    """Inline curses input box at bottom, fully inside TUI."""
    curses.curs_set(1)
    h, w = stdscr.getmaxyx()
    win = curses.newwin(1, w-2, h-2, 1)
    win.clear()
    win.addstr(0,0,prompt)
    win.refresh()
    buffer = ""
    pos = len(prompt)
    while True:
        stdscr.move(h-2,pos)
        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (10,13):  # Enter
            curses.curs_set(0)
            return buffer.strip()
        elif ch in (27,):  # Esc
            curses.curs_set(0)
            return None
        elif ch in (curses.KEY_BACKSPACE,127,8):
            if buffer:
                buffer = buffer[:-1]
                pos -=1
                win.delch(0,pos)
        elif 32<=ch<=126 and len(buffer)<maxlen:
            buffer += chr(ch)
            win.addch(0,pos,ch)
            pos+=1

# -----------------------
# TUI Drawing
# -----------------------
def draw_ui(stdscr, entries, selected, cursor, log_lines, current_ips):
    stdscr.clear()
    h,w = stdscr.getmaxyx()

    # Header
    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(0,0,f" NMCLI TUI - {CON_ID} ".ljust(w-1))
    stdscr.attroff(curses.color_pair(2))
    stdscr.addstr(1,0,"Arrows/jk:move | Space:toggle | N:add | D:del | A:apply | Q:quit")

    # Diff view
    new_ips = [entries[i]["ip"] for i in selected]
    stdscr.addstr(2,0,f"Current: {', '.join(current_ips)}"[:w-1])
    stdscr.addstr(3,0,f"New:     {', '.join(new_ips)}"[:w-1])

    # Entries
    row = 5
    stdscr.addstr(row,0,"Predefined:",curses.A_BOLD)
    row += 1
    for idx,e in enumerate(entries):
        if e["type"]=="custom" and idx==len(predefined_devices):
            stdscr.addstr(row,0,"Custom:",curses.A_BOLD)
            row+=1
        enabled = "[x]" if idx in selected else "[ ]"
        label = e["name"] if e["type"]=="predefined" else "custom"
        line = f"{enabled} {label:10} {e['ip']}"
        if idx==cursor:
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(row,0,line[:w-1])
            stdscr.attroff(curses.color_pair(1))
        else:
            stdscr.addstr(row,0,line[:w-1])
        row+=1

    # Log panel
    log_start = h - len(log_lines) -3
    stdscr.addstr(log_start-1,0,"-"*(w-1))
    stdscr.addstr(log_start-2,0,"Log:",curses.A_BOLD)
    for i,line in enumerate(log_lines):
        stdscr.addstr(log_start+i,0,line[:w-1])

    stdscr.refresh()

# -----------------------
# UI Loop
# -----------------------
def ui_loop(stdscr):
    curses.start_color()
    curses.init_pair(1,curses.COLOR_BLACK,curses.COLOR_CYAN)  # selection
    curses.init_pair(2,curses.COLOR_BLACK,curses.COLOR_YELLOW) # header
    curses.curs_set(0)

    entries = [{"name":d["name"],"ip":d["ip"],"type":"predefined"} for d in predefined_devices]
    for ip in load_custom_ips():
        entries.append({"name":"custom","ip":ip,"type":"custom"})

    current_ips = get_active_ips(CON_ID)
    selected = set(i for i,e in enumerate(entries) if e["ip"] in current_ips)
    cursor = 0
    log_lines = []

    while True:
        draw_ui(stdscr,entries,selected,cursor,log_lines,current_ips)
        key = stdscr.getch()

        if key in [curses.KEY_UP,ord("k")]:
            cursor = (cursor-1)%len(entries)
        elif key in [curses.KEY_DOWN,ord("j")]:
            cursor = (cursor+1)%len(entries)
        elif key==ord(" "):
            selected.symmetric_difference_update({cursor})

        elif key in [ord("n"),ord("N")]:
            ip = curses_input(stdscr,"Enter new IP (x.x.x.x/xx): ")
            if ip is None:
                log_lines.append("[CANCEL] Add IP")
            elif is_valid_ip(ip):
                ip = normalize_ip(ip)
                existing_ips = {e["ip"] for e in entries}
                if ip in existing_ips:
                    log_lines.append(f"[ERR] duplicate IP: {ip}")
                else:
                    entries.append({"name":"custom","ip":ip,"type":"custom"})
                    selected.add(len(entries)-1)
                    save_custom_ips(entries)
                    log_lines.append(f"[ADD] {ip}")
            else:
                log_lines.append(f"[ERR] invalid IP: {ip}")

        elif key in [ord("d"),ord("D")]:
            e = entries[cursor]
            if e["type"]=="custom":
                log_lines.append(f"[DEL] {e['ip']}")
                entries.pop(cursor)
                selected = {i if i<cursor else i-1 for i in selected if i!=cursor}
                save_custom_ips(entries)
                cursor = max(0,cursor-1)
            else:
                log_lines.append("[ERR] cannot delete predefined")

        elif key in [ord("a"),ord("A")]:
            new_ips = apply_changes(CON_ID,entries,selected,log_lines)
            current_ips = new_ips

        elif key in [ord("q"),ord("Q")]:
            break

# -----------------------
# Main
# -----------------------
def main():
    try:
        curses.wrapper(ui_loop)
    except KeyboardInterrupt:
        print("\nExited cleanly")
    except Exception:
        curses.endwin()
        traceback.print_exc()

if __name__=="__main__":
    main()