"""
AERIS · colour-pair constants and initialisation

Themes
------
  "amber"  — 256-colour xterm palette (default; warm amber/cyan/green accents)
  "mono"   — 8-colour ANSI fallback (works on every terminal)

Select via AERIS_THEME env-var or aeris.config.THEME.
Calling init_colors() reads config.THEME automatically.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass
from typing import Tuple

# ── colour-pair slot names (stable integers, never change these) ─────────────
C_HDR = 1
C_HINT = 2
C_BORDER = 3
C_SECTION = 4
C_DIM = 5

C_LIVE = 6
C_PEND_ADD = 7
C_PEND_DEL = 8
C_CURSOR = 9
C_CUR_LIVE = 10
C_CUR_PADD = 11
C_CUR_PDEL = 12

C_STAT_LIV = 13
C_STAT_ADD = 14
C_STAT_DEL = 15

C_LOG_OK = 16
C_LOG_ERR = 17
C_LOG_CMD = 18
C_LOG_INFO = 19

C_INPUT = 20


# ── theme dataclass ───────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Palette:
    """Foreground / background pairs for every colour slot."""

    # raw curses colour indices — fg, bg  (bg=-1 means terminal default)
    hdr_fg: int
    hdr_bg: int
    hint_fg: int
    hint_bg: int
    border_fg: int
    border_bg: int
    section_fg: int
    section_bg: int
    dim_fg: int
    dim_bg: int
    live_fg: int
    live_bg: int
    pend_add_fg: int
    pend_add_bg: int
    pend_del_fg: int
    pend_del_bg: int
    cursor_fg: int
    cursor_bg: int
    cur_live_fg: int
    cur_live_bg: int
    cur_padd_fg: int
    cur_padd_bg: int
    cur_pdel_fg: int
    cur_pdel_bg: int
    stat_liv_fg: int
    stat_liv_bg: int
    stat_add_fg: int
    stat_add_bg: int
    stat_del_fg: int
    stat_del_bg: int
    log_ok_fg: int
    log_ok_bg: int
    log_err_fg: int
    log_err_bg: int
    log_cmd_fg: int
    log_cmd_bg: int
    log_info_fg: int
    log_info_bg: int
    input_fg: int
    input_bg: int


def _amber_palette() -> _Palette:
    """256-colour warm amber theme."""
    A = 214  # amber
    CY = 51  # bright cyan
    GR = 82  # bright green
    RE = 196  # bright red
    BLK = 16  # true black
    DGY = 236  # dark grey  (background tint)
    MGY = 242  # mid grey
    LGY = 248  # light grey
    bg = -1  # terminal default background

    return _Palette(
        hdr_fg=BLK,
        hdr_bg=A,
        hint_fg=MGY,
        hint_bg=DGY,
        border_fg=DGY,
        border_bg=bg,
        section_fg=A,
        section_bg=bg,
        dim_fg=MGY,
        dim_bg=bg,
        live_fg=GR,
        live_bg=bg,
        pend_add_fg=CY,
        pend_add_bg=bg,
        pend_del_fg=RE,
        pend_del_bg=bg,
        cursor_fg=BLK,
        cursor_bg=CY,
        cur_live_fg=BLK,
        cur_live_bg=GR,
        cur_padd_fg=BLK,
        cur_padd_bg=CY,
        cur_pdel_fg=BLK,
        cur_pdel_bg=RE,
        stat_liv_fg=MGY,
        stat_liv_bg=bg,
        stat_add_fg=CY,
        stat_add_bg=bg,
        stat_del_fg=RE,
        stat_del_bg=bg,
        log_ok_fg=GR,
        log_ok_bg=bg,
        log_err_fg=RE,
        log_err_bg=bg,
        log_cmd_fg=MGY,
        log_cmd_bg=bg,
        log_info_fg=LGY,
        log_info_bg=bg,
        input_fg=A,
        input_bg=BLK,
    )


def _mono_palette() -> _Palette:
    """8-colour ANSI palette — works on every terminal."""
    Y = curses.COLOR_YELLOW
    C = curses.COLOR_CYAN
    G = curses.COLOR_GREEN
    R = curses.COLOR_RED
    W = curses.COLOR_WHITE
    K = curses.COLOR_BLACK
    bg = -1

    return _Palette(
        hdr_fg=K,
        hdr_bg=Y,
        hint_fg=W,
        hint_bg=K,
        border_fg=W,
        border_bg=bg,
        section_fg=Y,
        section_bg=bg,
        dim_fg=W,
        dim_bg=bg,
        live_fg=G,
        live_bg=bg,
        pend_add_fg=C,
        pend_add_bg=bg,
        pend_del_fg=R,
        pend_del_bg=bg,
        cursor_fg=K,
        cursor_bg=C,
        cur_live_fg=K,
        cur_live_bg=G,
        cur_padd_fg=K,
        cur_padd_bg=C,
        cur_pdel_fg=K,
        cur_pdel_bg=R,
        stat_liv_fg=W,
        stat_liv_bg=bg,
        stat_add_fg=C,
        stat_add_bg=bg,
        stat_del_fg=R,
        stat_del_bg=bg,
        log_ok_fg=G,
        log_ok_bg=bg,
        log_err_fg=R,
        log_err_bg=bg,
        log_cmd_fg=W,
        log_cmd_bg=bg,
        log_info_fg=W,
        log_info_bg=bg,
        input_fg=Y,
        input_bg=K,
    )


def _matrix_palette() -> _Palette:
    """
    Retro-avionic matrix theme — phosphor green on black.
    Accent colours follow classic CRT/MFD conventions:
      green  = nominal / live
      yellow = pending add / highlight
      red    = pending del / error
      cyan   = cursor / input
    Requires a 256-colour terminal; falls back to 'mono' automatically.
    """
    GRB = 46  # bright phosphor green  (foreground default)
    GRD = 28  # dim green              (borders, hints)
    GRM = 34  # mid green              (section headers)
    YEL = 226  # amber-yellow           (title bar bg, add pending)
    RED = 196  # bright red             (delete / error)
    CYN = 51  # cyan                   (cursor highlight)
    BLK = 16  # true black             (backgrounds)
    DGY = 232  # near-black tint        (subtle bg)
    bg = -1  # terminal default background

    return _Palette(
        hdr_fg=BLK,
        hdr_bg=GRB,
        hint_fg=GRD,
        hint_bg=DGY,
        border_fg=GRD,
        border_bg=bg,
        section_fg=GRM,
        section_bg=bg,
        dim_fg=GRD,
        dim_bg=bg,
        live_fg=GRB,
        live_bg=bg,
        pend_add_fg=YEL,
        pend_add_bg=bg,
        pend_del_fg=RED,
        pend_del_bg=bg,
        cursor_fg=BLK,
        cursor_bg=CYN,
        cur_live_fg=BLK,
        cur_live_bg=GRB,
        cur_padd_fg=BLK,
        cur_padd_bg=YEL,
        cur_pdel_fg=BLK,
        cur_pdel_bg=RED,
        stat_liv_fg=GRM,
        stat_liv_bg=bg,
        stat_add_fg=YEL,
        stat_add_bg=bg,
        stat_del_fg=RED,
        stat_del_bg=bg,
        log_ok_fg=GRB,
        log_ok_bg=bg,
        log_err_fg=RED,
        log_err_bg=bg,
        log_cmd_fg=GRD,
        log_cmd_bg=bg,
        log_info_fg=GRM,
        log_info_bg=bg,
        input_fg=GRB,
        input_bg=BLK,
    )


THEMES: dict[str, _Palette] = {}  # populated lazily after curses.start_color


def _apply_palette(p: _Palette) -> None:
    """Register every pair from a palette into curses."""
    pairs: Tuple[Tuple[int, int, int], ...] = (
        (C_HDR, p.hdr_fg, p.hdr_bg),
        (C_HINT, p.hint_fg, p.hint_bg),
        (C_BORDER, p.border_fg, p.border_bg),
        (C_SECTION, p.section_fg, p.section_bg),
        (C_DIM, p.dim_fg, p.dim_bg),
        (C_LIVE, p.live_fg, p.live_bg),
        (C_PEND_ADD, p.pend_add_fg, p.pend_add_bg),
        (C_PEND_DEL, p.pend_del_fg, p.pend_del_bg),
        (C_CURSOR, p.cursor_fg, p.cursor_bg),
        (C_CUR_LIVE, p.cur_live_fg, p.cur_live_bg),
        (C_CUR_PADD, p.cur_padd_fg, p.cur_padd_bg),
        (C_CUR_PDEL, p.cur_pdel_fg, p.cur_pdel_bg),
        (C_STAT_LIV, p.stat_liv_fg, p.stat_liv_bg),
        (C_STAT_ADD, p.stat_add_fg, p.stat_add_bg),
        (C_STAT_DEL, p.stat_del_fg, p.stat_del_bg),
        (C_LOG_OK, p.log_ok_fg, p.log_ok_bg),
        (C_LOG_ERR, p.log_err_fg, p.log_err_bg),
        (C_LOG_CMD, p.log_cmd_fg, p.log_cmd_bg),
        (C_LOG_INFO, p.log_info_fg, p.log_info_bg),
        (C_INPUT, p.input_fg, p.input_bg),
    )
    for slot, fg, bg in pairs:
        curses.init_pair(slot, fg, bg)


def init_colors(theme: str = "") -> None:
    """
    Initialise all colour pairs for *theme*.

    Falls back gracefully:
      1. Try the requested theme (default: config.THEME).
      2. If 256-colour init fails, fall back to "mono".
    """
    from aeris.config import THEME as cfg_theme

    chosen = theme or cfg_theme

    curses.start_color()
    curses.use_default_colors()

    # Build palette registry now that curses colour constants are valid
    global THEMES
    THEMES = {
        "amber": _amber_palette(),
        "mono": _mono_palette(),
        "matrix": _matrix_palette(),
    }

    palette = THEMES.get(chosen, THEMES["amber"])

    try:
        _apply_palette(palette)
    except Exception:
        # Terminal does not support 256 colours — silently fall back
        _apply_palette(THEMES["mono"])
