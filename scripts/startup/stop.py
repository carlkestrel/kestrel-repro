"""Stop: graceful shutdown that saves state and clears the lock."""
from __future__ import annotations

import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import lock as _lock

EXIT_INTERNAL = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(*, project_root: Path, plan_path: Path | None = None) -> dict:
    """Save state, send graceful stop to managed children, clear lock.

    MUST NOT touch other projects or user processes. The only signal it
    may send is SIGTERM, and only to children that this same project
    recorded as managed.
    """
    exec_dir = project_root / ".repro" / "execution"
    exec_dir.mkdir(parents=True, exist_ok=True)
    es_path = exec_dir / "execution_state.json"

    state = {}
    if es_path.exists():
        try:
            state = json.loads(es_path.read_text())
        except Exception:
            state = {}

    # Snapshot last valid state before mutating
    ck = exec_dir / "checkpoints" / "execution_state.last_valid.json"
    ck.parent.mkdir(parents=True, exist_ok=True)
    if state:
        ck.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Save training checkpoint placeholder (start never auto-trains;
    # this only saves the execution_state checkpoint)
    state["stopped_at"] = _utc_now()
    state["interrupted"] = False
    state["current_task"] = None
    state["stop_reason"] = "user_requested"
    es_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Graceful stop to managed children (only those we recorded).
    for pid in state.get("managed_pids", []) or []:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except (OSError, ValueError, ProcessLookupError):
            pass

    # Clear the project lock
    lock_path = project_root / ".repro" / "run.lock"
    _lock.release(lock_path)

    return {
        "stopped_at": state["stopped_at"],
        "lock_cleared": True,
        "state_path": str(es_path),
    }
