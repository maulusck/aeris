# AERIS · Avionic Ethernet Rig IP Selector

A curses TUI for managing multiple static IPv4 addresses on a single
NetworkManager-controlled Ethernet interface via `nmcli`.

---

## Installation

```bash
pip install aeris-ip-switcher
```

Or from source:

```bash
git clone <repo>
cd aeris
pip install .
```

## Usage

```bash
aeris
```

Or from Python:

```python
from aeris import main
main()
```

## Configuration

Edit `aeris/config.py` (or monkey-patch at runtime) to change:

| Variable      | Default                        | Description                        |
|---------------|--------------------------------|------------------------------------|
| `NMCLI`       | `"nmcli"`                      | Path to the `nmcli` binary         |
| `CON_ID`      | `"eth-operator"`               | NetworkManager connection name     |
| `IFACE`       | `"eth0"`                       | Network interface                  |
| `STATE_FILE`  | `~/.rig-ip-switcher.json`      | Custom-IP persistence file         |
| `LOG_MAX_LINES` | `200`                        | Maximum log lines kept in memory   |
| `LOG_PANEL_H` | `7`                            | Height of the log panel (rows)     |
| `PREDEFINED`  | `[Office, Lab, Test VM]`       | Built-in IP presets                |

## Key bindings

| Key          | Action                        |
|--------------|-------------------------------|
| `↑` / `k`   | Move cursor up                |
| `↓` / `j`   | Move cursor down              |
| `SPC`        | Toggle IP selection           |
| `N`          | Add custom IP                 |
| `E`          | Rename custom IP              |
| `D`          | Delete custom IP              |
| `A`          | Apply selected IPs            |
| `R`          | Refresh active IPs            |
| `[` / `]`   | Scroll log up / down          |
| `Shift+PgUp/Dn` | Page-scroll the log       |
| `?`          | Help popup                    |
| `Q` / `ESC` | Quit                          |

## Log panel scroll behaviour

- The log panel **always auto-follows** (sticks to the bottom) whenever a new
  event is appended — even if the user previously scrolled up.
- Scrolling up with `[` or `Shift+PgUp` enters *historical view*; a red
  `↑N` badge shows how many lines are hidden below.
- Pressing `]` / `Shift+PgDn` back to position 0 re-enables auto-follow.
- Any action that produces log output (apply, add, delete, refresh, error)
  automatically snaps the log back to the bottom.

## Package layout

```
aeris/
├── __init__.py      re-exports main()
├── app.py           main event loop
├── colors.py        colour-pair constants + init_colors()
├── config.py        user-tunable knobs
├── drawing.py       sadd(), hln(), draw_scrollbar()
├── network.py       nmcli wrappers
├── persistence.py   load/save custom IPs
├── tui.py           draw_ui()
├── utils.py         logging helpers, IP validation
└── widgets.py       input box, confirm dialog, help popup
```
