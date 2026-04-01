"""
AERIS · persistence – load/save custom IP entries
"""
import json
from aeris.config import STATE_FILE


def load_custom() -> list[dict]:
    if not STATE_FILE.exists():
        return []
    try:
        raw  = json.loads(STATE_FILE.read_text())
        recs = raw.get("custom_ips", [])
        out  = []
        for r in recs:
            if isinstance(r, str):
                out.append({"name": r, "ip": r})
            elif isinstance(r, dict) and "ip" in r:
                out.append({"name": r.get("name", r["ip"]), "ip": r["ip"]})
        return out
    except Exception:
        return []


def save_custom(entries: list[dict]) -> None:
    data = [{"name": e["name"], "ip": e["ip"]}
            for e in entries if e["type"] == "custom"]
    try:
        STATE_FILE.write_text(json.dumps({"custom_ips": data}, indent=2))
    except Exception:
        pass
