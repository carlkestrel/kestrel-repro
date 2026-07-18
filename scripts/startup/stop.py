"""Stop: graceful shutdown that saves state and clears the lock."""
from __future__ import annotations

import json
import os
import signal
import time as _time
from datetime import datetime, timezone
from pathlib import Path

from . import lock as _lock

EXIT_INTERNAL = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(*, project_root: Path, plan_path: Path | None = None,
          force: bool = False) -> dict:
    """Save state, send graceful stop to managed children, clear lock.

    R3F-8: ``force=True`` sends SIGKILL after SIGTERM for unresponsive processes.
    Always verifies the lock was actually cleared after release.
    """
    exec_dir = project_root / ".repro" / "execution"
    exec_dir.mkdir(parents=True, exist_ok=True)
    es_path = exec_dir / "execution_state.json"

    state: dict = {}
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

    state["stopped_at"] = _utc_now()
    state["interrupted"] = False
    state["current_task"] = None
    state["stop_reason"] = "user_requested"
    state["force_stop"] = force
    es_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Graceful stop to managed children
    for pid in state.get("managed_pids", []) or []:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except (OSError, ValueError, ProcessLookupError):
            pass

    if force:
        # R3F-8: after SIGTERM, give processes 2s to clean up, then SIGKILL
        _time.sleep(2)
        for pid in state.get("managed_pids", []) or []:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except (OSError, ValueError, ProcessLookupError):
                pass

    # Clear the project lock
    lock_path = project_root / ".repro" / "run.lock"
    _lock.release(lock_path)

    # R3F-8: verify lock was actually cleared
    lock_cleared = not lock_path.exists()

    return {
        "stopped_at": state["stopped_at"],
        "lock_cleared": lock_cleared,
        "state_path": str(es_path),
        "force_stop": force,
        "managed_pids_stopped": len(state.get("managed_pids") or []),
    }
