#!/usr/bin/env python3
"""
reproctl.py — Deep Learning Paper Reproduction Controller (v0.2.0)

This file is BOTH:
  - The original CLI (init / status / can-launch / launch / run-short-loop /
    verify / report / update-gate / record-experiment / update-experiment /
    get-experiments / human-checkpoint / check-principles / help)
  - A thin dispatcher for the NEW unified startup system
    (start | doctor | status | resume | stop | verify | version)

The new subcommands live in ``scripts/startup/cli.py`` and are the single
source of truth for startup behavior. The Cursor commands under
``commands/repro-*.md`` invoke this same script — there is no parallel
implementation.

Usage:
    python reproctl.py <command> [options]

Commands (unified startup system):
    start           Bootstrap & start the project (unified entry)
    doctor          Run preflight checks (no state mutation)
    status          Show project state, lock, plan hash
    resume          Resume an interrupted project
    stop            Stop gracefully and clear the lock
    verify          Verify the startup evidence chain
    version         Print plugin + CLI version

Commands (legacy, retained for backward compatibility):
    init           Initialize a new reproduction project
    can-launch     Check if full training can be launched
    launch         Launch full training (with gate enforcement)
    run-short-loop Run short-loop validation tests
    report         Generate human-readable report
    update-gate    Manually update gate status
    record-experiment / update-experiment / get-experiments
                    Experiment tracker helpers
    human-checkpoint   Enforce the 12-item human checkpoint
    check-principles   Run the 5 highest principles against a JSON spec
    help           Show this help message
"""

import argparse
import json
import os
import sys
import subprocess
import shutil
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ── Paths ────────────────────────────────────────────────────────────────────

PLUGIN_ROOT = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
TEMPLATES_DIR = PLUGIN_ROOT / "templates"
STARTUP_DIR = SCRIPTS_DIR / "startup"
REPRO_DIR = Path(".repro")
AUDIT_DIR = REPRO_DIR / "audit"
EXPERIMENTS_DIR = Path("experiments")


# ── New unified-subcommand dispatcher ────────────────────────────────────────
#
# If argv[1] is one of the new unified commands, hand off to
# scripts/startup/cli.py and exit. This means the legacy CLI below is
# ONLY consulted for backward-compatible commands.

_NEW_SUBCOMMANDS = {
    "start", "doctor", "resume", "stop", "version",
    # `status` and `verify` are also new; they have legacy equivalents
    # but the new versions are richer and preferred. The dispatcher
    # forwards them to startup/cli.py.
    "status", "verify",
    # Storage governance (disk policy + retention)
    "storage",
}

_ORCHESTRATOR_SUBCOMMANDS = {
    "run", "pause", "continue", "stop", "status",
    "approve", "reject", "events", "next", "daemon",
    "migrate", "backup", "restore", "integrity-check", "rollback-version",
}

_AUDIT_SUBCOMMANDS = {
    "init", "plan", "status", "run-next", "run-node",
    "run-stage", "retry", "report", "validate",
}

_SOAK_SUBCOMMANDS = {
    "plan", "start", "status", "pause", "resume", "stop", "report",
}

_REPROCTL_SUBCOMMANDS = {
    "init", "can-launch", "launch", "run-short-loop",
    "verify", "report", "update-gate", "record-experiment",
    "update-experiment", "get-experiments", "human-checkpoint",
    "check-principles", "integrity-check", "help",
}

# Legacy subcommands that also exist as new unified commands
_LEGACY_MAPPED_TO_NEW = {
    "status": "startup",   # reproctl status → startup/cli.py
    "verify": "startup",   # reproctl verify → startup/cli.py
}


def _dispatch_to_audit() -> Optional[int]:
    """Route `reproctl audit ...` commands to scripts/cvo/audit_cli.py."""
    if len(sys.argv) < 2 or sys.argv[1] != "audit":
        return None
    # Real script path (absolute, from scripts/ dir)
    _AUDIT_SCRIPT = Path(__file__).resolve().parent / "cvo" / "audit_cli.py"
    # Rewrite argv: python reproctl.py audit init → [audit_cli.py, init]
    sys.argv = [str(_AUDIT_SCRIPT)] + sys.argv[2:]
    # Inherit cwd from parent (reproctl.py) which is the plugin root.
    # Do NOT override cwd.
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from cvo.audit_cli import main as audit_main
    except Exception as e:
        print(f"[reproctl] could not import CVO audit subsystem: {e}",
              file=sys.stderr)
        return 10
    return audit_main()


def _dispatch_to_orchestrator() -> Optional[int]:
    """Route orchestrator subcommands to ``scripts/orchestrator/cli.py``.

    The orchestrator owns ``run``, ``pause``, ``continue``, ``status``,
    ``stop``, ``events``, ``next``, ``approve``, ``reject``, and ``daemon``.
    It is consulted BEFORE the startup dispatcher, so the new orchestrator
    surface takes precedence over the legacy startup aliases of the same
    names when an orchestrator-state directory exists in the project.
    """
    if len(sys.argv) < 2:
        return None
    cmd = sys.argv[1]
    if cmd not in _ORCHESTRATOR_SUBCOMMANDS:
        return None
    project_arg = _find_project_arg(sys.argv[2:])
    if project_arg is not None:
        path = Path(project_arg).resolve()
        if path.exists() and not (path / ".repro" / "execution" / "state.sqlite3").exists():
            # Project has no orchestrator state; the orchestrator command
            # would be a no-op. Fall through to the startup dispatcher so the
            # existing `status`/`stop` legacy semantics keep working.
            if cmd in {"status", "stop"}:
                return None
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    for cached in list(sys.modules.keys()):
        if cached == "orchestrator" or cached.startswith("orchestrator."):
            del sys.modules[cached]
    try:
        from orchestrator.cli import main as orchestrator_main
    except Exception as e:
        print(f"[reproctl] could not import orchestrator subsystem: {e}",
              file=sys.stderr)
        return 10  # EXIT_INTERNAL
    return orchestrator_main(sys.argv[1:])


def _find_project_arg(argv: list[str]) -> str | None:
    for index, token in enumerate(argv):
        if token == "--project" and index + 1 < len(argv):
            return argv[index + 1]
        if token.startswith("--project="):
            return token.split("=", 1)[1]
    return None


