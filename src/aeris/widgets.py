"""
AERIS · modal widgets — input box, confirm dialog, help popup,
        profile wizard, connection wizard
"""

from __future__ import annotations

import curses
from typing import List, Optional, Tuple

from aeris.colors import (
    C_BORDER,
    C_CUR_LIVE,
    C_CURSOR,
    C_DIM,
    C_HDR,
    C_HINT,
    C_INPUT,
    C_LOG_OK,
    C_PEND_ADD,
    C_PEND_DEL,
    C_SECTION,
)
from aeris.config import LOG_PANEL_H
from aeris.drawing import draw_scrollbar, sadd
from aeris.utils import HELP_TEXT as _HELP_TEXT_STR

NAME_W = 13

# ── Ctrl-key helpers ──────────────────────────────────────────────────────────
_CTRL_A = 1
_CTRL_E = 5
_CTRL_U = 21
_CTRL_W = 23

# Connection-wizard constants (module-level — built once)
_CON_HINT_MAIN = " jk/↑↓:move  ENTER:select  F:filter  R:refresh  ESC/Q:close"
_CON_HINT_EMPTY = " No nmcli connections found"
_CON_TYPE_W = 14
_CON_DEV_W = 10
_CON_HIDDEN = frozenset({"loopback", "bridge", "tun", "wireguard", "dummy"})

# Profile-wizard constants
_PROF_HINT_MAIN = " jk/↑↓:move  ENTER:load  N:new  R:rename  X:delete  C:copy  ESC/Q:close"
_PROF_HINT_ERR_DUP = " Name already exists — choose another"
_PROF_HINT_ERR_NONE = " Nothing to act on"


# ─────────────────────────────────────────────────────────────────────────────
# Text input widget
# ─────────────────────────────────────────────────────────────────────────────


