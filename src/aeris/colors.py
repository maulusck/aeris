"""
AERIS · color-pair constants and initialisation
"""
import curses

# ── Layout chrome ─────────────────────────
C_HDR     = 1   # amber title bar
C_HINT    = 2   # dark key-hint / status bar
C_BORDER  = 3   # dark-grey box lines
C_SECTION = 4   # amber section labels
C_DIM     = 5   # mid-grey inactive text

# ── Entry row states ──────────────────────
C_LIVE     = 6   # green   – IP currently applied
C_PEND_ADD = 7   # cyan    – selected, not yet applied
C_PEND_DEL = 8   # red     – live but deselected
C_CURSOR   = 9   # black/cyan bg  – cursor on neutral row
C_CUR_LIVE = 10  # black/green bg – cursor on live row
C_CUR_PADD = 11  # black/cyan bg  – cursor on pending-add
C_CUR_PDEL = 12  # black/red bg   – cursor on pending-del

# ── Status panel ──────────────────────────
C_STAT_LIV = 13  # live IPs   (green dim)
C_STAT_ADD = 14  # pending add (cyan)
C_STAT_DEL = 15  # pending remove (red)

# ── Log panel ─────────────────────────────
C_LOG_OK   = 16  # green
C_LOG_ERR  = 17  # red
C_LOG_CMD  = 18  # mid-grey
C_LOG_INFO = 19  # light-grey

# ── Input box ─────────────────────────────
C_INPUT = 20     # amber on near-black


def init_colors() -> None:
    """Initialise all colour pairs; falls back to 8-colour terminals."""
    curses.start_color()
    curses.use_default_colors()
    bg = -1

    try:
        A   = 214   # amber
        CY  = 51    # cyan
        GR  = 82    # green
        RE  = 196   # red
        BLK = 16    # true black
        DGY = 236   # dark grey
        MGY = 242   # mid grey
        LGY = 248   # light grey

        curses.init_pair(C_HDR,      BLK, A)
        curses.init_pair(C_HINT,     MGY, DGY)
        curses.init_pair(C_BORDER,   DGY, bg)
        curses.init_pair(C_SECTION,  A,   bg)
        curses.init_pair(C_DIM,      MGY, bg)
        curses.init_pair(C_LIVE,     GR,  bg)
        curses.init_pair(C_PEND_ADD, CY,  bg)
        curses.init_pair(C_PEND_DEL, RE,  bg)
        curses.init_pair(C_CURSOR,   BLK, CY)
        curses.init_pair(C_CUR_LIVE, BLK, GR)
        curses.init_pair(C_CUR_PADD, BLK, CY)
        curses.init_pair(C_CUR_PDEL, BLK, RE)
        curses.init_pair(C_STAT_LIV, MGY, bg)
        curses.init_pair(C_STAT_ADD, CY,  bg)
        curses.init_pair(C_STAT_DEL, RE,  bg)
        curses.init_pair(C_LOG_OK,   GR,  bg)
        curses.init_pair(C_LOG_ERR,  RE,  bg)
        curses.init_pair(C_LOG_CMD,  MGY, bg)
        curses.init_pair(C_LOG_INFO, LGY, bg)
        curses.init_pair(C_INPUT,    A,   BLK)

    except Exception:
        # 8-colour fallback
        Y, C, G, R, W, K = (
            curses.COLOR_YELLOW, curses.COLOR_CYAN,  curses.COLOR_GREEN,
            curses.COLOR_RED,    curses.COLOR_WHITE, curses.COLOR_BLACK,
        )
        curses.init_pair(C_HDR,      K, Y)
        curses.init_pair(C_HINT,     W, K)
        curses.init_pair(C_BORDER,   W, bg)
        curses.init_pair(C_SECTION,  Y, bg)
        curses.init_pair(C_DIM,      W, bg)
        curses.init_pair(C_LIVE,     G, bg)
        curses.init_pair(C_PEND_ADD, C, bg)
        curses.init_pair(C_PEND_DEL, R, bg)
        curses.init_pair(C_CURSOR,   K, C)
        curses.init_pair(C_CUR_LIVE, K, G)
        curses.init_pair(C_CUR_PADD, K, C)
        curses.init_pair(C_CUR_PDEL, K, R)
        curses.init_pair(C_STAT_LIV, W, bg)
        curses.init_pair(C_STAT_ADD, C, bg)
        curses.init_pair(C_STAT_DEL, R, bg)
        curses.init_pair(C_LOG_OK,   G, bg)
        curses.init_pair(C_LOG_ERR,  R, bg)
        curses.init_pair(C_LOG_CMD,  W, bg)
        curses.init_pair(C_LOG_INFO, W, bg)
        curses.init_pair(C_INPUT,    Y, K)