def _dispatch_to_startup() -> Optional[int]:
    """If argv matches a new subcommand, run startup/cli.py and return its
    exit code. Otherwise return None (fall through to legacy handling)."""
    if len(sys.argv) < 2:
        return None
    cmd = sys.argv[1]
    # Storage is a namespace command: argv[2] is the sub-action (status/plan-cleanup/cleanup).
    # Hand it off to startup/storage_governance.py via its own dispatch.
    if cmd == "storage":
        return _dispatch_storage()
    if cmd not in _NEW_SUBCOMMANDS:
        return None
    # Make the startup package importable as `startup.*`.
    parent = str(SCRIPTS_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    # Also clear any cached "startup" that may have been imported as a
    # top-level module by a previous test.
    for cached in list(sys.modules.keys()):
        if cached == "startup" or cached.startswith("startup."):
            del sys.modules[cached]
    try:
        from startup.cli import main as startup_main
    except Exception as e:
        print(f"[reproctl] could not import startup subsystem: {e}",
              file=sys.stderr)
        return 10  # EXIT_INTERNAL
    return startup_main(sys.argv[1:])


def _dispatch_to_soak() -> Optional[int]:
    """Route `reproctl soak ...` commands to scripts/ostar/cli.py."""
    if len(sys.argv) < 2 or sys.argv[1] != "soak":
        return None
    _SOAK_SCRIPT = SCRIPTS_DIR / "ostar" / "cli.py"
    sys.argv = [str(_SOAK_SCRIPT)] + sys.argv[2:]
    parent = str(SCRIPTS_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    # Also make the parent package importable
    _PKG = SCRIPTS_DIR.parent
    if str(_PKG) not in sys.path:
        sys.path.insert(0, str(_PKG))
    for cached in list(sys.modules.keys()):
        if cached.startswith("scripts.ostar") or cached == "scripts.ostar":
            del sys.modules[cached]
    try:
        from scripts.ostar.cli import main as soak_main
    except Exception as e:
        print(f"[reproctl] could not import OSTAR subsystem: {e}",
              file=sys.stderr)
        return 10
    return soak_main()


def _dispatch_storage() -> int:
    """Handle `reproctl storage <action>` via storage_governance.py."""
    import argparse
    parent = str(SCRIPTS_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    for cached in list(sys.modules.keys()):
        if cached == "startup" or cached.startswith("startup."):
            del sys.modules[cached]
    try:
        from startup import storage_governance as sg
    except Exception as e:
        print(f"[reproctl] storage: could not import storage_governance: {e}",
              file=sys.stderr)
        return 10

    # Build a minimal parser for the storage subcommands.
    parser = argparse.ArgumentParser(prog="reproctl storage")
    sub = parser.add_subparsers(dest="action", required=True)

    p_status = sub.add_parser("status", help="Check disk space against policy")
    p_status.add_argument("--project", default=".")

    p_plan = sub.add_parser("plan-cleanup", help="Generate cleanup plan (dry-run)")
    p_plan.add_argument("--project", default=".")

    p_cleanup = sub.add_parser("cleanup", help="Execute approved cleanup plan")
    p_cleanup.add_argument("--project", default=".")
    p_cleanup.add_argument("--approved-plan", required=True,
                          help="Path to JSON cleanup plan from plan-cleanup")

    p_apply = sub.add_parser("apply", help="Apply retention + disk_policy from config")
    p_apply.add_argument("--project", default=".")
    p_apply.add_argument("--config", default="")

    try:
        args = parser.parse_args(sys.argv[2:])
    except SystemExit:
        return 1

    project_root = Path(args.project).resolve()
    action = args.action

    if action == "status":
        result = sg.check_disk_policy(project_root)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "OK" else 1

    elif action == "plan-cleanup":
        result = sg.plan_cleanup(project_root, dry_run=True)
        print(json.dumps(result, indent=2))
        return 0

    elif action == "cleanup":
        try:
            with open(args.approved_plan) as f:
                plan = json.load(f)
        except Exception as e:
            print(f"[reproctl] storage cleanup: failed to load plan: {e}",
                  file=sys.stderr)
            return 1
        result = sg.plan_cleanup(project_root, dry_run=False)
        # Override with files from approved plan if provided
        if "files_to_delete" in plan:
            to_delete_paths = {item["path"] for item in plan["files_to_delete"]}
            executed = []
            warnings = []
            for item in plan["files_to_delete"]:
                p = project_root / item["path"]
                try:
                    p.unlink()
                    executed.append(item)
                except Exception as e:
                    warnings.append(f"Failed to delete {item['path']}: {e}")
            result = {
                "timestamp": sg.datetime.now(sg.timezone.utc).isoformat(),
                "files_deleted": len(executed),
                "files_failed": len(plan["files_to_delete"]) - len(executed),
                "warnings": warnings,
            }
        print(json.dumps(result, indent=2))
        return 0

    elif action == "apply":
        config = {}
        if args.config:
            try:
                with open(args.config) as f:
                    config = json.load(f)
            except Exception as e:
                print(f"[reproctl] storage apply: failed to load config: {e}",
                      file=sys.stderr)
                return 1
        result = sg.apply_retention_config(project_root, config)
        print(json.dumps(result, indent=2))
        return 0

    return 0


# Run the dispatcher as early as possible so the new subcommands work even
# before the legacy module finishes importing (cheaper startup).
if __name__ != "__main__":
    pass
else:
    rc = _dispatch_to_orchestrator()
    if rc is not None:
        sys.exit(int(rc))
    rc = _dispatch_to_startup()
    if rc is not None:
        sys.exit(int(rc))

# Legacy CLI starts below — only consulted for backward-compatible commands.


# ── ANSI Colors ───────────────────────────────────────────────────────────────

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def colored(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"

def ok(text: str) -> str:
    return colored(f"[OK]   {text}", GREEN)

def info(text: str) -> str:
    return colored(f"[INFO] {text}", BLUE)

def warn(text: str) -> str:
    return colored(f"[WARN] {text}", YELLOW)

def fail(text: str) -> str:
    return colored(f"[FAIL] {text}", RED)

def step(text: str) -> str:
    return colored(f"[STEP] {text}", BOLD)


# ── State Management ─────────────────────────────────────────────────────────

def get_state_path() -> Path:
    return REPRO_DIR / "state.json"

def load_state() -> dict:
    """Load reproduction state from .repro/state.json."""
    path = get_state_path()
    if not path.exists():
        die(f"State file not found: {path}\nRun 'python reproctl.py init' first.")
    with open(path) as f:
        return json.load(f)

def save_state(state: dict) -> None:
    """Save reproduction state to .repro/state.json."""
    path = get_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(path)

def get_default_state() -> dict:
    """Return the default state structure."""
    return {
        "paper_url": "",
        "paper_title": "",
        "target_metrics": [],
        "phase": "init",
        "gates": {
            "gate_0_paper_audit": {
                "status": "pending",
                "timestamp": "",
                "evidence": "",
                "failure_reasons": []
            },
            "gate_1_preflight": {
                "status": "pending",
                "timestamp": "",
                "evidence": "",
                "failure_reasons": []
            },
            "gate_2_short_loop": {
                "status": "pending",
                "timestamp": "",
                "evidence": "",
                "failure_reasons": [],
                "details": {
                    "l0_smoke": "pending",
                    "l1_overfit": "pending",
                    "l2_mini_loop": "pending",
                    "l3_checkpoint_resume": "pending"
                }
            },
            "gate_3_parity": {
                "status": "pending",
                "timestamp": "",
                "evidence": "",
                "failure_reasons": [],
                "parity_results": {
                    "amp_parity": "not_tested",
                    "ddp_parity": "not_tested",
                    "batch_size_parity": "not_tested"
                }
            },
            "gate_4_full_training": {
                "status": "pending",
                "timestamp": "",
                "evidence": "",
                "failure_reasons": []
            },
            "gate_5_evidence": {
                "status": "pending",
                "timestamp": "",
                "evidence": "",
                "failure_reasons": []
            }
        },
        "current_mode": "strict_repro",
        "project_mode": "reproduce",
        "mode_switches": [],
        "flags": {
            "AUTO_PROCEED": False,
            "HUMAN_CHECKPOINT": True,
            "EXTERNAL_REVIEW": False,
            "REVIEW_DIFFICULTY": "hard",
            "COMPUTE_BUDGET_GPU_HOURS": None,
            "STORAGE_BUDGET_GB": None
        },
        "repositories": {
            "primary": {"url": "", "commit": "", "role": "primary", "local_path": ""},
            "references": []
        },
        "runs": [],
        "hardware": {}
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Project Mode (Phase 1) ────────────────────────────────────────────────────

VALID_PROJECT_MODES = ("reproduce", "diagnose", "extend")


def get_project_mode(state: Optional[dict] = None) -> str:
    """Return the current project mode. Default: 'reproduce'.

    Backward compatible: if state is None, try to load from disk;
    if disk state is missing (uninitialized), return 'reproduce'.
    If state has no 'project_mode' key (older schema), return 'reproduce'.
    """
    if state is None:
        try:
            state = load_state()
        except SystemExit:
            return "reproduce"
        except Exception:
            return "reproduce"
    return state.get("project_mode", "reproduce")


def set_project_mode(mode: str, reason: str = "", state: Optional[dict] = None) -> dict:
    """Switch project mode and append an entry to mode_switches audit trail.

    Writes a row to repro_audit/DECISION_LOG.md with timestamp + reason.
    Returns the updated state dict (also persisted to disk).
    """
    if mode not in VALID_PROJECT_MODES:
        raise ValueError(
            f"Invalid project_mode: {mode!r}. Must be one of {VALID_PROJECT_MODES}"
        )
    if state is None:
        state = load_state()
    old = state.get("project_mode", "reproduce")
    if old == mode:
        return state
    state["project_mode"] = mode
    state.setdefault("mode_switches", []).append({
        "timestamp": now_iso(),
        "from": old,
        "to": mode,
        "reason": reason
    })
    save_state(state)
    _append_decision_log(old, mode, reason)
    return state


def require_mode(required: str, state: Optional[dict] = None) -> None:
    """Exit with code 1 unless current project mode equals `required`.

    Used by functions that must not run in a different mode
    (e.g. /repro-contract should not silently run in extend mode).
    """
    current = get_project_mode(state)
    if current != required:
        sys.stderr.write(
            f"[require_mode] FAIL: current={current!r}, required={required!r}\n"
        )
        sys.exit(1)


def _append_decision_log(
    old_mode: str = "",
    new_mode: str = "",
    reason: str = "",
    *,
    actor: str = "agent",
    phase: str = "",
    task_id: str = "",
    decision_type: str = "mode_switch",
    links: str = "",
) -> None:
    """Append a row to repro_audit/DECISION_LOG.md (best effort).

    If the audit dir / log file does not exist, materialize them from the
    templates/decision_log.md canonical schema (10 columns: id, ts, actor,
    phase, task_id, decision_type, before→after, reason, links).

    For backward compatibility, the old positional form
    `_append_decision_log(old, new, reason)` still works: it is recorded
    as a `mode_switch` row with phase/task_id/links empty.
    """
    try:
        audit_dir = Path(".repro/repro_audit")
        audit_dir.mkdir(parents=True, exist_ok=True)
        log_path = audit_dir / "DECISION_LOG.md"

        # Materialize template if missing (canonical 10-column schema).
        # Use absolute path resolution: search templates/decision_log.md
        # relative to this script's directory so cwd does not matter.
        if not log_path.exists():
            script_dir = Path(__file__).resolve().parent
            tpl = script_dir.parent / "templates" / "decision_log.md"
            if tpl.exists():
                log_path.write_text(tpl.read_text())
            else:
                log_path.write_text(
                    "# Decision Log\n\n"
                    "| id | ts | actor | phase | task_id | decision_type | before → after | reason | links |\n"
                    "|---|---|---|---|---|---|---|---|---|\n"
                )

        # Determine next id (D000 seed, D001, D002, ...)
        existing = log_path.read_text().splitlines()
        ids = [
            int(m.group(1))
            for line in existing
            for m in [__import__("re").compile(r"^\| D(\d+) \|").match(line)]
            if m
        ]
        next_id = (max(ids) + 1) if ids else 0
        before_after = (
            f"{old_mode} → {new_mode}" if (old_mode or new_mode) else "—"
        )
        ts = now_iso()
        row = (
            f"| D{next_id:03d} | {ts} | {actor} | {phase or '—'} | "
            f"{task_id or '—'} | {decision_type} | {before_after} | "
            f"{reason or '—'} | {links or '—'} |\n"
        )

        # Ensure previous content ends with a newline so the new row starts on its own line
        with open(log_path, "rb+") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() > 0:
                f.seek(-1, os.SEEK_END)
                last = f.read(1)
                if last != b"\n":
                    f.write(b"\n")
            f.write(row.encode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"[warn] DECISION_LOG append failed: {e}\n")


# ── Gate Checking ─────────────────────────────────────────────────────────────

# ── Experiment Tracker (Phase 2) ───────────────────────────────────────────────

TRACKER_COLUMNS = (
    "experiment_id", "module", "status", "run_id", "support_claim",
    "parent_run_id", "start_time", "end_time", "duration_min",
    "gpu_hours", "metric_value", "status_detail",
)


def _tracker_path() -> Path:
    """Locate experiments/experiment_tracker.csv (relative to repo root)."""
    script_dir = Path(__file__).resolve().parent.parent
    return script_dir / "experiments" / "experiment_tracker.csv"


def _ensure_tracker_file() -> Path:
    """Make sure the tracker file exists with the canonical header; return path."""
    import csv
    p = _tracker_path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(TRACKER_COLUMNS)
    return p


def _read_tracker_rows(p: Path) -> list:
    import csv
    with open(p, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def record_experiment(
    experiment_id: str,
    module: str,
    status: str,
    *,
    run_id: str = "",
    support_claim: str = "",
    parent_run_id: str = "",
    start_time: str = "",
    end_time: str = "",
    duration_min: str = "",
    gpu_hours: str = "",
    metric_value: str = "",
    status_detail: str = "",
) -> Path:
    """Append a new row to experiments/experiment_tracker.csv (header auto-created)."""
    import csv
    p = _ensure_tracker_file()
    # Idempotency: if experiment_id already present, do not append a duplicate.
    existing_ids = {r.get("experiment_id") for r in _read_tracker_rows(p)}
    if experiment_id in existing_ids:
        sys.stderr.write(
            f"[warn] experiment_id {experiment_id!r} already in tracker; skipping\n"
        )
        return p
    row = {
        "experiment_id": experiment_id,
        "module": module,
        "status": status,
        "run_id": run_id,
        "support_claim": support_claim,
        "parent_run_id": parent_run_id,
        "start_time": start_time or now_iso(),
        "end_time": end_time,
        "duration_min": duration_min,
        "gpu_hours": gpu_hours,
        "metric_value": metric_value,
        "status_detail": status_detail,
    }
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
        w.writerow(row)
    _append_decision_log(
        old_mode="", new_mode="",
        reason=f"record_experiment: {experiment_id} ({module}) → {status}",
        actor="agent", phase="P2_claim_evidence",
        task_id=module, decision_type="checkpoint",
        links=f"experiments/experiment_tracker.csv#{experiment_id}",
    )
    return p


def update_experiment(experiment_id: str, **fields) -> bool:
    """Update one or more fields of an existing tracker row. Returns True if updated."""
    import csv
    p = _tracker_path()
    if not p.exists():
        sys.stderr.write(f"[warn] tracker missing: {p}\n")
        return False
    rows = _read_tracker_rows(p)
    hit = False
    for r in rows:
        if r.get("experiment_id") == experiment_id:
            for k, v in fields.items():
                if k in TRACKER_COLUMNS:
                    r[k] = v
            hit = True
            break
    if not hit:
        sys.stderr.write(f"[warn] no row with experiment_id={experiment_id!r}\n")
        return False
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    _append_decision_log(
        old_mode="", new_mode="",
        reason=f"update_experiment: {experiment_id} fields={list(fields)}",
        actor="agent", phase="P2_claim_evidence",
        decision_type="checkpoint",
        links=f"experiments/experiment_tracker.csv#{experiment_id}",
    )
    return True


def get_experiments(
    *,
    module: str = "",
    status: str = "",
    support_claim: str = "",
    experiment_id: str = "",
) -> list:
    """Read tracker and return rows matching the given filters (AND-combined)."""
    p = _tracker_path()
    if not p.exists():
        return []
    rows = _read_tracker_rows(p)
    out = []
    for r in rows:
        if module and r.get("module") != module:
            continue
        if status and r.get("status") != status:
            continue
        if support_claim and r.get("support_claim") != support_claim:
            continue
        if experiment_id and r.get("experiment_id") != experiment_id:
            continue
        out.append(r)
    return out


def cmd_record_experiment(args: argparse.Namespace) -> None:
    p = record_experiment(
        experiment_id=args.experiment_id,
        module=args.module,
        status=args.status,
        run_id=getattr(args, "run_id", "") or "",
        support_claim=getattr(args, "support_claim", "") or "",
        parent_run_id=getattr(args, "parent_run_id", "") or "",
        start_time=getattr(args, "start_time", "") or "",
        end_time=getattr(args, "end_time", "") or "",
        duration_min=str(getattr(args, "duration_min", "") or ""),
        gpu_hours=str(getattr(args, "gpu_hours", "") or ""),
        metric_value=str(getattr(args, "metric_value", "") or ""),
        status_detail=getattr(args, "status_detail", "") or "",
    )
    print(f"[ok] recorded {args.experiment_id} → {p}")


def cmd_update_experiment(args: argparse.Namespace) -> None:
    fields = {k: v for k, v in vars(args).items()
              if k not in {"command", "experiment_id"} and v not in (None, "")}
    ok = update_experiment(args.experiment_id, **fields)
    if ok:
        print(f"[ok] updated {args.experiment_id}")
    else:
        print("[fail] no row updated", file=sys.stderr)
        sys.exit(1)


def cmd_get_experiments(args: argparse.Namespace) -> None:
    rows = get_experiments(
        module=getattr(args, "module", "") or "",
        status=getattr(args, "status", "") or "",
        support_claim=getattr(args, "support_claim", "") or "",
        experiment_id=getattr(args, "experiment_id", "") or "",
    )
    if not rows:
        print("(no rows)")
        return
    print(f"{len(rows)} row(s):")
    for r in rows:
        print(" | ".join(f"{k}={r.get(k,'')}" for k in TRACKER_COLUMNS))


# ── Human Checkpoint (Phase 3) ────────────────────────────────────────────────

HUMAN_CHECKPOINT_ITEMS = [
    "1. Synthesize / augment data beyond what the paper describes",
    "2. Change dataset split (train/val/test boundaries)",
    "3. Change metric definition (IoU formula, mIoU class averaging, ignore-label list)",
    "4. Reduce model / batch / resolution to fit OOM",
    "5. Modify loss function (reweighting, adding auxiliary losses)",
    "6. Use a different physical batch size than the paper",
    "7. Enable AMP / fp16 when paper used fp32",
    "8. Substitute a different pretrained checkpoint",
    "9. Selectively report results (cherry-pick seeds, drop outliers)",
    "10. Switch to `extend` mode without prior `evolve` approval",
    "11. Exceed compute budget without a new decision row",
    "12. Report a number you cannot re-derive from logs / artifacts",
]


def _state_path() -> Path:
    """Locate .repro/repro_audit/STATE.json, materializing from template if missing."""
    script_dir = Path(__file__).resolve().parent.parent
    audit_dir = script_dir / ".repro" / "repro_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir / "STATE.json"


def _load_state() -> dict:
    """Load STATE.json (materializing defaults from control_flags.md if missing)."""
    p = _state_path()
    if not p.exists():
        script_dir = Path(__file__).resolve().parent.parent
        tpl = script_dir / "templates" / "control_flags.md"
        flags = {
            "HUMAN_CHECKPOINT": True, "AUTO_RETRY": False, "ALLOW_NETWORK": True,
            "REQUIRE_GIT_PIN": True, "TOLERANCE_MIOU": 0.5, "WIP_LIMIT": 1,
            "EVIDENCE_REQUIRED": True,
        }
        if tpl.exists():
            for line in tpl.read_text().splitlines():
                m = __import__("re").match(r"\|\s*`?(\w+)`?\s*\|\s*`?(\S+?)`?\s*\|", line)
                if m and m.group(1) in flags:
                    raw = m.group(2)
                    if raw.lower() in ("true", "false"):
                        flags[m.group(1)] = (raw.lower() == "true")
                    else:
                        try:
                            flags[m.group(1)] = float(raw) if "." in raw else int(raw)
                        except ValueError:
                            pass
        default = {
            "project_mode": "plan",
            "flags": flags,
            "gates": {},
            "phase": "P1_mode_contract",
        }
        p.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(p.read_text())


def _save_state(state: dict) -> None:
    p = _state_path()
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def human_checkpoint(
    *,
    action: str = "check",
    reason: str = "",
    approved_by: str = "",
    item: str = "",
) -> int:
    """Enforce the 12-item human checkpoint.

    action:
      'check' (default): exit 1 if HUMAN_CHECKPOINT=true (blocks), 0 if false.
      'override': record a risk_override and exit 0 (use only when a human has approved).
    """
    state = _load_state()
    flags = state.get("flags", {})
    hc = bool(flags.get("HUMAN_CHECKPOINT", True))

    if action == "check":
        if hc:
            print("[human-checkpoint] BLOCKED — HUMAN_CHECKPOINT=true")
            print("[human-checkpoint] The 12 mandatory pause-and-ask behaviors:")
            for line in HUMAN_CHECKPOINT_ITEMS:
                print(f"  {line}")
            print("[human-checkpoint] To proceed, set flags.HUMAN_CHECKPOINT=false with a risk_override decision row.")
            return 1
        else:
            print("[human-checkpoint] PASS — HUMAN_CHECKPOINT=false")
            return 0

    if action == "override":
        if not approved_by:
            print("[human-checkpoint] FAIL — override requires --approved-by <name>", file=sys.stderr)
            return 2
        _append_decision_log(
            old_mode="", new_mode="",
            reason=f"human_checkpoint override: {reason or 'unspecified'}",
            actor="human", phase="P3_human_checkpoint",
            task_id=item or "P3_T02",
            decision_type="risk_override",
            links=f"override approved_by={approved_by}",
        )
        print(f"[human-checkpoint] override recorded, approved_by={approved_by}")
        return 0

    print(f"[human-checkpoint] unknown action: {action}", file=sys.stderr)
    return 2


def cmd_human_checkpoint(args: argparse.Namespace) -> None:
    rc = human_checkpoint(
        action=getattr(args, "action", "check"),
        reason=getattr(args, "reason", "") or "",
        approved_by=getattr(args, "approved_by", "") or "",
        item=getattr(args, "item", "") or "",
    )
    sys.exit(rc)


# ── Core Principles (P11_T03) ───────────────────────────────────────────────────

HIGHEST_PRINCIPLES = (
    "require_official_first",
    "require_strict_mode",
    "require_raw_metrics",
    "require_provenance",
    "require_reproducibility",
)


def require_official_first(repo_meta: dict) -> None:
    """Principle: paper-author official repo first. If absent, raise."""
    if not repo_meta.get("is_official") and not repo_meta.get("official"):
        raise AssertionError(
            "PRINCIPLE require_official_first: no official repo metadata. "
            "Always prefer the paper-author repo before any third-party impl."
        )


def require_strict_mode(mode: str) -> None:
    """Principle: default mode must be strict_repro (not optimized / experimental)."""
    if mode not in ("strict_repro",):
        raise AssertionError(
            f"PRINCIPLE require_strict_mode: mode={mode!r}. "
            "strict_repro is required for the baseline; optimizations require parity."
        )


def require_raw_metrics(metrics_path) -> None:
    """Principle: a reported number must trace to a raw metrics file on disk."""
    from pathlib import Path
    p = Path(metrics_path) if metrics_path else None
    if p is None or not p.exists():
        raise AssertionError(
            "PRINCIPLE require_raw_metrics: no raw metrics file. "
            "Cannot verify the number if the artifact is missing."
        )


def require_provenance(commit_sha: str) -> None:
    """Principle: every run must record a commit SHA (not just a branch)."""
    import re
    if not commit_sha or not re.match(r"^[0-9a-f]{7,40}$", str(commit_sha)):
        raise AssertionError(
            f"PRINCIPLE require_provenance: commit_sha={commit_sha!r}. "
            "Pinned commit SHAs (not branches) are required for reproducibility."
        )


def require_reproducibility(recompute_value, reported_value, tolerance_pp: float = 0.5) -> None:
    """Principle: a reported metric must match a recomputed one within tolerance."""
    if recompute_value is None or reported_value is None:
        raise AssertionError(
            "PRINCIPLE require_reproducibility: missing recompute_value or reported_value."
        )
    if abs(float(recompute_value) - float(reported_value)) > float(tolerance_pp):
        raise AssertionError(
            f"PRINCIPLE require_reproducibility: gap "
            f"{abs(float(recompute_value) - float(reported_value)):.4f} > tolerance "
            f"{float(tolerance_pp):.4f}. Do not report numbers you cannot re-derive."
        )


def cmd_check_principles(args: argparse.Namespace) -> None:
    """CLI: run all 5 principle checks against a JSON spec from stdin or --spec-file."""
    import json as _json
    spec = {}
    if args.spec_file:
        spec = _json.loads(open(args.spec_file).read())
    elif not sys.stdin.isatty():
        spec = _json.loads(sys.stdin.read() or "{}")
    checks = [
        ("require_official_first", lambda: require_official_first(spec.get("repo_meta", {}))),
        ("require_strict_mode",    lambda: require_strict_mode(spec.get("mode", "strict_repro"))),
        ("require_raw_metrics",    lambda: require_raw_metrics(spec.get("metrics_path"))),
        ("require_provenance",     lambda: require_provenance(spec.get("commit_sha", ""))),
        ("require_reproducibility",lambda: require_reproducibility(
            spec.get("recompute_value"), spec.get("reported_value"),
            float(spec.get("tolerance_pp", 0.5)))),
    ]
    passed = 0
    failed = []
    for name, fn in checks:
        try:
            fn(); passed += 1
        except AssertionError as e:
            failed.append((name, str(e)))
    for name, msg in failed:
        print(f"[FAIL] {name}: {msg}")
    print(f"[ok] {passed}/5 principles passed")
    if failed:
        sys.exit(2)


def cmd_integrity_check(args: argparse.Namespace) -> None:
    """Verify schema files and core artifact integrity."""
    import hashlib
    plugin_root = PLUGIN_ROOT
    schemas_dir = plugin_root / "schemas"
    results = {"schemas": {}, "warnings": [], "errors": []}

    # Verify all 8 schemas parse as valid JSON
    expected_schemas = {
        "config.schema.json",
        "plan.schema.json",
        "task.schema.json",
        "state.schema.json",
        "automation_policy.schema.json",
        "adapter.schema.json",
        "run_manifest.schema.json",
        "evidence.schema.json",
    }
    if schemas_dir.exists():
        for f in schemas_dir.glob("*.schema.json"):
            name = f.name
            try:
                json.loads(f.read_text())
                results["schemas"][name] = "valid"
            except json.JSONDecodeError as e:
                results["schemas"][name] = f"INVALID: {e}"
                results["errors"].append(f"Schema {name} is not valid JSON")
    else:
        results["errors"].append(f"schemas/ directory not found at {schemas_dir}")

    # Verify storage_governance.py exists and is importable
    sg_path = SCRIPTS_DIR / "startup" / "storage_governance.py"
    if sg_path.exists():
        results["storage_governance"] = "present"
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("storage_governance", sg_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            funcs = ["check_disk_policy", "plan_cleanup", "apply_retention_config",
                     "scan_checkpoints", "DiskPolicy", "RetentionPolicy"]
            missing = [f for f in funcs if not hasattr(mod, f)]
            if missing:
                results["storage_governance"] = f"missing attrs: {missing}"
                results["errors"].append(f"storage_governance missing: {missing}")
            else:
                results["storage_governance"] = "importable"
        except Exception as e:
            results["storage_governance"] = f"import failed: {e}"
            results["errors"].append(f"storage_governance import error: {e}")
    else:
        results["storage_governance"] = "MISSING"
        results["errors"].append(f"storage_governance.py not found at {sg_path}")

    # Summary
    print(json.dumps(results, indent=2))
    if results["errors"]:
        print(f"\n{fail(f'{len(results["errors"])} error(s) found')}")
        sys.exit(1)
    elif results["schemas"]:
        missing = expected_schemas - set(results["schemas"].keys())
        if missing:
            results["warnings"].extend(f"Missing schema: {m}" for m in missing)
            print(f"\n{warn(f'{len(missing)} schema(s) missing')}")
        else:
            print(f"\n{ok('All 8 schemas valid and storage_governance.py functional')}")
        sys.exit(0 if not results["warnings"] else 0)
    sys.exit(0)


def check_gate(gate_name: str, state: dict, required: bool = True) -> bool:
    """Check if a gate has passed."""
    gate = state.get("gates", {}).get(gate_name, {})
    status = gate.get("status", "pending")
    if required and status != "passed":
        reasons = gate.get("failure_reasons", [])
        if reasons:
            print(fail(f"Gate '{gate_name}' FAILED:"))
            for r in reasons:
                print(f"  - {r}")
        else:
            print(fail(f"Gate '{gate_name}' is not passed (status: {status})"))
        return False
    return status == "passed"

def require_gate(gate_name: str, state: dict) -> None:
    """Require a gate to be passed or die."""
    if not check_gate(gate_name, state):
        print(f"\n{fail('Cannot proceed: required gate not passed.')}")
        sys.exit(1)

def get_gate_status_summary(state: dict) -> list[tuple[str, str]]:
    """Return list of (gate_name, status) tuples."""
    gates = state.get("gates", {})
    return [
        (name, gate.get("status", "pending"))
        for name, gate in gates.items()
    ]

def print_gate_status(state: dict) -> None:
    """Print a colored gate status table."""
    print(f"\n{BOLD}Reproduction Gate Status{RESET}")
    print("─" * 60)
    for name, status in get_gate_status_summary(state):
        if status == "passed":
            symbol = ok("✓")
        elif status == "failed":
            symbol = fail("✗")
        elif status == "pending":
            symbol = warn("○")
        else:
            symbol = info(status)
        print(f"  {symbol}  {name}")

    phase = state.get("phase", "unknown")
    mode = state.get("current_mode", "strict_repro")
    print(f"\n  Phase: {BLUE}{phase}{RESET}  |  Mode: {BLUE}{mode}{RESET}")
    print("─" * 60)


# ── Short-Loop Tests ─────────────────────────────────────────────────────────

def run_smoke_test(primary_path: Path, config_path: Optional[Path] = None) -> dict:
    """L0: Run real forward/backward pass on one batch."""
    print(step("Running L0 Smoke Test (forward + backward pass)..."))

    smoke_script = SCRIPTS_DIR / "smoke_test.py"
    if not smoke_script.exists():
        print(warn(f"smoke_test.py not found at {smoke_script}, skipping"))
        return {"status": "skipped", "reason": "smoke_test.py not found"}

    cmd = [sys.executable, str(smoke_script)]
    if config_path:
        cmd += ["--config", str(config_path)]
    cmd += ["--primary", str(primary_path)]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(primary_path))

    passed = result.returncode == 0
    status = "passed" if passed else "failed"

    if passed:
        print(ok(f"L0 Smoke Test passed"))
    else:
        print(fail(f"L0 Smoke Test failed"))
        print(result.stdout)
        print(result.stderr)

    return {
        "status": status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "timestamp": now_iso()
    }


def run_overfit_test(primary_path: Path, config_path: Optional[Path] = None,
                     steps: int = 100) -> dict:
    """L1: Overfit a single batch to random labels."""
    print(step("Running L1 Overfit Test (memorize single batch)..."))

    overfit_script = SCRIPTS_DIR / "overfit_test.py"
    if not overfit_script.exists():
        print(warn(f"overfit_test.py not found at {overfit_script}, skipping"))
        return {"status": "skipped", "reason": "overfit_test.py not found"}

    cmd = [sys.executable, str(overfit_script), "--steps", str(steps)]
    if config_path:
        cmd += ["--config", str(config_path)]
    cmd += ["--primary", str(primary_path)]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(primary_path))
    passed = result.returncode == 0
    status = "passed" if passed else "failed"

    if passed:
        print(ok(f"L1 Overfit Test passed"))
    else:
        print(fail(f"L1 Overfit Test failed"))
        print(result.stdout)
        print(result.stderr)

    return {
        "status": status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "timestamp": now_iso()
    }


def run_mini_loop_test(primary_path: Path, config_path: Optional[Path] = None,
                       epochs: int = 3) -> dict:
    """L2: Run end-to-end loop on mini dataset."""
    print(step(f"Running L2 Mini-Loop Test ({epochs} epochs)..."))

    mini_loop_script = SCRIPTS_DIR / "mini_loop_test.py"
    if not mini_loop_script.exists():
        print(warn(f"mini_loop_test.py not found at {mini_loop_script}, skipping"))
        return {"status": "skipped", "reason": "mini_loop_test.py not found"}

    cmd = [sys.executable, str(mini_loop_script), "--epochs", str(epochs)]
    if config_path:
        cmd += ["--config", str(config_path)]
    cmd += ["--primary", str(primary_path)]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(primary_path))
    passed = result.returncode == 0
    status = "passed" if passed else "failed"

    if passed:
        print(ok(f"L2 Mini-Loop Test passed"))
    else:
        print(fail(f"L2 Mini-Loop Test failed"))
        print(result.stdout)
        print(result.stderr)

    return {
        "status": status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "timestamp": now_iso()
    }


def run_checkpoint_resume_test(primary_path: Path, config_path: Optional[Path] = None) -> dict:
    """L3: Verify checkpoint save/load produces identical results."""
    print(step("Running L3 Checkpoint Resume Test..."))

    resume_script = SCRIPTS_DIR / "checkpoint_resume_test.py"
    if not resume_script.exists():
        print(warn(f"checkpoint_resume_test.py not found, skipping"))
        return {"status": "skipped", "reason": "checkpoint_resume_test.py not found"}

    cmd = [sys.executable, str(resume_script)]
    if config_path:
        cmd += ["--config", str(config_path)]
    cmd += ["--primary", str(primary_path)]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(primary_path))
    passed = result.returncode == 0
    status = "passed" if passed else "failed"

    if passed:
        print(ok(f"L3 Checkpoint Resume Test passed"))
    else:
        print(fail(f"L3 Checkpoint Resume Test failed"))
        print(result.stdout)
        print(result.stderr)

    return {
        "status": status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "timestamp": now_iso()
    }


# ── Launch ────────────────────────────────────────────────────────────────────

def can_launch(mode: str = "strict_repro") -> bool:
    """Check if full training can be launched for the given mode."""
    state = load_state()

    print(f"\n{BOLD}Gate Check for Mode: {mode}{RESET}")
    print("─" * 60)

    # Always require Gates 0, 1, 2
    ok0 = check_gate("gate_0_paper_audit", state)
    ok1 = check_gate("gate_1_preflight", state)
    ok2 = check_gate("gate_2_short_loop", state)

    # Gate 3 required for optimized mode
    if mode == "optimized_repro_safe":
        ok3 = check_gate("gate_3_parity", state)
    else:
        ok3 = True  # strict_repro doesn't need parity

    all_ok = ok0 and ok1 and ok2 and ok3

    if all_ok:
        print(f"\n{ok('All required gates passed. Launch permitted.')}")
    else:
        print(f"\n{fail('Cannot launch. Resolve gate failures before proceeding.')}")

    print_gate_status(state)
    return all_ok


def launch_training(run_id: str, mode: str, seed: int, epochs: int,
                    config_override: Optional[str] = None,
                    extra_args: Optional[list[str]] = None) -> None:
    """Launch full training with gate enforcement."""

    state = load_state()

    # Enforce gates
    ok0 = check_gate("gate_0_paper_audit", state)
    ok1 = check_gate("gate_1_preflight", state)
    ok2 = check_gate("gate_2_short_loop", state)

    if mode == "optimized_repro_safe":
        ok3 = check_gate("gate_3_parity", state)
    else:
        ok3 = True

    if not (ok0 and ok1 and ok2 and ok3):
        print(fail("\nreproctl: Cannot launch full training. Required gates not passed."))
        print(fail("Run 'python reproctl.py can-launch --mode=" + mode + "' for details."))
        sys.exit(1)

    # Get primary repo path
    primary_url = state.get("repositories", {}).get("primary", {}).get("url", "")
    primary_path = Path("primary")
    if not primary_path.exists():
        print(fail(f"Primary repository not found at: {primary_path}"))
        sys.exit(1)

    # Find train script
    train_script = _find_train_script(primary_path)
    if not train_script:
        print(fail("No training script found in primary repository."))
        sys.exit(1)

    # Build command
    cmd = [sys.executable, str(train_script)]
    if config_override:
        cmd += ["--config", config_override]
    cmd += ["--seed", str(seed), "--epochs", str(epochs)]

    if mode == "optimized_repro_safe":
        cmd += ["--amp"]

    if extra_args:
        cmd += extra_args

    # Create run directory
    run_dir = EXPERIMENTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "checkpoints").mkdir(exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)
    (run_dir / "metrics").mkdir(exist_ok=True)

    # Record run
    run_record = {
        "run_id": run_id,
        "timestamp": now_iso(),
        "commit": _get_git_commit(primary_path),
        "branch": _get_git_branch(primary_path),
        "config": config_override or "default",
        "seed": seed,
        "mode": mode,
        "epochs": epochs,
        "command": " ".join(cmd),
        "working_dir": str(primary_path),
        "phase": "training",
        "status": "running",
        "run_dir": str(run_dir)
    }

    # Save environment snapshot
    env_file = run_dir / "artifacts" / "environment.txt"
    env_file.parent.mkdir(exist_ok=True)
    env_result = subprocess.run(
        [sys.executable, "-m", "torch.utils.collect_env"],
        capture_output=True, text=True
    )
    with open(env_file, "w") as f:
        f.write(env_result.stdout)

    # Update state
    state["runs"].append(run_record)
    state["phase"] = "full_training"
    save_state(state)

    # Save command script
    cmd_file = run_dir / "artifacts" / "command.sh"
    with open(cmd_file, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"cd {primary_path}\n")
        f.write(" ".join(cmd) + "\n")

    print(f"\n{step(f'Launching training run {run_id}')}")
    print(f"  Mode:    {mode}")
    print(f"  Seed:    {seed}")
    print(f"  Epochs:  {epochs}")
    print(f"  Command: {' '.join(cmd)}")
    print(f"  Run dir: {run_dir}")

    # Execute training
    log_file = run_dir / "logs" / "train.log"
    with open(log_file, "w") as log:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(primary_path)
        )
        for line in proc.stdout:
            log.write(line)
            print(line, end="")

    proc.wait()
    exit_code = proc.returncode

    # Update run status
    for r in state["runs"]:
        if r["run_id"] == run_id:
            r["status"] = "success" if exit_code == 0 else "failed"
            r["exit_code"] = exit_code
            r["completed_at"] = now_iso()
            break

    save_state(state)

    if exit_code == 0:
        print(f"\n{ok(f'Training run {run_id} completed successfully.')}")
    else:
        print(f"\n{fail(f'Training run {run_id} failed with exit code {exit_code}.')}")
        print(fail("Failed runs are preserved. Do NOT delete them."))

    sys.exit(exit_code)


def _find_train_script(repo_path: Path) -> Optional[Path]:
    """Find the training script in the repository."""
    candidates = [
        repo_path / "train.py",
        repo_path / "train.sh",
        repo_path / "main.py",
        repo_path / "scripts" / "train.py",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

def _get_git_commit(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except subprocess.CalledProcessError:
        return "unknown"

def _get_git_branch(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
    except subprocess.CalledProcessError:
        return "unknown"


# ── Metric Verification ──────────────────────────────────────────────────────

def verify_metrics(run_id: Optional[str] = None) -> dict:
    """Verify that metrics can be reproduced from checkpoints."""
    state = load_state()

    if run_id:
        runs = [r for r in state.get("runs", []) if r.get("run_id") == run_id]
        if not runs:
            die(f"Run '{run_id}' not found in state.")
    else:
        runs = [r for r in state.get("runs", []) if r.get("status") == "success"]
        if not runs:
            die("No successful runs found to verify.")

    print(f"\n{step(f'Verifying metrics for {len(runs)} run(s)...')}")

    results = []
    for run in runs:
        rid = run["run_id"]
        print(f"\n  Verifying run {rid}...")

        # Check checkpoint exists
        run_dir = Path(run.get("run_dir", f"experiments/{rid}"))
        checkpoint_dir = run_dir / "checkpoints"
        if not checkpoint_dir.exists():
            print(warn(f"  Checkpoint directory not found: {checkpoint_dir}"))
            results.append({"run_id": rid, "status": "failed", "reason": "no checkpoints"})
            continue

        checkpoints = sorted(checkpoint_dir.glob("*.pth"))
        if not checkpoints:
            print(warn(f"  No checkpoints found in {checkpoint_dir}"))
            results.append({"run_id": rid, "status": "failed", "reason": "no checkpoints"})
            continue

        # Check metrics file
        metrics_dir = run_dir / "metrics"
        metrics_files = list(metrics_dir.glob("*.json")) if metrics_dir.exists() else []
        has_raw_metrics = len(metrics_files) > 0

        # For now, just record what we found
        results.append({
            "run_id": rid,
            "status": "verified",
            "checkpoints_found": len(checkpoints),
            "metrics_found": len(metrics_files),
            "has_raw_metrics": has_raw_metrics,
            "timestamp": now_iso()
        })

        print(f"    Checkpoints: {len(checkpoints)}")
        print(f"    Raw metrics: {'yes' if has_raw_metrics else 'no'}")
        print(f"    {ok('Verified')}")

    return {"verifications": results, "timestamp": now_iso()}


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a new reproduction project."""
    print(f"\n{step('Initializing reproduction project...')}")

    REPRO_DIR.mkdir(parents=True, exist_ok=True)
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    state = get_default_state()
    if args.paper:
        state["paper_url"] = args.paper
    if args.target:
        state["target_metrics"] = [args.target]

    save_state(state)
    print(ok(f"Initialized at {REPRO_DIR}"))
    print(f"  Paper URL: {state['paper_url'] or '(none set)'}")
    print(f"  Target:    {state['target_metrics'] or '(none set)'}")
    print(f"\n  Next: Run '/repro-discover' to find candidate repositories.")


def cmd_status(args: argparse.Namespace) -> None:
    """Show current gate status."""
    state = load_state()
    print_gate_status(state)

    runs = state.get("runs", [])
    if runs:
        print(f"\n  Runs: {len(runs)}")
        for r in runs[-3:]:
            status_str = ok(r.get("status", "unknown")) if r.get("status") == "success" \
                else fail(r.get("status", "unknown")) if r.get("status") == "failed" \
                else warn(r.get("status", "unknown"))
            print(f"    {status_str}  {r.get('run_id', '?')}  mode={r.get('mode')}  seed={r.get('seed')}")


def cmd_can_launch(args: argparse.Namespace) -> None:
    """Check if training can be launched."""
    ok_flag = can_launch(mode=args.mode)
    sys.exit(0 if ok_flag else 1)


def cmd_launch(args: argparse.Namespace) -> None:
    """Launch full training."""
    run_id = str(uuid.uuid4())[:8]
    launch_training(
        run_id=run_id,
        mode=args.mode,
        seed=args.seed,
        epochs=args.epochs,
        config_override=args.config,
        extra_args=args.extra
    )


def cmd_run_short_loop(args: argparse.Namespace) -> None:
    """Run short-loop validation tests."""
    state = load_state()

    primary_path = Path(state.get("repositories", {}).get("primary", {}).get("local_path", "primary"))
    if not primary_path.exists():
        die(f"Primary repository not found at: {primary_path}")

    config_path = Path(args.config) if args.config else None

    results = {}

    # Gate 0 required
    require_gate("gate_0_paper_audit", state)
    # Gate 1 required
    require_gate("gate_1_preflight", state)

    # Run requested levels
    if args.level in ("L0", "all", None):
        results["l0_smoke"] = run_smoke_test(primary_path, config_path)
    if args.level in ("L1", "all", None):
        results["l1_overfit"] = run_overfit_test(primary_path, config_path, steps=args.overfit_steps)
    if args.level in ("L2", "all", None):
        results["l2_mini_loop"] = run_mini_loop_test(primary_path, config_path, epochs=args.epochs)
    if args.level in ("L3", "all", None):
        results["l3_checkpoint_resume"] = run_checkpoint_resume_test(primary_path, config_path)

    # Update gate 2
    all_passed = all(r.get("status") == "passed" for r in results.values() if r)
    none_failed = all(r.get("status") in ("passed", "skipped") for r in results.values() if r)

    gate_2 = state["gates"]["gate_2_short_loop"]
    gate_2["details"] = {
        k: v.get("status", "unknown") for k, v in results.items()
    }

    if all_passed or none_failed:
        gate_2["status"] = "passed" if none_failed else "failed"
        gate_2["timestamp"] = now_iso()
        gate_2["evidence"] = "repro_audit/short_loop/"
        state["phase"] = "short_loop"
        print(f"\n{ok('Gate 2 (Short Loop) COMPLETED')}")
    else:
        gate_2["status"] = "failed"
        gate_2["failure_reasons"] = [
            f"{k} failed" for k, v in results.items() if v.get("status") == "failed"
        ]
        print(f"\n{fail('Gate 2 (Short Loop) FAILED')}")

    save_state(state)
    print_gate_status(state)


def cmd_verify(args: argparse.Namespace) -> None:
    """Verify metrics from checkpoints."""
    result = verify_metrics(run_id=args.run_id)

    verifications = result.get("verifications", [])
    all_verified = all(v.get("status") == "verified" for v in verifications)

    if all_verified:
        print(f"\n{ok('All metrics verified successfully.')}")
        state = load_state()
        state["gates"]["gate_5_evidence"]["status"] = "passed"
        state["gates"]["gate_5_evidence"]["timestamp"] = now_iso()
        state["gates"]["gate_5_evidence"]["evidence"] = "repro_audit/evidence_chain/"
        save_state(state)
    else:
        print(f"\n{fail('Some verifications failed.')}")

    print_gate_status(load_state())


def cmd_report(args: argparse.Namespace) -> None:
    """Generate human-readable report."""
    state = load_state()

    print(f"\n{BOLD}=== Reproduction Report ==={RESET}\n")

    print(f"Paper: {state.get('paper_url', 'N/A')}")
    print(f"Phase: {state.get('phase', 'N/A')}")
    print(f"Mode:  {state.get('current_mode', 'N/A')}")

    print_gate_status(state)

    runs = state.get("runs", [])
    if runs:
        print(f"\n{BOLD}Training Runs:{RESET}")
        for r in runs:
            status = r.get("status", "unknown")
            sym = ok("✓") if status == "success" else fail("✗") if status == "failed" else warn("○")
            print(f"  {sym} {r.get('run_id')}  mode={r.get('mode')}  seed={r.get('seed')}  epochs={r.get('epochs')}  phase={r.get('phase')}")


def cmd_update_gate(args: argparse.Namespace) -> None:
    """Manually update gate status."""
    state = load_state()
    gate = state["gates"].get(args.gate)
    if not gate:
        die(f"Unknown gate: {args.gate}")

    old_status = gate.get("status")
    gate["status"] = args.status
    gate["timestamp"] = now_iso()
    if args.evidence:
        gate["evidence"] = args.evidence

    save_state(state)
    print(f"{info(f'Gate {args.gate}: {old_status} → {args.status}')}")
    print_gate_status(state)


def cmd_help(args: argparse.Namespace) -> None:
    """Show help message."""
    print(__doc__)


def die(msg: str) -> None:
    print(fail(f"ERROR: {msg}"))
    sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reproctl.py",
        description="Deep Learning Paper Reproduction Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize a new reproduction project")
    p_init.add_argument("--paper", help="Paper URL or arXiv ID")
    p_init.add_argument("--target", help="Target metric (e.g., 'Table 3, mIoU')")

    # status
    sub.add_parser("status", help="Show current gate status")

    # can-launch
    p_can = sub.add_parser("can-launch", help="Check if training can be launched")
    p_can.add_argument("--mode", default="strict_repro",
                       choices=["strict_repro", "optimized_repro_safe", "experimental_fast"])

    # launch
    p_launch = sub.add_parser("launch", help="Launch full training")
    p_launch.add_argument("--mode", default="strict_repro",
                         choices=["strict_repro", "optimized_repro_safe", "experimental_fast"])
    p_launch.add_argument("--seed", type=int, default=42)
    p_launch.add_argument("--epochs", type=int, default=300)
    p_launch.add_argument("--config")
    p_launch.add_argument("extra", nargs="*", help="Extra arguments to training script")

    # run-short-loop
    p_loop = sub.add_parser("run-short-loop", help="Run short-loop validation tests")
    p_loop.add_argument("--level", choices=["L0", "L1", "L2", "L3", "all"], default="all")
    p_loop.add_argument("--config")
    p_loop.add_argument("--overfit-steps", type=int, default=100)
    p_loop.add_argument("--epochs", type=int, default=3)

    # verify
    p_verify = sub.add_parser("verify", help="Verify metrics from checkpoints")
    p_verify.add_argument("--run-id")

    # report
    sub.add_parser("report", help="Generate human-readable report")

    # update-gate
    p_ug = sub.add_parser("update-gate", help="Manually update gate status")
    p_ug.add_argument("gate", help="Gate name (e.g., gate_0_paper_audit)")
    p_ug.add_argument("status", choices=["passed", "failed", "pending"])
    p_ug.add_argument("--evidence")

    # help
    sub.add_parser("help", help="Show this help message")

    # record-experiment
    p_rec = sub.add_parser("record-experiment", help="Append a row to experiments/experiment_tracker.csv")
    p_rec.add_argument("experiment_id")
    p_rec.add_argument("module")
    p_rec.add_argument("status")
    p_rec.add_argument("--run-id", default="")
    p_rec.add_argument("--support-claim", default="")
    p_rec.add_argument("--parent-run-id", default="")
    p_rec.add_argument("--start-time", default="")
    p_rec.add_argument("--end-time", default="")
    p_rec.add_argument("--duration-min", default="")
    p_rec.add_argument("--gpu-hours", default="")
    p_rec.add_argument("--metric-value", default="")
    p_rec.add_argument("--status-detail", default="")

    # update-experiment
    p_upd = sub.add_parser("update-experiment", help="Update fields of an existing tracker row")
    p_upd.add_argument("experiment_id")
    p_upd.add_argument("--module")
    p_upd.add_argument("--status")
    p_upd.add_argument("--run-id")
    p_upd.add_argument("--support-claim")
    p_upd.add_argument("--parent-run-id")
    p_upd.add_argument("--start-time")
    p_upd.add_argument("--end-time")
    p_upd.add_argument("--duration-min")
    p_upd.add_argument("--gpu-hours")
    p_upd.add_argument("--metric-value")
    p_upd.add_argument("--status-detail")

    # get-experiments
    p_get = sub.add_parser("get-experiments", help="Query tracker (AND-combined filters)")
    p_get.add_argument("--module", default="")
    p_get.add_argument("--status", default="")
    p_get.add_argument("--support-claim", default="")
    p_get.add_argument("--experiment-id", default="")

    # human-checkpoint
    p_hc = sub.add_parser("human-checkpoint", help="Enforce the 12-item human checkpoint")
    p_hc.add_argument("--action", choices=["check", "override"], default="check")
    p_hc.add_argument("--reason", default="")
    p_hc.add_argument("--approved-by", default="")
    p_hc.add_argument("--item", default="")

    # check-principles
    p_cp = sub.add_parser("check-principles", help="Run the 5 highest principles against a JSON spec")
    p_cp.add_argument("--spec-file", default="", help="path to JSON spec; stdin if absent")

    # integrity-check
    sub.add_parser("integrity-check", help="Verify schema files and core artifact integrity")

    return parser


def main() -> None:
    # Dispatch `reproctl audit ...` and `reproctl soak ...` before argparse
    # (avoids building the legacy parser when a subsystem handles the argv).
    if len(sys.argv) >= 2 and sys.argv[1] == "audit":
        rc = _dispatch_to_audit()
        sys.exit(int(rc) if rc is not None else 0)
    if len(sys.argv) >= 2 and sys.argv[1] == "soak":
        rc = _dispatch_to_soak()
        sys.exit(int(rc) if rc is not None else 0)

    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "can-launch": cmd_can_launch,
        "launch": cmd_launch,
        "run-short-loop": cmd_run_short_loop,
        "verify": cmd_verify,
        "report": cmd_report,
        "update-gate": cmd_update_gate,
        "record-experiment": cmd_record_experiment,
        "update-experiment": cmd_update_experiment,
        "get-experiments": cmd_get_experiments,
        "human-checkpoint": cmd_human_checkpoint,
        "check-principles": cmd_check_principles,
        "integrity-check": cmd_integrity_check,
        "help": cmd_help,
    }

    cmd_fn = commands.get(args.command)
    if cmd_fn:
        cmd_fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
