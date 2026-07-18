"""The BOOTSTRAP → … → EXECUTE_NEXT startup state machine."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import lock as _lock
from . import plan_validate as _plan
from . import doctor as _doctor
from . import config as _config

# R3-0: import from canonical core
try:
    from scripts.core.state_store import (
        StateStore as _CanonicalStateStore,
        compute_authorization_bound_hash as _compute_auth_hash,
        CURRENT_CANONICALIZATION_VERSION,
    )
except ImportError:
    _CanonicalStateStore = None  # type: ignore
    _compute_auth_hash = None  # type: ignore
    CURRENT_CANONICALIZATION_VERSION = "1"

EXIT_TASK_FAILED = 6
EXIT_TASK_BLOCKED = 7
EXIT_RESUME_FAILED = 8
EXIT_INTERNAL = 10
EXIT_INVALID_PLAN = 5

STAGES = (
    "BOOTSTRAP",
    "DISCOVER",
    "PREFLIGHT",
    "STATE_CHECK",
    "LOCK",
    "PLAN_VALIDATE",
    "READY",
    "EXECUTE_NEXT",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plugin_version(plugin_root: Path) -> str:
    """Read plugin.json for the version (no hardcoding)."""
    p = plugin_root / ".cursor-plugin" / "plugin.json"
    try:
        return json.loads(p.read_text()).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def _read_state(exec_dir: Path) -> dict | None:
    """Return the execution_state dict, or None if missing.

    Raises SystemExit(8) if the file exists but cannot be parsed as JSON —
    a corrupt state file is a resume-failure situation, not a no-state one.
    """
    p = exec_dir / "execution_state.json"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        # Empty file: treat as missing-state (fresh project) rather than corrupt
        return None
    try:
        return json.loads(text)
    except Exception as e:
        # Archive the corrupt state for forensics, then signal the caller.
        archive = exec_dir / "checkpoints" / f"execution_state.corrupt.{int(__import__('time').time())}.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        try:
            archive.write_text(text)
        except Exception:
            pass
        print(f"[startup] corrupt execution_state.json: {e}; "
              f"archived to {archive.name}", file=sys.stderr)
        sys.exit(EXIT_RESUME_FAILED)


def _write_state(exec_dir: Path, state: dict) -> None:
    p = exec_dir / "execution_state.json"
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(p)


def _git_commit(project_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(project_root),
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unknown"


def _git_dirty(project_root: Path) -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(project_root),
            stderr=subprocess.DEVNULL, text=True)
        return bool(out.strip())
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────
# Stage implementations
# ──────────────────────────────────────────────────────────────────────


def bootstrap(*, plugin_root: Path, project_root: Path,
              mode: str) -> dict:
    return {
        "plugin_version": _plugin_version(plugin_root),
        "plugin_root": str(plugin_root),
        "project_root": str(project_root),
        "mode": mode,
        "cwd": os.getcwd(),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "started_at": _utc_now(),
    }


def discover(*, project_root: Path, plan_path: Path) -> dict:
    primary = project_root / "primary"
    refs = project_root / "references"
    return {
        "primary_exists": primary.exists(),
        "references_exists": refs.exists(),
        "git_repo": (project_root / ".git").exists(),
        "git_commit": _git_commit(project_root),
        "git_dirty": _git_dirty(project_root),
        "plan_exists": plan_path.exists(),
        "plan_size_bytes": plan_path.stat().st_size if plan_path.exists() else 0,
    }


def preflight(*, project_root: Path, plan_path: Path,
              expected_cuda: str | None) -> dict:
    report = _doctor.run(project_root=project_root, plan_path=plan_path,
                         expected_cuda=expected_cuda)
    return {
        "overall": report["overall"],
        "summary": report["summary"],
        "report": report,
    }


def state_check(*, project_root: Path) -> dict:
    """Distinguish new-task vs resume, surface leftover state."""
    state_path = project_root / ".repro" / "execution" / "execution_state.json"
    res = {
        "is_new": True,
        "leftover_state": False,
        "corrupt": False,
        "interrupted": False,
    }
    if not state_path.exists():
        return res
    res["leftover_state"] = True
    res["is_new"] = False
    try:
        s = json.loads(state_path.read_text())
        if s.get("interrupted"):
            res["interrupted"] = True
        res["last_completed_task"] = s.get("last_completed_task")
    except Exception:
        res["corrupt"] = True
    return res


def lock_acquire(*, project_root: Path, command: str,
                 plan_hash: str, plugin_version: str) -> dict:
    lock_path = project_root / ".repro" / "run.lock"
    return _lock.acquire(
        lock_path, command=command, plan_hash=plan_hash,
        project_root=str(project_root), plugin_version=plugin_version,
    )


def plan_validate(plan_path: Path) -> str:
    return _plan.validate(plan_path)


def ready_summary(*, project_root: Path, plan_path: Path, mode: str,
                  plugin_version: str, doctor: dict,
                  state_check_info: dict, plan_hash: str,
                  next_task: dict | None, last_completed_task: str | None,
                  dry_run: bool) -> dict:
    return {
        "project_root": str(project_root),
        "plan_path": str(plan_path),
        "mode": mode,
        "plugin_version": plugin_version,
        "git_commit": _git_commit(project_root),
        "git_dirty": _git_dirty(project_root),
        "doctor_overall": doctor["overall"],
        "doctor_summary": doctor["summary"],
        "is_new": state_check_info.get("is_new", True),
        "last_completed_task": last_completed_task,
        "next_task": next_task,
        "plan_hash": plan_hash,
        "dry_run": dry_run,
    }


# ──────────────────────────────────────────────────────────────────────
# Claim ONE atomic task
# ──────────────────────────────────────────────────────────────────────


def claim_one(*, project_root: Path, plan_path: Path,
              dry_run: bool = False) -> dict:
    """Claim ONE ready atomic task; persist state on completion.

    The state machine:
      - Read execution_state.json (corrupt → exit 8)
      - Verify plan_hash matches plan file (changed → exit 8)
      - Read task_graph.yaml and pick the first task with status == READY
      - Persist: current_task, started_at, claimed_at
      - DO NOT claim the next task automatically
    """
    exec_dir = project_root / ".repro" / "execution"
    exec_dir.mkdir(parents=True, exist_ok=True)
    state = _read_state(exec_dir)

    current_hash = ""
    try:
        current_hash = _plan.validate(plan_path)
    except SystemExit as e:
        # If the plan can't even be validated, we can't claim anything.
        raise

    if state is not None:
        existing_hash = state.get("plan_hash")
        if existing_hash and existing_hash != current_hash:
            report = exec_dir / "plan_change_report.md"
            report.write_text(
                f"# Plan Hash Changed\n\n"
                f"- previous: `{existing_hash}`\n"
                f"- current : `{current_hash}`\n"
                f"- action  : refusing to resume. Use `reproctl resume` after "
                f"`git checkout` or re-plan.\n"
            )
            print(f"[startup] plan hash changed; wrote {report}",
                  file=sys.stderr)
            sys.exit(EXIT_RESUME_FAILED)

    # Task graph
    tg_path = exec_dir / "task_graph.yaml"
    task_graph = _ensure_task_graph(plan_path, tg_path)

    # plan_hash is recorded either at top-level or under metadata
    plan_hash = task_graph.get("plan_hash")
    if not plan_hash and isinstance(task_graph.get("metadata"), dict):
        plan_hash = task_graph["metadata"].get("plan_hash")

    ready = [t for t in task_graph["tasks"] if t.get("status") == "READY"]
    if not ready:
        return {"id": None, "status": "NONE",
                "message": "no READY tasks in task graph"}

    task = ready[0]

    if dry_run:
        return {"id": task["id"], "status": "WOULD_CLAIM",
                "dry_run": True,
                "message": "dry-run; no state mutated"}

    # Persist claim
    if state is None:
        state = {
            "plan_hash": plan_hash or current_hash,
            "plan_path": str(plan_path),
            "project_root": str(project_root),
            "current_task": task["id"],
            "last_completed_task": None,
            "completed_tasks": [],
            "started_at": _utc_now(),
            "claimed_at": _utc_now(),
            "interrupted": False,
        }
    else:
        state["current_task"] = task["id"]
        state["claimed_at"] = _utc_now()
        state["interrupted"] = False
        state["plan_path"] = str(plan_path)
        state["project_root"] = str(project_root)
    _write_state(exec_dir, state)

    # Append to task_journal.jsonl
    journal = exec_dir / "task_journal.jsonl"
    with journal.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "task": task["id"], "event": "CLAIMED",
            "at": _utc_now(),
        }) + "\n")

    return {"id": task["id"], "status": "CLAIMED",
            "task": task, "state": state}


def _ensure_task_graph(plan_path: Path, tg_path: Path) -> dict:
    """Materialize a minimal task graph from the plan frontmatter.

    If ``tg_path`` already exists, load it (so the user can hand-edit it).
    Otherwise, derive tasks from the plan and write them out.
    """
    if tg_path.exists():
        try:
            import yaml  # type: ignore
            return yaml.safe_load(tg_path.read_text())
        except Exception:
            pass
    import yaml  # type: ignore
    fm_text = plan_path.read_text().split("---", 2)
    if len(fm_text) >= 3:
        fm = yaml.safe_load(fm_text[1]) or {}
    else:
        fm = {}
    tasks = fm.get("tasks") or _default_tasks(plan_path)
    # Annotate statuses: READY for the first, BLOCKED for the rest.
    annotated = []
    for i, t in enumerate(tasks):
        t2 = dict(t)
        t2.setdefault("status", "READY" if i == 0 else "BLOCKED")
        annotated.append(t2)
    plan_hash = _plan.validate(plan_path)
    graph = {
        "metadata": {"plan_hash": plan_hash,
                     "total_tasks": len(annotated),
                     "generated_at": _utc_now()},
        "tasks": annotated,
    }
    tg_path.write_text(yaml.safe_dump(graph, sort_keys=False))
    return graph


def _default_tasks(plan_path: Path) -> list[dict]:
    return [
        {"id": "PLAN_REVIEW", "title": "Review the plan with the user",
         "status": "READY", "depends_on": [],
         "acceptance": ["user acknowledges plan"]},
        {"id": "FIRST_ATOMIC_TASK", "title": "Execute the first atomic task",
         "status": "BLOCKED", "depends_on": ["PLAN_REVIEW"],
         "acceptance": ["task completes and is recorded"]},
    ]


# ──────────────────────────────────────────────────────────────────────
# Bootstrap the .repro/ tree for a project
# ──────────────────────────────────────────────────────────────────────


def bootstrap_exec_layout(project_root: Path) -> dict:
    """Create <project>/.repro/{startup,execution,performance,repair,reports}.

    Idempotent. Returns the list of paths created.
    """
    repro = project_root / ".repro"
    paths = {
        "startup": repro / "startup",
        "execution": repro / "execution",
        "performance": repro / "performance",
        "repair": repro / "repair",
        "reports": repro / "reports",
    }
    for k, p in paths.items():
        p.mkdir(parents=True, exist_ok=True)
    # Sub-directories required by spec
    (paths["execution"] / "checkpoints").mkdir(exist_ok=True)
    (paths["execution"] / "heartbeats").mkdir(exist_ok=True)
    (paths["execution"] / "evidence").mkdir(exist_ok=True)
    return paths
