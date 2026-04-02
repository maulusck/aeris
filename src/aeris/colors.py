"""
AERIS · color-pair constants and initialisation
"""

import curses

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


def init_colors() -> None:
    """Initialise all colour pairs; falls back to 8-colour terminals."""
    curses.start_color()
    curses.use_default_colors()
    bg = -1

    try:
        A = 214
        CY = 51
        GR = 82
        RE = 196
        BLK = 16
        DGY = 236
        MGY = 242
        LGY = 248

        curses.init_pair(C_HDR, BLK, A)
        curses.init_pair(C_HINT, MGY, DGY)
        curses.init_pair(C_BORDER, DGY, bg)
        curses.init_pair(C_SECTION, A, bg)
        curses.init_pair(C_DIM, MGY, bg)
        curses.init_pair(C_LIVE, GR, bg)
        curses.init_pair(C_PEND_ADD, CY, bg)
        curses.init_pair(C_PEND_DEL, RE, bg)
        curses.init_pair(C_CURSOR, BLK, CY)
        curses.init_pair(C_CUR_LIVE, BLK, GR)
        curses.init_pair(C_CUR_PADD, BLK, CY)
        curses.init_pair(C_CUR_PDEL, BLK, RE)
        curses.init_pair(C_STAT_LIV, MGY, bg)
        curses.init_pair(C_STAT_ADD, CY, bg)
        curses.init_pair(C_STAT_DEL, RE, bg)
        curses.init_pair(C_LOG_OK, GR, bg)
        curses.init_pair(C_LOG_ERR, RE, bg)
        curses.init_pair(C_LOG_CMD, MGY, bg)
        curses.init_pair(C_LOG_INFO, LGY, bg)
        curses.init_pair(C_INPUT, A, BLK)

    except Exception:

        Y, C, G, R, W, K = (
            curses.COLOR_YELLOW,
            curses.COLOR_CYAN,
            curses.COLOR_GREEN,
            curses.COLOR_RED,
            curses.COLOR_WHITE,
            curses.COLOR_BLACK,
        )
        curses.init_pair(C_HDR, K, Y)
        curses.init_pair(C_HINT, W, K)
        curses.init_pair(C_BORDER, W, bg)
        curses.init_pair(C_SECTION, Y, bg)
        curses.init_pair(C_DIM, W, bg)
        curses.init_pair(C_LIVE, G, bg)
        curses.init_pair(C_PEND_ADD, C, bg)
        curses.init_pair(C_PEND_DEL, R, bg)
        curses.init_pair(C_CURSOR, K, C)
        curses.init_pair(C_CUR_LIVE, K, G)
        curses.init_pair(C_CUR_PADD, K, C)
        curses.init_pair(C_CUR_PDEL, K, R)
        curses.init_pair(C_STAT_LIV, W, bg)
        curses.init_pair(C_STAT_ADD, C, bg)
        curses.init_pair(C_STAT_DEL, R, bg)
        curses.init_pair(C_LOG_OK, G, bg)
        curses.init_pair(C_LOG_ERR, R, bg)
        curses.init_pair(C_LOG_CMD, W, bg)
        curses.init_pair(C_LOG_INFO, W, bg)
        curses.init_pair(C_INPUT, Y, K)
