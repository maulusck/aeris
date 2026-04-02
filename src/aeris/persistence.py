"""
AERIS · persistence
Handles profile files in ~/.config/aeris/profiles/ and
the state.json that tracks the last active profile.
"""

import json
from pathlib import Path

from aeris.config import DEFAULT_IPS, PROFILES_DIR, STATE_FILE


def _ensure_dir() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _profile_path(name: str) -> Path:
    return PROFILES_DIR / f"{name}.json"


def _read_profile_file(path: Path) -> list[dict]:
    """Return list of {name, ip} dicts from a profile JSON, or [] on error."""
    try:
        raw = json.loads(path.read_text())
        out = []
        for r in raw.get("ips", []):
            if isinstance(r, dict) and "ip" in r:
                out.append({"name": r.get("name", r["ip"]), "ip": r["ip"]})
        return out
    except Exception:
        return []


def ensure_default() -> None:
    """Create default.json from DEFAULT_IPS if it does not exist."""
    _ensure_dir()
    p = _profile_path("default")
    if not p.exists():
        _write_profile_file(p, DEFAULT_IPS)


def _write_profile_file(path: Path, entries: list[dict]) -> None:
    data = [{"name": e["name"], "ip": e["ip"]} for e in entries]
    try:
        path.write_text(json.dumps({"ips": data}, indent=2))
    except Exception:
        pass


def list_profiles() -> list[str]:
    """Return sorted list of profile names (without .json extension)."""
    _ensure_dir()
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def profile_exists(name: str) -> bool:
    return _profile_path(name).exists()


def load_profile(name: str) -> list[dict]:
    """Load entries for *name*. Falls back to [] if missing/corrupt."""
    ensure_default()
    return _read_profile_file(_profile_path(name))


def save_profile(name: str, entries: list[dict]) -> None:
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


def load_state() -> str:
    """Return the last active profile name, defaulting to 'default'."""
    try:
        raw = json.loads(STATE_FILE.read_text())
        return raw.get("active_profile", "default")
    except Exception:
        return "default"


def save_state(active_profile: str) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"active_profile": active_profile}, indent=2))
    except Exception:
        pass
