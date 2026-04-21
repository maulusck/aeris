"""
AERIS · modal widgets — input box, confirm dialog, help popup, profile wizard

Changes from original
---------------------
* 3.9-safe: `from __future__ import annotations`; `Optional` / `List` instead
  of `X | Y` and `list[...]` in signatures.
* curses_input: input window uses blocking getch (nodelay=False) so the
  500 ms stdscr timeout does not leak in and make typing feel sluggish.
  Added Ctrl-A/E (BOL/EOL), Ctrl-U (kill line), Ctrl-W (kill word) readline
  shortcuts.
* confirm_dialog / _mini_confirm: refactored into a shared _bordered_dialog
  primitive to eliminate near-identical duplication.
* profile_wizard: profiles list only reloaded on mutations, not every frame.
  Removed dead `if False` branch + latent NameError on C_CUR_LIVE_PROF.
  Uses imported C_CUR_LIVE constant instead of magic number 10.
* help_popup: _HELP_CONTENT (joined list) is a module-level constant so it
  is never rebuilt. ASCII art lookup uses a frozenset for O(1) membership.
* All colour lookups use named constants — no bare pair numbers.
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


# ─────────────────────────────────────────────────────────────────────────────
# Text input widget
# ─────────────────────────────────────────────────────────────────────────────


def curses_input(
    stdscr,
    prompt: str,
    prefill: str = "",
    maxlen: int = 40,
) -> Optional[str]:
    """
    Floating amber input box with full cursor editing.

    Readline shortcuts supported:
      Ctrl-A / Home  — beginning of line
      Ctrl-E / End   — end of line
      Ctrl-U         — kill whole line
      Ctrl-W         — kill word left

    Returns stripped string, or None on Esc.
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

    # Block in the widget — don't inherit stdscr's 500 ms timeout.
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
    cpos = len(buf)

    def redraw() -> None:
        start = max(0, cpos - field_w + 1)
        view = "".join(buf)[start : start + field_w]
        sadd(win, 1, field_x, view.ljust(field_w), inp_a)
        try:
            win.move(1, field_x + (cpos - start))
        except curses.error:
            pass
        win.refresh()

    while True:
        redraw()
        ch = win.getch()

        if ch in (10, 13):  # Enter
            curses.curs_set(0)
            return "".join(buf).strip()

        elif ch == 27:  # Esc
            curses.curs_set(0)
            return None

        elif ch in (curses.KEY_BACKSPACE, 127, 8):  # Backspace
            if cpos > 0:
                buf.pop(cpos - 1)
                cpos -= 1

        elif ch == curses.KEY_DC:  # Delete
            if cpos < len(buf):
                buf.pop(cpos)

        elif ch in (curses.KEY_LEFT,):
            cpos = max(0, cpos - 1)

        elif ch in (curses.KEY_RIGHT,):
            cpos = min(len(buf), cpos + 1)

        elif ch in (curses.KEY_HOME, _CTRL_A):  # BOL
            cpos = 0

        elif ch in (curses.KEY_END, _CTRL_E):  # EOL
            cpos = len(buf)

        elif ch == _CTRL_U:  # Kill line
            buf.clear()
            cpos = 0

        elif ch == _CTRL_W:  # Kill word left
            # Eat trailing spaces, then eat non-space chars
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
# Shared bordered-dialog primitive
# ─────────────────────────────────────────────────────────────────────────────


