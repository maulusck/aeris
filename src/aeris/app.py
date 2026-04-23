"""
AERIS · main event loop
"""

from __future__ import annotations

import argparse
import curses
import sys
import traceback
from typing import List, Optional, Set, Tuple

from aeris.colors import init_colors
from aeris.config import CON_ID, LOG_PANEL_H, THEME
from aeris.network import apply_ips, get_active_ips
from aeris.persistence import (
    ensure_default,
    list_profiles,
    load_profile,
    load_state,
    save_profile,
    save_state,
)
from aeris.tui import draw_ui
from aeris.utils import HELP_TEXT, is_valid_ip, log_append, make_log, normalize_ip
from aeris.widgets import (
    NAME_W,
    confirm_dialog,
    connection_wizard,
    curses_input,
    help_popup,
    profile_wizard,
)

# ── Internal helpers ──────────────────────────────────────────────────────────


def _load_profile_entries(profile_name: str) -> List[dict]:
    ensure_default()
    return load_profile(profile_name)


def _compute_pending(
    entries: List[dict],
    selected: Set[int],
    current_ips: List[str],
) -> Tuple[List[str], List[str]]:
    new_ips = [entries[i]["ip"] for i in sorted(selected)]
    current_set = set(current_ips)
    new_set = set(new_ips)
    pend_add = [ip for ip in new_ips if ip not in current_set]
    pend_del = [ip for ip in current_ips if ip not in new_set]
    return pend_add, pend_del


# ── Headless apply ────────────────────────────────────────────────────────────


def _headless_apply(profile: str, con_id: str) -> int:
    """Apply all IPs in *profile* without a TUI. Returns exit code."""
    ensure_default()
    entries = load_profile(profile)
    if not entries:
        print(f"aeris: profile '{profile}' is empty or does not exist.", file=sys.stderr)
        return 1
    ips = [e["ip"] for e in entries]
    log = make_log()
    print(f"Applying {len(ips)} IP(s) from profile '{profile}' to '{con_id}'...")
    result = apply_ips(con_id, ips, log)
    if result:
        print("OK:", ", ".join(result))
        return 0
    else:
        for entry in log:
            print(entry, file=sys.stderr)
        print("aeris: apply failed.", file=sys.stderr)
        return 1


# ── TUI loop ──────────────────────────────────────────────────────────────────


