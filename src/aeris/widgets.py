"""
AERIS · modal widgets — input box, confirm dialog, help popup
"""
import curses
from aeris.colors import (
    C_INPUT, C_SECTION, C_BORDER, C_HDR, C_HINT,
    C_CURSOR, C_PEND_ADD, C_PEND_DEL, C_DIM,
)
from aeris.drawing import sadd, draw_scrollbar
from aeris.config import LOG_PANEL_H

NAME_W = 13   # max visible name width in entry list


# ─────────────────────────────────────────────────────────────
#  Floating input box
# ─────────────────────────────────────────────────────────────
def curses_input(stdscr, prompt: str, prefill: str = "",
                 maxlen: int = 40) -> str | None:
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

    inp_a = curses.color_pair(C_INPUT)   | curses.A_BOLD
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

    def redraw() -> None:
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


# ─────────────────────────────────────────────────────────────
#  Confirm dialog
# ─────────────────────────────────────────────────────────────
def confirm_dialog(stdscr, removing: list[str],
                   adding: list[str]) -> bool:
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
        ("  [Y] apply   [N] cancel",
         curses.color_pair(C_SECTION) | curses.A_BOLD),
    ]

    box_h = min(h - 4, len(rows) + 2)
    box_w = min(w - 6, max(len(t) for t, _ in rows) + 4)
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2

    try:
        win = curses.newwin(box_h, box_w, box_y, box_x)
    except curses.error:
        return False   # fail-safe: never auto-apply

    win.keypad(True)
    pos     = 0
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

        draw_scrollbar(win, 1, box_h - 2, bar_col,
                       len(rows), pos, bar_atr)
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


# ─────────────────────────────────────────────────────────────
#  Help popup
# ─────────────────────────────────────────────────────────────
_HELP_TEXT = """\
AERIS · Avionic Ethernet Rig IP Selector
─────────────────────────────────────────────

KEYBINDINGS
  ↑ / k        Move cursor up
  ↓ / j        Move cursor down
  SPC          Toggle IP selection
  N            Add custom IP
  E            Rename custom IP
  D            Delete custom IP
  A            Apply selected IPs
  R            Refresh active IPs
  ?            Show this help
  Q / ESC      Quit

DESCRIPTION
  Select, add, rename, and apply IPv4 addresses to the Ethernet interface.
  Entries are divided into PREDEFINED (fixed) and CUSTOM (editable) lists.
  The live IPs are displayed at the top; pending additions/removals are
  highlighted in colour.

EXAMPLES
  - Toggle multiple IPs with SPC and press A to apply.
  - Add a new IP with N, label it, then apply.
  - Use R to refresh active IPs after changes outside AERIS.

NOTES
  - Predefined entries cannot be renamed or deleted.
  - Custom entries are saved to ~/.rig-ip-switcher.json
  - Scroll lists with ↑/↓ or j/k, exit with Q or ESC.\
""".splitlines()

_ASCII_ART = """\


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
""".splitlines()

_PRESS_LINE = "PRESS Q / ESC to close"


def help_popup(stdscr) -> None:
    curses.curs_set(0)
    h, w = stdscr.getmaxyx()
    box_w = min(100, w - 4)
    box_h = min(h - 4, 28)
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2

    content = _HELP_TEXT + [""] + [_PRESS_LINE] + [""] + _ASCII_ART

    try:
        win = curses.newwin(box_h, box_w, box_y, box_x)
    except curses.error:
        return

    win.keypad(True)
    pos     = 0
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

        draw_scrollbar(win, 1, box_h - 2, bar_col,
                       len(content), pos, bar_atr)
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
