"""
AERIS · modal widgets — input box, confirm dialog, help popup, profile wizard
"""

import curses

from aeris.colors import (
    C_BORDER,
    C_CURSOR,
    C_DIM,
    C_HDR,
    C_HINT,
    C_INPUT,
    C_LOG_ERR,
    C_LOG_OK,
    C_PEND_ADD,
    C_PEND_DEL,
    C_SECTION,
)
from aeris.config import LOG_PANEL_H
from aeris.drawing import draw_scrollbar, sadd

NAME_W = 13


def curses_input(stdscr, prompt: str, prefill: str = "", maxlen: int = 40) -> str | None:
    """
    Floating amber input box with full cursor editing.
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

    inp_a = curses.color_pair(C_INPUT) | curses.A_BOLD
    lbl_a = curses.color_pair(C_SECTION) | curses.A_BOLD

    win.attron(inp_a)
    win.border()
    win.attroff(inp_a)

    label = f" {prompt} "
    field_x = 2 + len(label)
    field_w = max(4, box_w - field_x - 3)
    sadd(win, 1, 2, label, lbl_a)

    buf = list(prefill[:maxlen])
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
        ch = stdscr.getch()
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
        elif ch == curses.KEY_HOME:
            cpos = 0
        elif ch == curses.KEY_END:
            cpos = len(buf)
        elif 32 <= ch <= 126 and len(buf) < maxlen:
            buf.insert(cpos, chr(ch))
            cpos += 1


def confirm_dialog(stdscr, removing: list[str], adding: list[str]) -> bool:
    h, w = stdscr.getmaxyx()

    rows: list[tuple[str, int]] = [
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

    box_h = min(h - 4, len(rows) + 2)
    box_w = min(w - 6, max(len(t) for t, _ in rows) + 4)
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2

    try:
        win = curses.newwin(box_h, box_w, box_y, box_x)
    except curses.error:
        return False

    win.keypad(True)
    pos = 0
    max_pos = max(0, len(rows) - (box_h - 2))
    bar_col = box_w - 2
    bar_atr = curses.color_pair(C_BORDER)

    while True:
        win.erase()
        win.attron(curses.color_pair(C_CURSOR) | curses.A_BOLD)
        win.border()
        win.attroff(curses.color_pair(C_CURSOR) | curses.A_BOLD)

        for i in range(box_h - 2):
            ri = pos + i
            if ri >= len(rows):
                break
            text, attr = rows[ri]
            sadd(win, i + 1, 1, text[: box_w - 2], attr)

        draw_scrollbar(win, 1, box_h - 2, bar_col, len(rows), pos, bar_atr)
        win.refresh()

        ch = win.getch()
        if ch in (ord("y"), ord("Y"), 10, 13):
            return True
        if ch in (ord("n"), ord("N"), 27):
            return False
        elif ch in (curses.KEY_DOWN, ord("j")):
            pos = min(pos + 1, max_pos)
        elif ch in (curses.KEY_UP, ord("k")):
            pos = max(pos - 1, 0)
        elif ch == curses.KEY_PPAGE:
            pos = max(0, pos - (box_h - 2))
        elif ch == curses.KEY_NPAGE:
            pos = min(max_pos, pos + (box_h - 2))


_PROF_HINT_MAIN = " jk/↑↓:move  ENTER:load  N:new  R:rename  X:delete  C:copy  ESC/Q:close"
_PROF_HINT_ERR_DUP = " Name already exists — choose another"
_PROF_HINT_ERR_NONE = " Nothing to act on"


def profile_wizard(stdscr, active_profile: str) -> str | None:
    """
    Full-screen-ish floating popup for profile management.

    Returns
    -------
    str  — name of the profile to switch to (may equal *active_profile*
           if user just closed without switching)
    None — caller should treat as "no change" (same as returning active_profile)
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

    hint_msg = _PROF_HINT_MAIN

    def _reload() -> list[str]:
        return list_profiles()

    profiles = _reload()

    cursor = next((i for i, n in enumerate(profiles) if n == active_profile), 0)
    list_h = box_h - 5

    while True:
        profiles = _reload()
        cursor = max(0, min(cursor, len(profiles) - 1))
        scroll = max(0, min(cursor - list_h + 1, max(0, len(profiles) - list_h)))
        if cursor < scroll:
            scroll = cursor

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

        sadd(win, 1, 1, _PROF_HINT_MAIN[: box_w - 2], curses.color_pair(C_HINT))

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
                attr = curses.color_pair(C_CUR_LIVE_PROF) if False else (curses.color_pair(C_CURSOR) | curses.A_BOLD)

                attr = curses.color_pair(10) | curses.A_BOLD
            elif is_cursor:
                attr = curses.color_pair(C_CURSOR) | curses.A_BOLD
            elif is_active:
                attr = curses.color_pair(C_LOG_OK) | curses.A_BOLD
            else:
                attr = curses.color_pair(C_DIM)

            marker = "▶" if is_active else " "
            line = f"  {marker} {name}"
            sadd(win, screen_row, 1, line.ljust(box_w - 3)[: box_w - 3], attr)

        draw_scrollbar(
            win,
            2,
            list_h,
            bar_col,
            len(profiles),
            scroll,
            curses.color_pair(C_BORDER),
        )

        hint_attr = curses.color_pair(C_LOG_ERR) | curses.A_BOLD if hint_msg != _PROF_HINT_MAIN else curses.color_pair(C_HINT)
        sadd(win, box_h - 2, 1, hint_msg[: box_w - 2], hint_attr)

        win.refresh()
        hint_msg = _PROF_HINT_MAIN

        key = win.getch()

        if key in (27, ord("q"), ord("Q")):
            return None

        elif key in (curses.KEY_DOWN, ord("j")):
            cursor = min(cursor + 1, len(profiles) - 1)

        elif key in (curses.KEY_UP, ord("k")):
            cursor = max(cursor - 1, 0)

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
                    hint_msg = _PROF_HINT_ERR_DUP
                else:
                    profiles = _reload()
                    cursor = next((i for i, n in enumerate(profiles) if n == name), cursor)

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
                            return new
                        profiles = _reload()
                        cursor = next((i for i, n in enumerate(profiles) if n == new), cursor)

        elif key in (ord("x"), ord("X")):
            if not profiles:
                hint_msg = _PROF_HINT_ERR_NONE
            else:
                name = profiles[cursor]

                rows = [
                    (f"  Delete profile '{name}' ?", curses.color_pair(C_PEND_DEL) | curses.A_BOLD),
                    ("", 0),
                    ("  [Y] delete   [N] cancel", curses.color_pair(C_SECTION) | curses.A_BOLD),
                ]
                if _mini_confirm(stdscr, rows):
                    delete_profile(name)

                    profiles = _reload()
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
                        profiles = _reload()
                        cursor = next((i for i, n in enumerate(profiles) if n == dst), cursor)


