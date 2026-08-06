"""Watermark storage — what makes the poll loop a trigger instead of a re-run.

Lead Scout remembers which leads it has already worked, so polling every five
minutes doesn't mean pitching the same person every five minutes. The state
lives in a small JSON file next to the repo (gitignored).
"""

import json
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / ".state"
STATE_FILE = STATE_DIR / "lead_scout.json"

def _empty() -> dict:
    # Built fresh every call — a shared default would let mark_seen() append
    # into the module-level list and outlive a reset().
    return {"seen_ids": [], "last_poll": None}


def load() -> dict:
    if not STATE_FILE.exists():
        return _empty()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    state = _empty()
    state.update(data)
    state["seen_ids"] = list(state.get("seen_ids") or [])
    return state


def save(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def already_seen(lead_id: str) -> bool:
    return lead_id in load()["seen_ids"]


def mark_seen(lead_id: str) -> None:
    state = load()
    if lead_id not in state["seen_ids"]:
        state["seen_ids"].append(lead_id)
        # Keep the file from growing forever; recent history is all we need.
        state["seen_ids"] = state["seen_ids"][-500:]
    save(state)


def reset() -> None:
    """Forget everything — handy right before filming a demo."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
