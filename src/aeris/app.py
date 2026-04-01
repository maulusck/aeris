"""
AERIS · main event loop
"""
import curses
import traceback

from aeris.colors import init_colors
from aeris.config import CON_ID, LOG_PANEL_H, PREDEFINED
from aeris.network import get_active_ips, apply_ips
from aeris.persistence import load_custom, save_custom
from aeris.tui import draw_ui
from aeris.utils import log_append, is_valid_ip, normalize_ip
from aeris.widgets import curses_input, confirm_dialog, help_popup, NAME_W


def ui_loop(stdscr) -> None:
    init_colors()
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(500)

    # ── Initialise entry list ───────────────────────────────
    entries: list[dict] = [
        {"name": d["name"], "ip": d["ip"], "type": "predefined"}
        for d in PREDEFINED
    ]
    for rec in load_custom():
        entries.append({"name": rec["name"], "ip": rec["ip"], "type": "custom"})

    current_ips   = get_active_ips(CON_ID)
    selected      = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
    cursor        = 0
    entry_scroll  = 0
    log: list     = []
    # log_scroll == 0  → auto-follow (pinned to bottom)
    # log_scroll >  0  → user scrolled up by N lines (historical view)
    log_scroll    = 0
    status        = "Ready"

    while True:
        # draw_ui returns clamped scroll values
        entry_scroll, log_scroll = draw_ui(
            stdscr, entries, selected, cursor,
            entry_scroll, log, log_scroll,
            current_ips, status,
        )

        key = stdscr.getch()
        if key == -1:
            continue

        h, w = stdscr.getmaxyx()
        list_top = 5                        # approximate; draw_ui recalculates
        list_bot = h - LOG_PANEL_H - 1
        list_h   = max(1, list_bot - list_top)
        log_rows = LOG_PANEL_H - 1

        # ── Navigation (entry list) ──────────────────────────
        if key in (curses.KEY_UP, ord("k"), ord("K")):
            cursor = (cursor - 1) % max(1, len(entries))

        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            cursor = (cursor + 1) % max(1, len(entries))

        # ── Entry list paging ────────────────────────────────
        elif key == curses.KEY_PPAGE:
            cursor       = max(0, cursor - list_h)
            entry_scroll = max(0, entry_scroll - list_h)

        elif key == curses.KEY_NPAGE:
            cursor       = min(len(entries) - 1, cursor + list_h)
            entry_scroll += list_h   # draw_ui will clamp

        # ── Log panel — fine scroll ──────────────────────────
        # '[' scrolls UP (towards older entries)
        # ']' scrolls DOWN (towards newest / re-enables follow mode)
        elif key == ord("["):
            log_max    = max(0, len(log) - log_rows)
            log_scroll = min(log_max, log_scroll + 1)

        elif key == ord("]"):
            log_scroll = max(0, log_scroll - 1)

        # ── Log panel — page scroll ──────────────────────────
        elif key == curses.KEY_SPREVIOUS:   # Shift+PgUp
            log_max    = max(0, len(log) - log_rows)
            log_scroll = min(log_max, log_scroll + log_rows)

        elif key == curses.KEY_SNEXT:       # Shift+PgDn
            log_scroll = max(0, log_scroll - log_rows)

        # ── Toggle selection ─────────────────────────────────
        elif key == ord(" "):
            selected.symmetric_difference_update({cursor})
            ip = entries[cursor]["ip"]
            status = f"{ip} {'selected' if cursor in selected else 'deselected'}"

        # ── Add custom IP ────────────────────────────────────
        elif key in (ord("n"), ord("N")):
            ip = curses_input(stdscr, "New IP (x.x.x.x/prefix):")
            if ip is None:
                status = "Cancelled"
            elif not is_valid_ip(ip):
                log_append(log, "ERR", f"Invalid IP: {ip}")
                status = "Invalid IP"
                log_scroll = 0      # snap log back to bottom on new entry
            else:
                ip = normalize_ip(ip)
                if ip in {e["ip"] for e in entries}:
                    log_append(log, "ERR", f"Duplicate: {ip}")
                    status     = "Duplicate"
                    log_scroll = 0
                else:
                    name = (
                        curses_input(stdscr, "Label (blank = use IP):",
                                     prefill="", maxlen=NAME_W)
                        or ip
                    )
                    entries.append({"name": name, "ip": ip, "type": "custom"})
                    selected.add(len(entries) - 1)
                    save_custom(entries)
                    log_append(log, "OK", f"Added {name} ({ip})")
                    status     = f"Added {name}"
                    log_scroll = 0   # snap to bottom so user sees the new entry

        # ── Rename custom ─────────────────────────────────────
        elif key in (ord("e"), ord("E")):
            e = entries[cursor]
            if e["type"] != "custom":
                log_append(log, "ERR", "Predefined labels are fixed")
                status     = "Cannot rename predefined"
                log_scroll = 0
            else:
                new_name = curses_input(stdscr, "New label:",
                                        prefill=e["name"], maxlen=NAME_W)
                if new_name is None:
                    status = "Cancelled"
                elif new_name:
                    old       = e["name"]
                    e["name"] = new_name
                    save_custom(entries)
                    log_append(log, "OK", f"Renamed: {old} → {new_name}")
                    status     = f"Renamed to {new_name}"
                    log_scroll = 0

        # ── Delete custom ─────────────────────────────────────
        elif key in (ord("d"), ord("D")):
            e = entries[cursor]
            if e["type"] != "custom":
                log_append(log, "ERR", "Cannot delete predefined entry")
                status     = "Predefined — protected"
                log_scroll = 0
            else:
                entries.pop(cursor)
                selected   = {i if i < cursor else i - 1
                              for i in selected if i != cursor}
                save_custom(entries)
                cursor     = max(0, min(cursor, len(entries) - 1))
                log_append(log, "OK", f"Deleted {e['name']} ({e['ip']})")
                status     = f"Deleted {e['name']}"
                log_scroll = 0

        # ── Apply ─────────────────────────────────────────────
        elif key in (ord("a"), ord("A")):
            new_ips = [entries[i]["ip"] for i in sorted(selected)]
            if not new_ips:
                log_append(log, "ERR", "Nothing selected")
                status     = "Select IPs first"
                log_scroll = 0
            else:
                removing = [ip for ip in current_ips if ip not in new_ips]
                adding   = [ip for ip in new_ips    if ip not in current_ips]
                if confirm_dialog(stdscr, removing, adding):
                    status = "Applying…"
                    # Snap log so user sees the nmcli commands as they run
                    log_scroll = 0
                    draw_ui(stdscr, entries, selected, cursor,
                            entry_scroll, log, log_scroll,
                            current_ips, status)
                    result = apply_ips(CON_ID, new_ips, log)
                    if result:
                        current_ips = result
                        status      = "Applied OK"
                    else:
                        status      = "Apply FAILED — see log"
                    log_scroll = 0   # keep user at bottom after apply
                else:
                    log_append(log, "INFO", "Apply cancelled")
                    status     = "Cancelled"
                    log_scroll = 0

        # ── Refresh ───────────────────────────────────────────
        elif key in (ord("r"), ord("R")):
            current_ips = get_active_ips(CON_ID)
            selected    = {i for i, e in enumerate(entries)
                           if e["ip"] in current_ips}
            log_append(log, "INFO",
                       f"Refreshed: {', '.join(current_ips) or '—'}")
            status     = "Refreshed"
            log_scroll = 0

        # ── Help ──────────────────────────────────────────────
        elif key == ord("?"):
            help_popup(stdscr)

        # ── Quit ──────────────────────────────────────────────
        elif key in (ord("q"), ord("Q"), 27):
            break


def main() -> None:
    try:
        curses.wrapper(ui_loop)
    except KeyboardInterrupt:
        print("\nExited.")
    except Exception:
        curses.endwin()
        traceback.print_exc()
