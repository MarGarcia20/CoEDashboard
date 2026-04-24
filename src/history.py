"""
Archive a JSON snapshot of metrics per day.
One file per calendar day in output/history/YYYY-MM-DD.json.
Re-runs on the same day overwrite — we keep the latest snapshot for each date.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

HISTORY_DIR = Path(__file__).parent.parent / "output" / "history"


def save_snapshot(metrics: dict, today: date, verbose: bool = False) -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / f"{today.isoformat()}.json"

    snapshot = {
        "date": today.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "metrics": _clean(metrics),
    }

    path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")

    if verbose:
        print(f"  Snapshot archived → {path.name}")

    return path


def _clean(d: dict) -> dict:
    """Strip values that don't serialize cleanly (keeps things portable)."""
    out = {}
    for k, v in d.items():
        try:
            json.dumps(v, default=str)
            out[k] = v
        except (TypeError, ValueError):
            continue
    return out


def load_history() -> list[dict]:
    """Load all historical snapshots, newest first. For future trend features."""
    if not HISTORY_DIR.exists():
        return []
    snapshots = []
    for p in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        try:
            snapshots.append(json.loads(p.read_text()))
        except (ValueError, OSError):
            continue
    return snapshots
