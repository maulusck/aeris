"""
AERIS · main event loop
"""

from __future__ import annotations

import curses
import traceback
from collections import deque
from typing import List, Optional, Set, Tuple

from aeris.colors import init_colors
from aeris.config import CON_ID, LOG_PANEL_H, THEME
from aeris.network import apply_ips, get_active_ips
from aeris.persistence import (
    ensure_default,
    load_profile,
    load_state,
    save_profile,
    save_state,
)
from aeris.tui import draw_ui
from aeris.utils import is_valid_ip, log_append, make_log, normalize_ip
from aeris.widgets import (
    NAME_W,
    confirm_dialog,
    curses_input,
    help_popup,
    profile_wizard,
)


def _load_profile_entries(profile_name: str) -> List[dict]:
    """Load entries for a profile, ensuring default exists first."""
    ensure_default()
    return load_profile(profile_name)


def _compute_pending(
    entries: List[dict],
    selected: Set[int],
    current_ips: List[str],
) -> Tuple[List[str], List[str]]:
    """
    Return (pend_add, pend_del) — the diff between the selected set and
    the currently live IPs.  Call this only when selected or current_ips
    actually change, then cache the result.
    """
    new_ips = [entries[i]["ip"] for i in sorted(selected)]
    current_set = set(current_ips)
    new_set = set(new_ips)
    pend_add = [ip for ip in new_ips if ip not in current_set]
    pend_del = [ip for ip in current_ips if ip not in new_set]
    return pend_add, pend_del


def ui_loop(stdscr) -> None:
    init_colors(THEME)
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(500)

    active_profile = load_state()
    ensure_default()

    entries = _load_profile_entries(active_profile)
    current_ips = get_active_ips(CON_ID)
    selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
    cursor = 0
    entry_scroll = 0
    log = make_log()
    log_scroll = 0
    status = f"Profile: {active_profile}"

    # Pre-compute pending diff; invalidated whenever selected / current_ips change.
    pend_add, pend_del = _compute_pending(entries, selected, current_ips)
    _pending_dirty = False  # flag: recompute before next draw

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

        # ── navigation ────────────────────────────────────────────────────────

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

        # ── log scrolling ─────────────────────────────────────────────────────

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

        # ── toggle selection ──────────────────────────────────────────────────

        elif key == ord(" "):
            if entries:
                selected.symmetric_difference_update({cursor})
                ip = entries[cursor]["ip"]
                status = f"{ip} {'selected' if cursor in selected else 'deselected'}"
                _pending_dirty = True

        # ── add new entry ─────────────────────────────────────────────────────

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
                    name = (
                        curses_input(
                            stdscr,
                            "Label (blank = use IP):",
                            prefill="",
                            maxlen=NAME_W,
                        )
                        or ip
                    )
                    entries.append({"name": name, "ip": ip})
                    selected.add(len(entries) - 1)
                    save_profile(active_profile, entries)
                    log_append(log, "OK", f"Added {name} ({ip})")
                    status = f"Added {name}"
                    log_scroll = 0
                    _pending_dirty = True

        # ── rename entry ──────────────────────────────────────────────────────

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
                    log_append(log, "OK", f"Renamed: {old} → {new_name}")
                    status = f"Renamed to {new_name}"
                    log_scroll = 0

        # ── delete entry ──────────────────────────────────────────────────────

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

        # ── apply ─────────────────────────────────────────────────────────────

        elif key in (ord("a"), ord("A")):
            new_ips = [entries[i]["ip"] for i in sorted(selected)]
            if not new_ips:
                log_append(log, "ERR", "Nothing selected")
                status = "Select IPs first"
                log_scroll = 0
            else:
                if confirm_dialog(stdscr, pend_del, pend_add):
                    status = "Applying…"
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
                        pend_add=pend_add,
                        pend_del=pend_del,
                    )
                    result = apply_ips(CON_ID, new_ips, log)
                    if result:
                        current_ips = result
                        status = "Applied OK"
                    else:
                        status = "Apply FAILED — see log"
                    log_scroll = 0
                    _pending_dirty = True
                else:
                    log_append(log, "INFO", "Apply cancelled")
                    status = "Cancelled"
                    log_scroll = 0

        # ── refresh ───────────────────────────────────────────────────────────

        elif key in (ord("r"), ord("R")):
            current_ips = get_active_ips(CON_ID)
            selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
            log_append(log, "INFO", f"Refreshed: {', '.join(current_ips) or '—'}")
            status = "Refreshed"
            log_scroll = 0
            _pending_dirty = True

        # ── profile manager ───────────────────────────────────────────────────

        elif key in (ord("p"), ord("P")):
            result = profile_wizard(stdscr, active_profile)
            if result is not None and result != active_profile:
                active_profile = result
                save_state(active_profile)
                entries = _load_profile_entries(active_profile)
                current_ips = get_active_ips(CON_ID)
                selected = {i for i, e in enumerate(entries) if e["ip"] in current_ips}
                cursor = 0
                entry_scroll = 0
                log_append(log, "INFO", f"Switched to profile '{active_profile}'")
                status = f"Profile: {active_profile}"
                log_scroll = 0
                _pending_dirty = True
            elif result == active_profile:
                status = f"Profile: {active_profile}"

        # ── help ──────────────────────────────────────────────────────────────

        elif key == ord("?"):
            help_popup(stdscr)

        # ── quit ──────────────────────────────────────────────────────────────

        elif key in (ord("q"), ord("Q"), 27):
            save_state(active_profile)
            break


def main() -> None:
    try:
        curses.wrapper(ui_loop)
    except KeyboardInterrupt:
        print("\nExited.")
    except Exception:
        curses.endwin()
        traceback.print_exc()