def curses_input(stdscr, prompt: str, prefill: str = "", maxlen: int = 40) -> Optional[str]:
    """
    Floating input box. Readline shortcuts: Ctrl-A/E (BOL/EOL), Ctrl-U (kill
    line), Ctrl-W (kill word). Returns stripped string or None on Esc.
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

    win.nodelay(False)

    inp_a = curses.color_pair(C_INPUT) | curses.A_BOLD
    lbl_a = curses.color_pair(C_SECTION) | curses.A_BOLD

    win.attron(inp_a)
    win.border()
    win.attroff(inp_a)

    label = f" {prompt} "
    field_x = 2 + len(label)
    field_w = max(4, box_w - field_x - 3)
    sadd(win, 1, 2, label, lbl_a)

    buf: List[str] = list(prefill[:maxlen])
    cpos: int = len(buf)

    def _redraw() -> None:
        start = max(0, cpos - field_w + 1)
        view = "".join(buf)[start : start + field_w]
        sadd(win, 1, field_x, view.ljust(field_w), inp_a)
        try:
            win.move(1, field_x + (cpos - start))
        except curses.error:
            pass
        win.refresh()

    while True:
        _redraw()
        ch = win.getch()

        if ch in (10, 13):
            curses.curs_set(0)
            return "".join(buf).strip()
        elif ch == 27:
            curses.curs_set(0)
            return None
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if cpos > 0:
                buf.pop(cpos - 1)
                cpos -= 1
        elif ch == curses.KEY_DC:
            if cpos < len(buf):
                buf.pop(cpos)
        elif ch == curses.KEY_LEFT:
            cpos = max(0, cpos - 1)
        elif ch == curses.KEY_RIGHT:
            cpos = min(len(buf), cpos + 1)
        elif ch in (curses.KEY_HOME, _CTRL_A):
            cpos = 0
        elif ch in (curses.KEY_END, _CTRL_E):
            cpos = len(buf)
        elif ch == _CTRL_U:
            buf.clear()
            cpos = 0
        elif ch == _CTRL_W:
            while cpos > 0 and buf[cpos - 1] == " ":
                buf.pop(cpos - 1)
                cpos -= 1
            while cpos > 0 and buf[cpos - 1] != " ":
                buf.pop(cpos - 1)
                cpos -= 1
        elif 32 <= ch <= 126 and len(buf) < maxlen:
            buf.insert(cpos, chr(ch))
            cpos += 1


# ─────────────────────────────────────────────────────────────────────────────
# Shared bordered-dialog primitive  (confirm / mini-confirm)
# ─────────────────────────────────────────────────────────────────────────────


def _bordered_dialog(
    stdscr,
    rows: List[Tuple[str, int]],
    border_attr: int,
    scrollable: bool = False,
) -> bool:
    """
    Generic modal dialog. Displays *rows* (text, attr) in a centred bordered
    window. Returns True on Y/Enter, False on N/Esc.
    """
    h, w = stdscr.getmaxyx()
    box_h = min(h - 4, len(rows) + 2)
    box_w = min(w - 6, max((len(t) for t, _ in rows), default=20) + 4)
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2

    try:
        win = curses.newwin(box_h, box_w, box_y, box_x)
    except curses.error:
        return False

    win.keypad(True)
    win.nodelay(False)

    pos = 0
    max_pos = max(0, len(rows) - (box_h - 2))
    inner_h = box_h - 2

    while True:
        win.erase()
        win.attron(border_attr)
        win.border()
        win.attroff(border_attr)

        for i in range(inner_h):
            ri = pos + i
            if ri >= len(rows):
                break
            text, attr = rows[ri]
            sadd(win, i + 1, 1, text[: box_w - 2], attr)

        if scrollable and max_pos > 0:
            draw_scrollbar(win, 1, inner_h, box_w - 2, len(rows), pos, curses.color_pair(C_BORDER))

        win.refresh()
        ch = win.getch()

        if ch in (ord("y"), ord("Y"), 10, 13):
            return True
        if ch in (ord("n"), ord("N"), 27):
            return False

        if scrollable:
            if ch in (curses.KEY_DOWN, ord("j")):
                pos = min(pos + 1, max_pos)
            elif ch in (curses.KEY_UP, ord("k")):
                pos = max(pos - 1, 0)
            elif ch == curses.KEY_PPAGE:
                pos = max(0, pos - inner_h)
            elif ch == curses.KEY_NPAGE:
                pos = min(max_pos, pos + inner_h)


# ─────────────────────────────────────────────────────────────────────────────
# Confirm dialog
# ─────────────────────────────────────────────────────────────────────────────


def confirm_dialog(stdscr, removing: List[str], adding: List[str]) -> bool:
    rows: List[Tuple[str, int]] = [
        ("  CONFIRM APPLY  ", curses.color_pair(C_CURSOR) | curses.A_BOLD),
    ]
    for ip in removing:
        rows.append((f"  - {ip}", curses.color_pair(C_PEND_DEL)))
    for ip in adding:
        rows.append((f"  + {ip}", curses.color_pair(C_PEND_ADD) | curses.A_BOLD))
    if not removing and not adding:
        rows.append(("  (no diff)", curses.color_pair(C_DIM)))
    rows += [
        ("", 0),
        ("  [Y] apply   [N] cancel", curses.color_pair(C_SECTION) | curses.A_BOLD),
    ]
    return _bordered_dialog(stdscr, rows, curses.color_pair(C_CURSOR) | curses.A_BOLD, scrollable=True)


def _mini_confirm(stdscr, rows: List[Tuple[str, int]]) -> bool:
    return _bordered_dialog(stdscr, rows, curses.color_pair(C_BORDER))


# ─────────────────────────────────────────────────────────────────────────────
# Shared list-popup primitive  (profile wizard + connection wizard both use this)
# ─────────────────────────────────────────────────────────────────────────────


def _make_popup(stdscr, box_w: int, box_h: int) -> Optional[curses.window]:
    """Create a centred bordered popup window, or return None on failure."""
    h, w = stdscr.getmaxyx()
    box_w = min(w - 4, box_w)
    box_h = min(h - 4, box_h)
    try:
        win = curses.newwin(box_h, box_w, (h - box_h) // 2, (w - box_w) // 2)
    except curses.error:
        return None
    win.keypad(True)
    win.nodelay(False)
    return win


def _popup_frame(win, title: str, hint: str, footer: str) -> None:
    """Draw border, centred title, hint row, and footer row."""
    box_h, box_w = win.getmaxyx()
    border_a = curses.color_pair(C_BORDER)
    win.erase()
    win.attron(border_a)
    win.border()
    win.attroff(border_a)
    sadd(win, 0, (box_w - len(title)) // 2, title, curses.color_pair(C_HDR) | curses.A_BOLD)
    sadd(win, 1, 1, hint[: box_w - 2], curses.color_pair(C_HINT))
    sadd(win, box_h - 2, 1, footer[: box_w - 2], curses.color_pair(C_DIM))


def _clamp_scroll(cursor: int, scroll: int, list_h: int, total: int) -> int:
    scroll = max(0, min(scroll, max(0, total - list_h)))
    if cursor < scroll:
        scroll = cursor
    elif cursor >= scroll + list_h:
        scroll = cursor - list_h + 1
    return scroll


# ─────────────────────────────────────────────────────────────────────────────
# Profile wizard
# ─────────────────────────────────────────────────────────────────────────────


def profile_wizard(stdscr, active_profile: str) -> Optional[str]:
    """
    Floating popup for profile management.
    Returns the profile to switch to, or active_profile if unchanged.
    """
    from aeris.persistence import (
        create_profile,
        delete_profile,
        duplicate_profile,
        ensure_default,
        list_profiles,
        rename_profile,
    )

    ensure_default()
    curses.curs_set(0)

    win = _make_popup(stdscr, 62, 22)
    if win is None:
        return None

    box_h, box_w = win.getmaxyx()
    list_h = box_h - 5  # rows 2 … box_h-3  (title + hint + footer + border)

    profiles: List[str] = list_profiles()
    cursor = next((i for i, n in enumerate(profiles) if n == active_profile), 0)
    scroll = 0
    hint = _PROF_HINT_MAIN

    _a_cur_act = curses.color_pair(C_CUR_LIVE) | curses.A_BOLD
    _a_cur = curses.color_pair(C_CURSOR) | curses.A_BOLD
    _a_active = curses.color_pair(C_LOG_OK) | curses.A_BOLD
    _a_dim = curses.color_pair(C_DIM)

    while True:
        cursor = max(0, min(cursor, len(profiles) - 1)) if profiles else 0
        scroll = _clamp_scroll(cursor, scroll, list_h, len(profiles))

        _popup_frame(win, " PROFILES ", hint, "N:new  R:rename  X:del  C:copy  ENTER:load  Q:close")
        hint = _PROF_HINT_MAIN  # reset one-frame error messages

        bar_col = box_w - 2
        for row_i in range(list_h):
            pi = scroll + row_i
            if pi >= len(profiles):
                break
            name = profiles[pi]
            is_active = name == active_profile
            is_cursor = pi == cursor

            if is_cursor and is_active:
                attr = _a_cur_act
            elif is_cursor:
                attr = _a_cur
            elif is_active:
                attr = _a_active
            else:
                attr = _a_dim

            marker = "▶" if is_active else " "
            line = f"  {marker} {name}"
            sadd(win, 2 + row_i, 0, line[: box_w - 3].ljust(box_w - 3), attr)

        draw_scrollbar(win, 2, list_h, bar_col, len(profiles), scroll, curses.color_pair(C_BORDER))
        win.refresh()

        key = win.getch()

        if key in (27, ord("q"), ord("Q")):
            return active_profile

        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            cursor = (cursor - 1) % max(1, len(profiles))

        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            cursor = (cursor + 1) % max(1, len(profiles))

        elif key == curses.KEY_PPAGE:
            cursor = max(0, cursor - list_h)

        elif key == curses.KEY_NPAGE:
            cursor = min(len(profiles) - 1, cursor + list_h)

        elif key in (10, 13):
            if profiles:
                return profiles[cursor]

        elif key in (ord("n"), ord("N")):
            name = curses_input(stdscr, "New profile name:", maxlen=32)
            if name:
                if not create_profile(name):
                    hint = _PROF_HINT_ERR_DUP
                else:
                    profiles = list_profiles()
                    cursor = next((i for i, n in enumerate(profiles) if n == name), cursor)

        elif key in (ord("r"), ord("R")):
            if not profiles:
                hint = _PROF_HINT_ERR_NONE
            else:
                old = profiles[cursor]
                new = curses_input(stdscr, "Rename to:", prefill=old, maxlen=32)
                if new and new != old:
                    if not rename_profile(old, new):
                        hint = _PROF_HINT_ERR_DUP
                    else:
                        if old == active_profile:
                            return new
                        profiles = list_profiles()
                        cursor = next((i for i, n in enumerate(profiles) if n == new), cursor)

        elif key in (ord("x"), ord("X")):
            if not profiles:
                hint = _PROF_HINT_ERR_NONE
            else:
                name = profiles[cursor]
                if _mini_confirm(
                    stdscr,
                    [
                        (f"  Delete profile '{name}' ?", curses.color_pair(C_PEND_DEL) | curses.A_BOLD),
                        ("", 0),
                        ("  [Y] delete   [N] cancel", curses.color_pair(C_SECTION) | curses.A_BOLD),
                    ],
                ):
                    delete_profile(name)
                    profiles = list_profiles()
                    cursor = max(0, min(cursor, len(profiles) - 1))
                    if name == active_profile:
                        return profiles[cursor] if profiles else "default"

        elif key in (ord("c"), ord("C")):
            if not profiles:
                hint = _PROF_HINT_ERR_NONE
            else:
                src = profiles[cursor]
                dst = curses_input(stdscr, f"Copy '{src}' to:", maxlen=32)
                if dst:
                    if not duplicate_profile(src, dst):
                        hint = _PROF_HINT_ERR_DUP
                    else:
                        profiles = list_profiles()
                        cursor = next((i for i, n in enumerate(profiles) if n == dst), cursor)


# ─────────────────────────────────────────────────────────────────────────────
# Connection wizard
# ─────────────────────────────────────────────────────────────────────────────


def connection_wizard(stdscr, active_con_id: str) -> Optional[str]:
    """
    Floating popup listing all nmcli connections.
    Returns the selected connection name, or active_con_id if unchanged.
    F toggles filtering of loopback/bridge/tun/wireguard/dummy connections.
    R refreshes the list.
    """
    from aeris.network import list_connections

    curses.curs_set(0)

    win = _make_popup(stdscr, 76, 24)
    if win is None:
        return None

    box_h, box_w = win.getmaxyx()
    list_h = box_h - 6  # rows 3 … box_h-3  (title + hint + col-hdr + footer + border)
    name_w = max(10, box_w - _CON_TYPE_W - _CON_DEV_W - 8)

    def _fetch(filter_on: bool) -> List[dict]:
        cons = list_connections()
        return [c for c in cons if c["type"] not in _CON_HIDDEN] if filter_on else cons

    filter_on = True
    connections = _fetch(filter_on)
    cursor = next((i for i, c in enumerate(connections) if c["name"] == active_con_id), 0)
    scroll = 0
    hint = _CON_HINT_MAIN

    _a_border = curses.color_pair(C_BORDER)
    _a_cur = curses.color_pair(C_CURSOR) | curses.A_BOLD
    _a_cur_act = curses.color_pair(C_CUR_LIVE) | curses.A_BOLD
    _a_active = curses.color_pair(C_LOG_OK) | curses.A_BOLD
    _a_dim = curses.color_pair(C_DIM)
    _a_add = curses.color_pair(C_PEND_ADD)
    _a_del = curses.color_pair(C_PEND_DEL)
    _a_section = curses.color_pair(C_SECTION) | curses.A_BOLD

    col_hdr = f"  {'NAME':<{name_w}} {'TYPE':<{_CON_TYPE_W}} {'DEVICE':<{_CON_DEV_W}}"
    footer = "ENTER:select  F:filter  R:refresh  Q:close"

    while True:
        cursor = max(0, min(cursor, len(connections) - 1)) if connections else 0
        scroll = _clamp_scroll(cursor, scroll, list_h, len(connections))

        filt_tag = "[filter:on]" if filter_on else "[filter:off]"
        _popup_frame(win, " CONNECTIONS ", f"{hint}  {filt_tag}", footer)
        hint = _CON_HINT_MAIN  # reset one-frame messages

        sadd(win, 2, 1, col_hdr[: box_w - 2], _a_section)

        bar_col = box_w - 2
        for row_i in range(list_h):
            ci = scroll + row_i
            screen_row = 3 + row_i
            if ci >= len(connections):
                break
            c = connections[ci]
            is_active = c["name"] == active_con_id
            is_cursor = ci == cursor
            is_up = "activated" in c["state"]

            if is_cursor and is_active:
                attr = _a_cur_act
            elif is_cursor:
                attr = _a_cur
            elif is_active:
                attr = _a_active
            else:
                attr = _a_dim

            dot = "●" if is_up else "○"
            dot_attr = _a_add if is_up else _a_del
            name_col = c["name"][:name_w].ljust(name_w)
            type_col = c["type"][:_CON_TYPE_W].ljust(_CON_TYPE_W)
            dev_col = c["device"][:_CON_DEV_W].ljust(_CON_DEV_W)

            line = f"  {dot} {name_col} {type_col} {dev_col}"
            sadd(win, screen_row, 0, line[: box_w - 2].ljust(box_w - 2), attr)
            sadd(win, screen_row, 3, dot, dot_attr if not is_cursor else attr)

        if not connections:
            sadd(win, 3, 2, _CON_HINT_EMPTY, _a_dim)

        draw_scrollbar(win, 3, list_h, bar_col, len(connections), scroll, _a_border)
        win.refresh()

        key = win.getch()

        if key in (27, ord("q"), ord("Q")):
            return active_con_id

        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            cursor = (cursor - 1) % max(1, len(connections))

        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            cursor = (cursor + 1) % max(1, len(connections))

        elif key == curses.KEY_PPAGE:
            cursor = max(0, cursor - list_h)

        elif key == curses.KEY_NPAGE:
            cursor = min(max(0, len(connections) - 1), cursor + list_h)

        elif key in (10, 13):
            if connections:
                return connections[cursor]["name"]

        elif key in (ord("f"), ord("F")):
            filter_on = not filter_on
            connections = _fetch(filter_on)
            cursor = next((i for i, c in enumerate(connections) if c["name"] == active_con_id), 0)
            scroll = 0

        elif key in (ord("r"), ord("R")):
            connections = _fetch(filter_on)
            cursor = next((i for i, c in enumerate(connections) if c["name"] == active_con_id), 0)
            scroll = 0


# ─────────────────────────────────────────────────────────────────────────────
# Help popup
# ─────────────────────────────────────────────────────────────────────────────

_HELP_TEXT = _HELP_TEXT_STR.splitlines()

_ASCII_ART_LINES = """\

                             =:=.
                           .=:.:*-
                        .=+*-.::*%%*:.
                       .****:-=:=%%%##*:.
                       .**#=:*%=:*%%%#**
               ..      -%*#--#@#:=%%%##*%*:
      .::::.:*****#*-  =%##:=%@%-:*%###*%%##*:
   .==++***%%%%%**#%**:=@%%:+%%%*.=#*****%%#*#.
  .:-*****#***%%%#**#%%%@@%:+%%%%-:+******%%##%#=
   :-=***%@@@%#*%%#***%%@@%-=%%@%*:-#*****#%#*%#*+
  :=+:+=+*%@@@%%#*##***%%@%-=#%%%%-:+*+****#%##%*##-
 :==*=-==*%%%%%%##**#+**%%%=:*#%%#%::++++++*##*#%*@%%*.
  ::++:--**: .:+**#++*+**#%+:+*%*%%*::+===+++***###%%#%*.
  :.=+:-:+#=     :+*=++++***:-***%%%=.:==-=+=***###%%%##*=
  .::*--:*#=       :=:-::=+*-:===+**%-.----=+=***##%%%##%#*.
  ::-+--=*#:       -*=:...:::::-===+#%-:=-::+==*+*%#%%%#*%%#:
  .:-*-=+#*.      .*=.........::-===*#%=.-:::=-+**#%%%%#*%%%#.
  .-=*==*%=       :*:...........:--=+*#%+:=::-:-*+*%%%%%%#%%%#.
  :=*#=*##.       -=...........:::--=*#%#=:-::-:=+*#@%%%%%#%%%+
  =+##*#%+        ::.............:--+**#+*--::=--*+*%%#%%%%%%%%.
  :#%%%%%%.       :.............::-=+*+*=+*==-===***%%%%%%%%%%%=
   .#%@%%%%:      ++=::......-+*###%#*****#*+=+*+*#*%%%%%%%@%%%*
    .*%%*%%%*:    -=+**:...:=*##%*%@%#%#++***+*#*%%%@@%@@%%%@@%#
      =#- :*##=   .*#%%#::..-==+**%%%@@%#**#%*#%#%%%@@@@%@@@@@@@%%#*=.
       -+    :**: ::*%#*=.....:..:*%#*=:+**%%%%%%%@%@@@%#*@@@@@@%%###%=
        -.     .== .=**-.........:***+:=*=#%@%%@%@@@@@@@%*#@@@@@%%#####:
        ..       .:====:...::.:.:.::::::=*%%%@@@@@@@@@@%#*#@@@@@@%%%###%:
                   .:..:..:-*=-:.:.::::=*#**@@@@@@@@@%%#+*@@@@@@@%%%%###*
                    ......:*#*==-:::-=+*++*%%@%%@@@@@@%##@@@@@@@%%@@%%###=
                     .....=***===========*%%**#%*#%%%@@@@@@@@@@@%%%%%%%###=
                     .::...::-=========*++**+**%*+*%*#%@@@@@@@%%%%%%%%%%##%-
                     .=-.:=******==========+***#%*+#%%%%@@@@@@@@%%%%%%%%####-
                      -*+.::------========+***%%*+**%@@@@@@@%@@@@@%%%%%###**%=
                      :=#*::::::---======+**%@%%*+=+*@@@@@@%%@@@%%%%%%======+=
                      .=*#*:.:::--=====+*%@@%%%%%*=+**@@@@%%%%@@%%%%**:
                     ::=**%%-::::-=+*%%@%%%%%%##%%#+*##@@%%@%%%%%#%***.
                     -=+**%%%%==-=%%%%%%%%%%%##*%%@%*%%%@%%%%%%%%%#*%#.
                     .*=*#%%@=   .+=*%%%%##*****#%%@@%@@@%%%%%%%##%%%#*.
                     ==****%@*.   -:-==**********#%%@@@@@%%%%%%#%%%%%***.
                      =#**%@@#.  -#::::-=+++++**+*%%%@@@@@%%%%%%%%%%##**:
                       =%%@@%%:=***-.:.::-===+:===%%@@@@%@%%%%%%%%#*####.
                       .*%%@%%***##-..:..::-*+++==##@@@%%%%%%%%%%%**%%%=
                       +#*%%%%%%%%#-.:.:..::****==**@@@%%@%%%%%%%#%%%#*=:
                      =**#%%%@%%%%+=::.:..:-*#*#+==*%@@%%%%%%%%#%%%%***+:
                      .+#**%%%%%%*==-:...:-=*#*#%*++%%@@%%%%%%%%%%%#***+:
                       +**%##%#*+===-:.::--+#####%#**%@@%%%%%%%%%%#***+=:
                      :*+***+-:-:::.....::+*######%%##%@@%%%%%%%%#*****+.
                      -=-+:.             :***######%@#%@@%%%%%%%###***+-
                                         -***#######%%%@@%%%%%%##*****+:
                                         :********#%#@%@%%%%%%##*****+=.
                                          :==+******#@@@%####******++=:
                                                  .:=%@%##*##****=--:
                                                    +%%#**++=::
                                                  :*#*+==-:::.
                                                :*+: :.