def _mini_confirm(stdscr, rows: list[tuple[str, int]]) -> bool:
    """Tiny inline confirm box reused by the profile wizard."""
    h, w = stdscr.getmaxyx()
    box_h = min(h - 4, len(rows) + 2)
    box_w = min(w - 10, max(len(t) for t, _ in rows) + 4)
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2
    try:
        win = curses.newwin(box_h, box_w, box_y, box_x)
    except curses.error:
        return False
    win.keypad(True)
    while True:
        win.erase()
        win.attron(curses.color_pair(C_BORDER))
        win.border()
        win.attroff(curses.color_pair(C_BORDER))
        for i, (text, attr) in enumerate(rows):
            sadd(win, i + 1, 1, text[: box_w - 2], attr)
        win.refresh()
        ch = win.getch()
        if ch in (ord("y"), ord("Y"), 10, 13):
            return True
        if ch in (ord("n"), ord("N"), 27):
            return False


_HELP_TEXT = """\
AERIS · Avionic Ethernet Rig IP Selector
─────────────────────────────────────────────

KEYBINDINGS
  ↑ / k        Move cursor up
  ↓ / j        Move cursor down
  SPC          Toggle IP selection
  N            Add IP to profile
  E            Rename IP entry
  D            Delete IP from profile
  A            Apply selected IPs
  R            Refresh active IPs
  P            Profile manager
  ?            Show this help
  Q / ESC      Quit

DESCRIPTION
  Select, add, rename, and apply IPv4 addresses to the Ethernet interface.
  IPs are organised into profiles stored in ~/.config/aeris/profiles/.
  The active profile is shown in the title bar.
  The live IPs are displayed at the top; pending additions/removals are
  highlighted in colour.

EXAMPLES
  - Toggle multiple IPs with SPC and press A to apply.
  - Add a new IP with N, label it, then apply.
  - Use R to refresh active IPs after changes outside AERIS.
  - Press P to switch profiles or create new ones.

NOTES
  - All IPs within a profile are equal and fully editable.
  - The default profile is recreated from built-in defaults if deleted.
  - Scroll lists with ↑/↓ or j/k, exit with Q or ESC.\
""".splitlines()