def ui_loop(stdscr, *, active_profile: str, con_id: str, theme: str) -> None:
    init_colors(theme)
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(500)

    ensure_default()

    entries = _load_profile_entries(active_profile)
    current_ips = get_active_ips(con_id)
    selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
    cursor = 0
    entry_scroll = 0
    log = make_log()
    log_scroll = 0
    status = f"Profile: {active_profile}"

    pend_add, pend_del = _compute_pending(entries, selected, current_ips)
    _pending_dirty = False

    while True:
        if _pending_dirty:
            pend_add, pend_del = _compute_pending(entries, selected, current_ips)
            _pending_dirty = False

        entry_scroll, log_scroll = draw_ui(
            stdscr,
            entries,
            selected,
            cursor,
            entry_scroll,
            log,
            log_scroll,
            current_ips,
            status,
            active_profile,
            con_id,
            pend_add=pend_add,
            pend_del=pend_del,
        )

        key = stdscr.getch()
        if key == -1:
            continue

        h, w = stdscr.getmaxyx()
        list_top = 5
        list_bot = h - LOG_PANEL_H - 1
        list_h = max(1, list_bot - list_top)
        log_rows = LOG_PANEL_H - 1

        if key in (curses.KEY_UP, ord("k"), ord("K")):
            cursor = (cursor - 1) % max(1, len(entries))
        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            cursor = (cursor + 1) % max(1, len(entries))
        elif key == curses.KEY_PPAGE:
            cursor = max(0, cursor - list_h)
            entry_scroll = max(0, entry_scroll - list_h)
        elif key == curses.KEY_NPAGE:
            cursor = min(max(0, len(entries) - 1), cursor + list_h)
            entry_scroll += list_h
        elif key == ord("["):
            log_max = max(0, len(log) - log_rows)
            log_scroll = min(log_max, log_scroll + 1)
        elif key == ord("]"):
            log_scroll = max(0, log_scroll - 1)
        elif key == curses.KEY_SPREVIOUS:
            log_max = max(0, len(log) - log_rows)
            log_scroll = min(log_max, log_scroll + log_rows)
        elif key == curses.KEY_SNEXT:
            log_scroll = max(0, log_scroll - log_rows)
        elif key == ord(" "):
            if entries:
                selected.symmetric_difference_update({cursor})
                ip = entries[cursor]["ip"]
                status = f"{ip} {'selected' if cursor in selected else 'deselected'}"
                _pending_dirty = True
        elif key in (ord("n"), ord("N")):
            ip = curses_input(stdscr, "New IP (x.x.x.x/prefix):")
            if ip is None:
                status = "Cancelled"
            elif not is_valid_ip(ip):
                log_append(log, "ERR", f"Invalid IP: {ip}")
                status = "Invalid IP"
                log_scroll = 0
            else:
                ip = normalize_ip(ip)
                if ip in {e["ip"] for e in entries}:
                    log_append(log, "ERR", f"Duplicate: {ip}")
                    status = "Duplicate"
                    log_scroll = 0
                else:
                    name = curses_input(stdscr, "Label (blank = use IP):", prefill="", maxlen=NAME_W) or ip
                    entries.append({"name": name, "ip": ip})
                    selected.add(len(entries) - 1)
                    save_profile(active_profile, entries)
                    log_append(log, "OK", f"Added {name} ({ip})")
                    status = f"Added {name}"
                    log_scroll = 0
                    _pending_dirty = True
        elif key in (ord("e"), ord("E")):
            if not entries:
                status = "No entries"
            else:
                e = entries[cursor]
                new_name = curses_input(stdscr, "New label:", prefill=e["name"], maxlen=NAME_W)
                if new_name is None:
                    status = "Cancelled"
                elif new_name:
                    old = e["name"]
                    e["name"] = new_name
                    save_profile(active_profile, entries)
                    log_append(log, "OK", f"Renamed: {old} -> {new_name}")
                    status = f"Renamed to {new_name}"
                    log_scroll = 0
        elif key in (ord("d"), ord("D")):
            if not entries:
                status = "No entries"
            else:
                e = entries.pop(cursor)
                selected = {i if i < cursor else i - 1 for i in selected if i != cursor}
                save_profile(active_profile, entries)
                cursor = max(0, min(cursor, len(entries) - 1))
                log_append(log, "OK", f"Deleted {e['name']} ({e['ip']})")
                status = f"Deleted {e['name']}"
                log_scroll = 0
                _pending_dirty = True
        elif key in (ord("a"), ord("A")):
            new_ips = [entries[i]["ip"] for i in sorted(selected)]
            if not new_ips:
                log_append(log, "ERR", "Nothing selected")
                status = "Select IPs first"
                log_scroll = 0
            else:
                if confirm_dialog(stdscr, pend_del, pend_add):
                    status = "Applying..."
                    log_scroll = 0
                    draw_ui(
                        stdscr,
                        entries,
                        selected,
                        cursor,
                        entry_scroll,
                        log,
                        log_scroll,
                        current_ips,
                        status,
                        active_profile,
                        con_id,
                        pend_add=pend_add,
                        pend_del=pend_del,
                    )
                    result = apply_ips(con_id, new_ips, log)
                    if result:
                        current_ips = result
                        status = "Applied OK"
                    else:
                        status = "Apply FAILED - see log"
                    log_scroll = 0
                    _pending_dirty = True
                else:
                    log_append(log, "INFO", "Apply cancelled")
                    status = "Cancelled"
                    log_scroll = 0
        elif key in (ord("r"), ord("R")):
            current_ips = get_active_ips(con_id)
            selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
            log_append(log, "INFO", f"Refreshed: {', '.join(current_ips) or '-'}")
            status = "Refreshed"
            log_scroll = 0
            _pending_dirty = True
        elif key in (ord("p"), ord("P")):
            result = profile_wizard(stdscr, active_profile)
            if result is not None and result != active_profile:
                active_profile = result
                save_state(active_profile, con_id)
                entries = _load_profile_entries(active_profile)
                current_ips = get_active_ips(con_id)
                selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
                cursor = 0
                entry_scroll = 0
                log_append(log, "INFO", f"Switched to profile '{active_profile}'")
                status = f"Profile: {active_profile}"
                log_scroll = 0
                _pending_dirty = True
            elif result == active_profile:
                status = f"Profile: {active_profile}"

        # ── connection selector ───────────────────────────────────────────────

        elif key in (ord("c"), ord("C")):
            result = connection_wizard(stdscr, con_id)
            if result is not None and result != con_id:
                con_id = result
                save_state(active_profile, con_id)
                current_ips = get_active_ips(con_id)
                selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
                log_append(log, "INFO", f"Connection: '{con_id}'")
                status = f"Connection: {con_id}"
                log_scroll = 0
                _pending_dirty = True
        elif key == ord("?"):
            help_popup(stdscr)
        elif key in (ord("q"), ord("Q"), 27):
            save_state(active_profile, con_id)
            break


# ── Entry point ───────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aeris",
        description="AERIS · Avionic Ethernet Rig IP Selector",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show help and exit")
    parser.add_argument("-v", "--version", action="store_true", help="Show version and exit")
    parser.add_argument("-p", "--profile", metavar="NAME", help="Start with this profile (default: last used)")
    parser.add_argument("-c", "--con-id", metavar="ID", dest="con_id", help="NetworkManager connection ID (overrides AERIS_CON_ID)")
    parser.add_argument("--theme", metavar="THEME", choices=("amber", "matrix", "mono"), help="Colour theme: amber|matrix|mono (overrides AERIS_THEME)")
    parser.add_argument("--list-profiles", action="store_true", help="Print available profiles and exit")
    parser.add_argument("--apply", metavar="PROFILE", help="Headless: apply all IPs in PROFILE and exit")
    return parser


def main() -> None:
    from aeris import __version__

    parser = _build_parser()
    args = parser.parse_args()

    if args.version:
        print(f"AERIS {__version__}")
        return

    if args.help:
        print(HELP_TEXT)
        return

    if args.list_profiles:
        ensure_default()
        for name in list_profiles():
            print(name)
        return

    active_profile, con_id_saved = load_state()
    if args.con_id:
        con_id = args.con_id
    elif con_id_saved:
        con_id = con_id_saved
    else:
        con_id = CON_ID
    theme: str = args.theme or THEME

    if args.apply:
        sys.exit(_headless_apply(args.apply, con_id))

    active_profile = args.profile or active_profile

    try:
        curses.wrapper(ui_loop, active_profile=active_profile, con_id=con_id, theme=theme)
    except KeyboardInterrupt:
        print("\nExited.")
    except Exception:
        curses.endwin()
        traceback.print_exc()
