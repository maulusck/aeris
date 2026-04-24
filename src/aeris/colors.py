"""
AERIS · colour-pair constants and initialisation

Themes:  amber (default) · matrix · mono
Select via AERIS_THEME env-var or --theme flag.
"""

from __future__ import annotations

import curses
from dataclasses import astuple, dataclass
from typing import Sequence

# Colour-pair slot IDs — never renumber these
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


@dataclass(frozen=True)
class _Palette:
    """(fg, bg) for every slot, in slot-ID order 1–20."""

    hdr: tuple[int, int]
    hint: tuple[int, int]
    border: tuple[int, int]
    section: tuple[int, int]
    dim: tuple[int, int]
    live: tuple[int, int]
    pend_add: tuple[int, int]
    pend_del: tuple[int, int]
    cursor: tuple[int, int]
    cur_live: tuple[int, int]
    cur_padd: tuple[int, int]
    cur_pdel: tuple[int, int]
    stat_liv: tuple[int, int]
    stat_add: tuple[int, int]
    stat_del: tuple[int, int]
    log_ok: tuple[int, int]
    log_err: tuple[int, int]
    log_cmd: tuple[int, int]
    log_info: tuple[int, int]
    inp: tuple[int, int]


def _apply(p: _Palette) -> None:
    for slot, (fg, bg) in enumerate(astuple(p), start=1):
        curses.init_pair(slot, fg, bg)


def _amber() -> _Palette:
    A, CY, GR, RE = 214, 51, 82, 196
    BLK, DGY, MGY, LGY, bg = 16, 236, 242, 248, -1
    return _Palette(
        hdr=(BLK, A),
        hint=(MGY, DGY),
        border=(DGY, bg),
        section=(A, bg),
        dim=(MGY, bg),
        live=(GR, bg),
        pend_add=(CY, bg),
        pend_del=(RE, bg),
        cursor=(BLK, CY),
        cur_live=(BLK, GR),
        cur_padd=(BLK, CY),
        cur_pdel=(BLK, RE),
        stat_liv=(MGY, bg),
        stat_add=(CY, bg),
        stat_del=(RE, bg),
        log_ok=(GR, bg),
        log_err=(RE, bg),
        log_cmd=(MGY, bg),
        log_info=(LGY, bg),
        inp=(A, BLK),
    )


def _mono() -> _Palette:
    Y, C, G, R, W, K, bg = (curses.COLOR_YELLOW, curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_WHITE, curses.COLOR_BLACK, -1)
    return _Palette(
        hdr=(K, Y),
        hint=(W, K),
        border=(W, bg),
        section=(Y, bg),
        dim=(W, bg),
        live=(G, bg),
        pend_add=(C, bg),
        pend_del=(R, bg),
        cursor=(K, C),
        cur_live=(K, G),
        cur_padd=(K, C),
        cur_pdel=(K, R),
        stat_liv=(W, bg),
        stat_add=(C, bg),
        stat_del=(R, bg),
        log_ok=(G, bg),
        log_err=(R, bg),
        log_cmd=(W, bg),
        log_info=(W, bg),
        inp=(Y, K),
    )


def _matrix() -> _Palette:
    GRB, GRD, GRM = 46, 28, 34
    YEL, RED, CYN = 226, 196, 51
    BLK, DGY, bg = 16, 232, -1
    return _Palette(
        hdr=(BLK, GRB),
        hint=(GRD, DGY),
        border=(GRD, bg),
        section=(GRM, bg),
        dim=(GRD, bg),
        live=(GRB, bg),
        pend_add=(YEL, bg),
        pend_del=(RED, bg),
        cursor=(BLK, CYN),
        cur_live=(BLK, GRB),
        cur_padd=(BLK, YEL),
        cur_pdel=(BLK, RED),
        stat_liv=(GRM, bg),
        stat_add=(YEL, bg),
        stat_del=(RED, bg),
        log_ok=(GRB, bg),
        log_err=(RED, bg),
        log_cmd=(GRD, bg),
        log_info=(GRM, bg),
        inp=(GRB, BLK),
    )


THEMES: dict[str, _Palette] = {}


def init_colors(theme: str = "") -> None:
    from aeris.config import THEME as cfg_theme

    curses.start_color()
    curses.use_default_colors()
    global THEMES
    THEMES = {"amber": _amber(), "mono": _mono(), "matrix": _matrix()}
    try:
        _apply(THEMES.get(theme or cfg_theme, THEMES["amber"]))
    except Exception:
        _apply(THEMES["mono"])