_ASCII_ART = """\


                             =:=.
                           .=:.:*-
                        .=+*-.::*%%*:.
                       .****:-=:=%%%
                       .**
               ..      -%*
      .::::.:*****
   .==++***%%%%%**
  .:-*****
   :-=***%@@@%
  :=+:+=+*%@@@%%
 :==*=-==*%%%%%%
  ::++:--**: .:+**
  :.=+:-:+
  .::*--:*
  ::-+--=*
  .:-*-=+
  .-=*==*%=       :*:...........:--=+*
  :=*
  =+
  :
   .
    .*%%*%%%*:    -=+**:...:=*
      =
       -+    :**: ::*%
        -.     .== .=**-.........:***+:=*=
        ..       .:====:...::.:.:.::::::=*%%%@@@@@@@@@@%
                   .:..:..:-*=-:.:.::::=*
                    ......:*
                     .....=***===========*%%**
                     .::...::-=========*++**+**%*+*%*
                     .=-.:=******==========+***
                      -*+.::------========+***%%*+**%@@@@@@@%@@@@@%%%%%
                      :=
                      .=*
                     ::=**%%-::::-=+*%%@%%%%%%
                     -=+**%%%%==-=%%%%%%%%%%%
                     .*=*
                     ==****%@*.   -:-==**********
                      =
                       =%%@@%%:=***-.:.::-===+:===%%@@@@%@%%%%%%%%
                       .*%%@%%***
                       +
                      =**
                      .+
                       +**%
                      :*+***+-:-:::.....::+*
                      -=-+:.             :***
                                         -***
                                         :********
                                          :==+******
                                                  .:=%@%
                                                    +%%
                                                  :*
                                                :*+: :.

True strength comes from our ability to forgive -
                            to forge ahead in the hope of making things right.
                                                                ~ Aeris

""".splitlines()

_PRESS_LINE = "PRESS Q / ESC to close"


def help_popup(stdscr) -> None:
    curses.curs_set(0)
    h, w = stdscr.getmaxyx()
    box_w = min(120, w - 4)
    box_h = min(h - 4, 35)
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2

    content = _HELP_TEXT + [""] + [_PRESS_LINE] + [""] + _ASCII_ART

    try:
        win = curses.newwin(box_h, box_w, box_y, box_x)
    except curses.error:
        return

    win.keypad(True)
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
            elif line in _ASCII_ART:
                attr = curses.color_pair(C_PEND_ADD)
            else:
                attr = curses.color_pair(C_DIM) | curses.A_BOLD

            x_pos = 2
            if line in _ASCII_ART:
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