def _bordered_dialog(
    stdscr,
    rows: List[Tuple[str, int]],
    border_attr: int,
    scrollable: bool = False,
) -> bool:
    """
    Generic modal dialog.

    Displays *rows* (text, attr) inside a centred bordered window.
    Returns True on Y/Enter, False on N/Esc.

    If *scrollable* is True the user can navigate with j/k/PgUp/PgDn.
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
    bar_col = box_w - 2
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
            draw_scrollbar(win, 1, inner_h, bar_col, len(rows), pos, curses.color_pair(C_BORDER))

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
# Confirm dialog  (apply diff)
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
    return _bordered_dialog(
        stdscr,
        rows,
        border_attr=curses.color_pair(C_CURSOR) | curses.A_BOLD,
        scrollable=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mini confirm  (reused inside profile wizard)
# ─────────────────────────────────────────────────────────────────────────────


def _mini_confirm(stdscr, rows: List[Tuple[str, int]]) -> bool:
    """Tiny inline confirm box reused by the profile wizard."""
    return _bordered_dialog(
        stdscr,
        rows,
        border_attr=curses.color_pair(C_BORDER),
        scrollable=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Profile wizard
# ─────────────────────────────────────────────────────────────────────────────

_PROF_HINT_MAIN = " jk/↑↓:move  ENTER:load  N:new  R:rename  X:delete  C:copy  ESC/Q:close"
_PROF_HINT_ERR_DUP = " Name already exists — choose another"
_PROF_HINT_ERR_NONE = " Nothing to act on"


def profile_wizard(stdscr, active_profile: str) -> Optional[str]:
    """
    Full-screen-ish floating popup for profile management.

    Returns
    -------
    str  — name of the profile to switch to (may equal *active_profile*
           if the user just closed without switching)
    None — caller should treat as "no change"

    Optimisation: the profiles list is only re-read from disk after a
    mutating operation (create / rename / delete / duplicate), not on
    every keypress.
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

    h, w = stdscr.getmaxyx()
    box_w = min(w - 6, 62)
    box_h = min(h - 4, 22)
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2

    try:
        win = curses.newwin(box_h, box_w, box_y, box_x)
    except curses.error:
        return None

    win.keypad(True)
    win.nodelay(False)

    profiles: List[str] = list_profiles()
    cursor = next((i for i, n in enumerate(profiles) if n == active_profile), 0)
    list_h = box_h - 5
    hint_msg = _PROF_HINT_MAIN

    # active-cursor colour
    _attr_cur_active = curses.color_pair(C_CUR_LIVE) | curses.A_BOLD
    _attr_cur = curses.color_pair(C_CURSOR) | curses.A_BOLD
    _attr_active = curses.color_pair(C_LOG_OK) | curses.A_BOLD
    _attr_dim = curses.color_pair(C_DIM)

    while True:
        # ── clamp / scroll ────────────────────────────────────────────────────
        cursor = max(0, min(cursor, len(profiles) - 1))
        scroll = max(0, min(cursor - list_h + 1, max(0, len(profiles) - list_h)))
        if cursor < scroll:
            scroll = cursor

        # ── draw ──────────────────────────────────────────────────────────────
        win.erase()
        win.attron(curses.color_pair(C_BORDER))
        win.border()
        win.attroff(curses.color_pair(C_BORDER))

        title = " PROFILES "
        sadd(
            win,
            0,
            (box_w - len(title)) // 2,
            title,
            curses.color_pair(C_HDR) | curses.A_BOLD,
        )
        sadd(win, 1, 1, hint_msg[: box_w - 2], curses.color_pair(C_HINT))
        hint_msg = _PROF_HINT_MAIN  # reset after one-frame error messages

        bar_col = box_w - 2
        for row_i in range(list_h):
            pi = scroll + row_i
            screen_row = 2 + row_i
            if pi >= len(profiles):
                break
            name = profiles[pi]
            is_active = name == active_profile
            is_cursor = pi == cursor

            if is_cursor and is_active:
                attr = _attr_cur_active
            elif is_cursor:
                attr = _attr_cur
            elif is_active:
                attr = _attr_active
            else:
                attr = _attr_dim

            marker = "▶" if is_active else " "
            line = f"  {marker} {name}"
            sadd(win, screen_row, 0, line[: box_w - 3].ljust(box_w - 3), attr)

        draw_scrollbar(
            win,
            2,
            list_h,
            bar_col,
            len(profiles),
            scroll,
            curses.color_pair(C_BORDER),
        )

        sadd(
            win,
            box_h - 2,
            1,
            "N:new  R:rename  X:del  C:copy  ENTER:load  Q:close"[: box_w - 2],
            curses.color_pair(C_DIM),
        )
        win.refresh()

        # ── input ─────────────────────────────────────────────────────────────
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

        elif key in (10, 13):  # Enter → load profile
            if profiles:
                return profiles[cursor]

        elif key in (ord("n"), ord("N")):
            name = curses_input(stdscr, "New profile name:", maxlen=32)
            if name:
                if not create_profile(name):
                    hint_msg = _PROF_HINT_ERR_DUP
                else:
                    profiles = list_profiles()  # reload after mutation
                    cursor = next(
                        (i for i, n in enumerate(profiles) if n == name),
                        cursor,
                    )

        elif key in (ord("r"), ord("R")):
            if not profiles:
                hint_msg = _PROF_HINT_ERR_NONE
            else:
                old = profiles[cursor]
                new = curses_input(stdscr, "Rename to:", prefill=old, maxlen=32)
                if new and new != old:
                    if not rename_profile(old, new):
                        hint_msg = _PROF_HINT_ERR_DUP
                    else:
                        if old == active_profile:
                            return new  # caller must update state
                        profiles = list_profiles()  # reload after mutation
                        cursor = next(
                            (i for i, n in enumerate(profiles) if n == new),
                            cursor,
                        )

        elif key in (ord("x"), ord("X")):
            if not profiles:
                hint_msg = _PROF_HINT_ERR_NONE
            else:
                name = profiles[cursor]
                confirm_rows: List[Tuple[str, int]] = [
                    (
                        f"  Delete profile '{name}' ?",
                        curses.color_pair(C_PEND_DEL) | curses.A_BOLD,
                    ),
                    ("", 0),
                    (
                        "  [Y] delete   [N] cancel",
                        curses.color_pair(C_SECTION) | curses.A_BOLD,
                    ),
                ]
                if _mini_confirm(stdscr, confirm_rows):
                    delete_profile(name)
                    profiles = list_profiles()  # reload after mutation
                    cursor = max(0, min(cursor, len(profiles) - 1))
                    if name == active_profile:
                        return profiles[cursor] if profiles else "default"

        elif key in (ord("c"), ord("C")):
            if not profiles:
                hint_msg = _PROF_HINT_ERR_NONE
            else:
                src = profiles[cursor]
                dst = curses_input(stdscr, f"Copy '{src}' to:", maxlen=32)
                if dst:
                    if not duplicate_profile(src, dst):
                        hint_msg = _PROF_HINT_ERR_DUP
                    else:
                        profiles = list_profiles()  # reload after mutation
                        cursor = next(
                            (i for i, n in enumerate(profiles) if n == dst),
                            cursor,
                        )


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