True strength comes from our ability to forgive -
                            to forge ahead in the hope of making things right.
                                                                ~ Aeris

""".splitlines()

_PRESS_LINE = "PRESS Q / ESC to close"

_HELP_CONTENT: List[str] = _HELP_TEXT + ["", _PRESS_LINE, ""] + _ASCII_ART_LINES
_ASCII_ART_SET: frozenset = frozenset(_ASCII_ART_LINES)


def help_popup(stdscr) -> None:
    curses.curs_set(0)
    h, w = stdscr.getmaxyx()
    box_w = min(120, w - 4)
    box_h = min(h - 4, 35)

    try:
        win = curses.newwin(box_h, box_w, (h - box_h) // 2, (w - box_w) // 2)
    except curses.error:
        return

    win.keypad(True)
    win.nodelay(False)

    content = _HELP_CONTENT
    pos = 0
    max_pos = max(0, len(content) - (box_h - 2))
    bar_atr = curses.color_pair(C_BORDER)

    while True:
        win.erase()
        win.attron(bar_atr)
        win.border()
        win.attroff(bar_atr)

        for idx in range(box_h - 2):
            li = pos + idx
            if li >= len(content):
                break
            line = content[li]
            in_art = line in _ASCII_ART_SET  # O(1)

            if li == 0:
                attr = curses.color_pair(C_HDR) | curses.A_BOLD
            elif line.strip().isupper() and not line.startswith("PRESS"):
                attr = curses.color_pair(C_SECTION) | curses.A_BOLD
            elif line.startswith("PRESS"):
                attr = curses.color_pair(C_PEND_DEL) | curses.A_BOLD
            elif in_art:
                attr = curses.color_pair(C_PEND_ADD)
            else:
                attr = curses.color_pair(C_DIM) | curses.A_BOLD

            x = max(2, (box_w - len(line)) // 2) if in_art else 2
            sadd(win, idx + 1, x, line[: box_w - 4], attr)

        draw_scrollbar(win, 1, box_h - 2, box_w - 2, len(content), pos, bar_atr)
        win.refresh()

        key = win.getch()
        if key in (27, ord("q"), ord("Q")):
            break
        elif key in (curses.KEY_DOWN, ord("j")):
            pos = min(pos + 1, max_pos)
        elif key in (curses.KEY_UP, ord("k")):
            pos = max(pos - 1, 0)
        elif key == curses.KEY_PPAGE:
            pos = max(0, pos - (box_h - 2))
        elif key == curses.KEY_NPAGE:
            pos = min(max_pos, pos + (box_h - 2))
