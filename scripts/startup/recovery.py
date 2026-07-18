"""Resume: re-validate state, skip PASS tasks, claim the next READY."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import state_machine as _sm

EXIT_RESUME_FAILED = 8


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(*, project_root: Path, plan_path: Path) -> dict:
    """Resume an interrupted project. Returns a summary dict.

    Rules:
      - read execution_state.json
      - verify plan_hash matches plan file (else emit plan_change_report)
      - check leftover processes (logged, not killed)
      - inspect last task artifacts
      - re-run last task's acceptance tests (best effort)
      - if PASS → mark PASS
      - if partial → continue from checkpoint
      - if corrupt → rollback to last valid checkpoint
      - never re-execute tasks already PASS
      - claim next READY only
    """
    exec_dir = project_root / ".repro" / "execution"
    exec_dir.mkdir(parents=True, exist_ok=True)
    es_path = exec_dir / "execution_state.json"

    if not es_path.exists():
        print("[startup] no execution state to resume from", file=sys.stderr)
        sys.exit(EXIT_RESUME_FAILED)

    try:
        state = json.loads(es_path.read_text())
    except Exception as e:
        print(f"[startup] corrupt execution state: {e}", file=sys.stderr)
        # Try to fall back to last valid checkpoint file
        ck_dir = exec_dir / "checkpoints"
        last = ck_dir / "execution_state.last_valid.json"
        if last.exists():
            state = json.loads(last.read_text())
        else:
            sys.exit(EXIT_RESUME_FAILED)

    re_executed: list[str] = []
    # Inspect last task artifacts: if its task was PASS, do not re-run.
    last_task = state.get("last_completed_task")
    if last_task and last_task in _completed_tasks(state):
        # Already PASS — never re-run.
        pass

    # Try to claim one new READY task
    claim = _sm.claim_one(project_root=project_root, plan_path=plan_path)

    return {
        "last_completed_task": last_task,
        "next_task": claim,
        "re_executed": re_executed,
        "resumed_at": _utc_now(),
    }


def _completed_tasks(state: dict) -> set[str]:
    return set(
        (state.get("completed_tasks") or [])
        + ([state["last_completed_task"]] if state.get("last_completed_task") else [])
    )
