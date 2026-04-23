"""
AERIS · persistence
Handles profile files in ~/.config/aeris/profiles/ and
the state.json that tracks the last active profile.

Errors are no longer silently swallowed: IO failures raise AerisError
so callers can log them properly instead of operating on stale data.

Ownership
---------
Every file and directory created here is immediately chowned to the real
(non-root) user via config.chown_to_real_user().  This makes ``sudo aeris``
and normal ``aeris`` (with sudoers rule) behave identically from the user's
perspective — all config files are always theirs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from aeris.config import DEFAULT_IPS, PROFILES_DIR, STATE_FILE, chown_to_real_user

# ── Custom exception ─────────────────────────────────────────────────────────


class AerisError(RuntimeError):
    """Raised when a persistence operation cannot be completed."""


# ── Internal helpers ─────────────────────────────────────────────────────────


def _ensure_dir() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    chown_to_real_user(PROFILES_DIR)


def _profile_path(name: str) -> Path:
    return PROFILES_DIR / f"{name}.json"


def _read_profile_file(path: Path) -> List[dict]:
    """
    Return list of {name, ip} dicts from a profile JSON.
    Returns [] on missing file; raises AerisError on corrupt JSON.
    """
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        out: List[dict] = []
        for r in raw.get("ips", []):
            if isinstance(r, dict) and "ip" in r:
                out.append({"name": r.get("name", r["ip"]), "ip": r["ip"]})
        return out
    except (json.JSONDecodeError, OSError) as exc:
        raise AerisError(f"Cannot read profile '{path.stem}': {exc}") from exc


def _write_profile_file(path: Path, entries: List[dict]) -> None:
    data = [{"name": e["name"], "ip": e["ip"]} for e in entries]
    try:
        path.write_text(
            json.dumps({"ips": data}, indent=2),
            encoding="utf-8",
        )
        chown_to_real_user(path)
    except OSError as exc:
        raise AerisError(f"Cannot write profile '{path.stem}': {exc}") from exc


# ── Public API ────────────────────────────────────────────────────────────────


def ensure_default() -> None:
    """Create default.json from DEFAULT_IPS if it does not exist."""
    _ensure_dir()
    p = _profile_path("default")
    if not p.exists():
        _write_profile_file(p, DEFAULT_IPS)


def list_profiles() -> List[str]:
    """Return sorted list of profile names (without .json extension)."""
    _ensure_dir()
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def profile_exists(name: str) -> bool:
    return _profile_path(name).exists()


def load_profile(name: str) -> List[dict]:
    """Load entries for *name*. Falls back to [] if missing; raises on corrupt."""
    ensure_default()
    return _read_profile_file(_profile_path(name))


def save_profile(name: str, entries: List[dict]) -> None:
    _ensure_dir()
    _write_profile_file(_profile_path(name), entries)


def create_profile(name: str) -> bool:
    """
    Create an empty profile.
    Returns False if a profile with that name already exists.
    """
    if profile_exists(name):
        return False
    _ensure_dir()
    _write_profile_file(_profile_path(name), [])
    return True


def rename_profile(old: str, new: str) -> bool:
    """
    Rename *old* → *new*.
    Returns False if *new* already exists or *old* does not.
    """
    if not profile_exists(old) or profile_exists(new):
        return False
    _profile_path(old).rename(_profile_path(new))
    return True


def delete_profile(name: str) -> bool:
    """Delete profile file. Returns False if it did not exist."""
    p = _profile_path(name)
    if not p.exists():
        return False
    p.unlink()
    return True


def duplicate_profile(src: str, dst: str) -> bool:
    """
    Copy *src* into a new profile *dst*.
    Returns False if *dst* already exists or *src* does not.
    """
    if not profile_exists(src) or profile_exists(dst):
        return False
    entries = load_profile(src)
    _write_profile_file(_profile_path(dst), entries)
    return True


def load_state() -> tuple:
    """Return (active_profile, con_id) — both default if missing."""
    from aeris.config import CON_ID as _DEFAULT_CON

    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return raw.get("active_profile", "default"), raw.get("con_id", _DEFAULT_CON)
    except (FileNotFoundError, json.JSONDecodeError):
        return "default", _DEFAULT_CON
    except OSError as exc:
        raise AerisError(f"Cannot read state file: {exc}") from exc


def save_state(active_profile: str, con_id: str) -> None:
    from aeris.config import CON_ID as _DEFAULT_CON

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        chown_to_real_user(STATE_FILE.parent)
        STATE_FILE.write_text(
            json.dumps({"active_profile": active_profile, "con_id": con_id}, indent=2),
            encoding="utf-8",
        )
        chown_to_real_user(STATE_FILE)
    except OSError as exc:
        raise AerisError(f"Cannot write state file: {exc}") from exc