# Module-level constant: built once, reused on every popup open.
_HELP_CONTENT: List[str] = _HELP_TEXT + ["", _PRESS_LINE, ""] + _ASCII_ART_LINES

# Frozenset for O(1) membership test in the render loop.
_ASCII_ART_SET: frozenset = frozenset(_ASCII_ART_LINES)


def help_popup(stdscr) -> None:
    curses.curs_set(0)
    h, w = stdscr.getmaxyx()
    box_w = min(120, w - 4)
    box_h = min(h - 4, 35)
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2

    content = _HELP_CONTENT  # reuse constant, no allocation

    try:
        win = curses.newwin(box_h, box_w, box_y, box_x)
    except curses.error:
        return

    win.keypad(True)
    win.nodelay(False)

    pos = 0
    max_pos = max(0, len(content) - (box_h - 2))
    bar_col = box_w - 2
    bar_atr = curses.color_pair(C_BORDER)

    while True:
        win.erase()
        win.attron(curses.color_pair(C_BORDER))
        win.border()
        win.attroff(curses.color_pair(C_BORDER))

        for idx in range(box_h - 2):
            li = pos + idx
            if li >= len(content):
                break
            line = content[li]

            if li == 0:
                attr = curses.color_pair(C_HDR) | curses.A_BOLD
            elif line.strip().isupper() and not line.startswith("PRESS"):
                attr = curses.color_pair(C_SECTION) | curses.A_BOLD
            elif line.startswith("PRESS"):
                attr = curses.color_pair(C_PEND_DEL) | curses.A_BOLD
            elif line in _ASCII_ART_SET:  # O(1) — frozenset lookup
                attr = curses.color_pair(C_PEND_ADD)
            else:
                attr = curses.color_pair(C_DIM) | curses.A_BOLD

            x_pos = 2
            if line in _ASCII_ART_SET:
                x_pos = max(2, (box_w - len(line)) // 2)
            sadd(win, idx + 1, x_pos, line[: box_w - 4], attr)

        draw_scrollbar(win, 1, box_h - 2, bar_col, len(content), pos, bar_atr)
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
