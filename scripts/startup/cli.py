"""Top-level CLI for the unified startup system.

Usage:
    reproctl start  --project <root> --plan <plan.md> [--mode strict] [--dry-run]
    reproctl doctor --project <root> [--plan <plan.md>]
    reproctl status --project <root>
    reproctl resume --project <root>
    reproctl stop   --project <root>
    reproctl verify --project <root>
    reproctl version

All command output (success and failure) follows the spec's required format.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running this file directly (python scripts/startup/cli.py) by adding
# the parent dir to sys.path.
_THIS = Path(__file__).resolve()
_PKG_PARENT = _THIS.parent.parent
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from startup import (
    __version__,
)
from startup import (
    config as _config,
)
from startup import (
    doctor as _doctor,
)
from startup import (
    lock as _lock,
)
from startup import (
    log_setup as _log,
)
from startup import (
    plan_schema as _plan_schema,
)
from startup import (
    plan_validate as _plan_legacy,
)
from startup import (
    recovery as _recovery,
)
from startup import (
    state_machine as _sm,
)
from startup import (
    stop as _stop,
)

EXIT_OK = 0
EXIT_BAD_CONFIG = 2
EXIT_DOCTOR_FAIL = 3
EXIT_ALREADY_RUNNING = 4
EXIT_INVALID_PLAN = 5
EXIT_TASK_FAILED = 6
EXIT_TASK_BLOCKED = 7
EXIT_RESUME_FAILED = 8
EXIT_SECURITY_BLOCK = 9
EXIT_INTERNAL = 10

VALID_MODES = ("strict", "optimized", "diagnose", "test", "extend")


# ──────────────────────────────────────────────────────────────────────
# Path / platform helpers (no hardcoding)
# ──────────────────────────────────────────────────────────────────────


def normalize_path(p: str | os.PathLike) -> str:
    """Return an absolute, normalized path string for the current OS.

    On Windows / WSL this expands ``%ENV%`` and short-path prefixes via
    ``Path.resolve()``. On POSIX it just resolves ``.`` / ``..`` and
    symlinks.
    """
    return str(Path(os.path.expandvars(os.path.expanduser(str(p)))).resolve())


def platform_tag() -> str:
    """Return ``linux`` / ``darwin`` / ``windows`` / ``wsl`` / ``unknown``.

    WSL is detected via ``/proc/sys/kernel/osrelease`` containing
    ``microsoft`` (the canonical WSL fingerprint) or via the
    ``WSL_DISTRO_NAME`` / ``WSLENV`` env vars.
    """
    sysname = platform.system().lower()
    if sysname == "linux":
        try:
            txt = Path("/proc/sys/kernel/osrelease").read_text().lower()
            if "microsoft" in txt or "wsl" in txt:
                return "wsl"
        except OSError:
            pass
        if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSLENV"):
            return "wsl"
        return "linux"
    if sysname == "darwin":
        return "darwin"
    if sysname in ("windows", "win32"):
        return "windows"
    return "unknown"


def plugin_root() -> Path:
    """Return the plugin root using ``Path(__file__)``. Never hard-coded."""
    return Path(__file__).resolve().parents[2]


# ──────────────────────────────────────────────────────────────────────
# Output formatters
# ──────────────────────────────────────────────────────────────────────

import hashlib


def _sha256_text(path: Path) -> str:
    """Return SHA-256 of a file's UTF-8 text."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _cmd_self_test(
    project: Path, plan: Path | None, cfg: dict, layout: dict, log_level: str
) -> int:
    """R3F-6: Run doctor + plan validation in isolation.

    Writes ``startup_verification_report.json`` and exits 0.
    Does NOT acquire the lock or claim tasks.
    """
    log_path = layout["startup"] / "startup.log"
    log = _log.get_logger("reproctl.startup", log_file=log_path, level=log_level)
    report: dict[str, Any] = {
        "report_type": "startup_self_test",
        "generated_at": _now(),
        "project_root": str(project),
        "plan_path": str(plan) if plan else None,
        "doctor": None,
        "plan_validation": None,
        "lock_status": None,
        "overall": "PASS",
        "errors": [],
    }

    # Doctor
    pf = _sm.preflight(
        project_root=project,
        plan_path=plan or Path(""),
        expected_cuda=cfg.get("expected_cuda") or None,
    )
    doctor_report = pf["report"]
    report["doctor"] = {
        "overall": doctor_report["overall"],
        "summary": doctor_report["summary"],
        "checks": doctor_report["checks"],
        "failed_checks": [c["name"] for c in doctor_report["checks"] if c["status"] == "FAIL"],
    }
    if doctor_report["overall"] == "FAIL":
        report["overall"] = "FAIL"
        report["errors"].append("doctor failed")

    # Plan validation (canonical + legacy fallback)
    plan_errors: list[str] = []
    plan_hash = ""
    if plan and plan.exists():
        try:
            plan_schema_obj = _plan_schema.load_plan(plan)
            plan_hash = plan_schema_obj._canonical_sha256 or _sha256_text(plan)
        except SystemExit:
            # Non-frontmatter legacy plan — use migrate_legacy_plan
            import json as _json

            try:
                legacy = _json.loads(plan.read_text())
            except Exception:
                import yaml as _yaml

                loaded = _yaml.safe_load(plan.read_text())
                # Handle YAML list of task dicts (not a full plan dict)
                if isinstance(loaded, list):
                    legacy = {"tasks": loaded}
                else:
                    legacy = loaded
            if not isinstance(legacy, dict):
                plan_errors = [f"plan is a {type(legacy).__name__}, not a mapping"]
            else:
                migrated = _plan_schema.migrate_legacy_plan(legacy)
                migrated_obj = _plan_schema._dict_to_plan(
                    migrated, plan.read_text().encode("utf-8"), loaded_from=plan
                )
                schema_errors = [
                    e
                    for e in _plan_schema.validate_plan(migrated_obj)
                    if e.field != "tasks" or "circular" not in e.message
                ]
                schema_errors = [
                    e
                    for e in schema_errors
                    if not (e.field == "deps" and "unknown task" in e.message)
                ]
                schema_errors = [e for e in schema_errors if not (e.field == "schema_version")]
                plan_errors = [str(e) for e in schema_errors]
            plan_hash = _sha256_text(plan)
    else:
        plan_errors = ["no plan provided or plan does not exist"]

    report["plan_validation"] = {
        "plan_hash": plan_hash,
        "errors": plan_errors,
        "status": "PASS" if not plan_errors else "FAIL",
    }
    if plan_errors:
        report["overall"] = "FAIL"
        report["errors"].append("plan validation failed")

    # Lock status (check-only, don't acquire)
    lock_path = project / ".repro" / "run.lock"
    lock_held = lock_path.exists()
    report["lock_status"] = {
        "lock_file": str(lock_path),
        "held": lock_held,
        "acquired": False,
        "note": "not acquired in self-test mode",
    }

    # Write report
    report_path = layout["startup"] / "startup_verification_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if report["overall"] == "PASS":
        print("[self-test] PASS — all checks ok", file=sys.stdout)
        print(f"[self-test] report: {report_path}", file=sys.stdout)
        return EXIT_OK
    else:
        print(f"[self-test] FAIL — errors: {report['errors']}", file=sys.stdout)
        print(f"[self-test] report: {report_path}", file=sys.stdout)
        return EXIT_BAD_CONFIG


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _print_success_summary(state: dict, cfg: dict) -> None:
    """Print the spec's mandated startup summary format."""
    nxt = state.get("next_task") or {}
    last = state.get("last_completed_task") or "(none)"
    log_path = state.get("log_path") or ""
    out = [
        "Repro Agent Ready",
        f"Project: {cfg['project_root']}",
        f"Plan: {cfg['plan_path']}",
        f"Mode: {cfg['mode']}",
        f"Plugin Version: {state.get('plugin_version')}",
        f"Git Commit: {state.get('git_commit')}",
        f"GPU: {state.get('gpu_label')}",
        f"Execution State: {state.get('execution_state_label')}",
        f"Last Completed Task: {last}",
        f"Next Task: {nxt.get('id') if isinstance(nxt, dict) else nxt}",
        f"Log: {log_path}",
        f"Status Command: reproctl status --project {cfg['project_root']}",
        f"Stop Command: reproctl stop --project {cfg['project_root']}",
    ]
    print("\n".join(out))


def _print_failure(
    stage: str, code: int, reason: str, related_file: str, fix: str, log_path: str | None = None
) -> None:
    print("Repro Agent FAILED", file=sys.stderr)
    print(f"  Stage:        {stage}", file=sys.stderr)
    print(f"  Error Number: {code}", file=sys.stderr)
    print(f"  Reason:       {reason}", file=sys.stderr)
    print(f"  Related File: {related_file}", file=sys.stderr)
    print(f"  Suggested Fix: {fix}", file=sys.stderr)
    if log_path:
        print(f"  Full Log:     {log_path}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────
# Subcommand implementations
# ──────────────────────────────────────────────────────────────────────


def cmd_start(args: argparse.Namespace) -> int:
    plugin = plugin_root()
    project = Path(args.project).resolve() if args.project else None
    plan = Path(args.plan).resolve() if args.plan else None

    if not project or not project.exists():
        _print_failure(
            "DISCOVER",
            EXIT_BAD_CONFIG,
            "missing or nonexistent --project",
            str(args.project),
            "pass --project <PROJECT_ROOT> with an existing directory",
        )
        return EXIT_BAD_CONFIG

    # Bootstrap the project layout
    layout = _sm.bootstrap_exec_layout(project)

    # Start logger inside .repro/startup/startup.log
    log_path = layout["startup"] / "startup.log"
    log = _log.get_logger("reproctl.startup", log_file=log_path, level=args.log_level)

    cfg = _config.resolve(
        project_root=project,
        plan_path=plan or Path(""),
        cli={
            "mode": args.mode or "",
            "expected_cuda": args.expected_cuda or "",
            "log_level": args.log_level or "",
        },
    )

    # R3F-6 --self-test: run doctor + plan validation in isolation, write the
    # unified startup_verification_report.json, and exit 0 without acquiring the
    # lock or claiming any tasks. This is safe to run on any project.
    if getattr(args, "self_test", False):
        return _cmd_self_test(project, plan, cfg, layout, args.log_level)

    if args.mode not in VALID_MODES:
        _print_failure(
            "CONFIG",
            EXIT_BAD_CONFIG,
            f"invalid --mode: {args.mode!r}",
            "scripts/startup/cli.py",
            f"valid modes: {', '.join(VALID_MODES)}",
        )
        return EXIT_BAD_CONFIG

    # BOOTSTRAP
    boot = _sm.bootstrap(plugin_root=plugin, project_root=project, mode=args.mode)

    # DISCOVER
    if plan is None or not plan.exists():
        _print_failure(
            "DISCOVER",
            EXIT_INVALID_PLAN,
            "missing --plan or plan does not exist",
            str(plan) if plan else "(not provided)",
            "pass --plan <PLAN_PATH> with a YAML-frontmatter plan",
            log_path=str(log_path),
        )
        return EXIT_INVALID_PLAN

    disc = _sm.discover(project_root=project, plan_path=plan)

    # PREFLIGHT (doctor)
    pf = _sm.preflight(
        project_root=project, plan_path=plan, expected_cuda=cfg.get("expected_cuda") or None
    )
    doctor_report = pf["report"]
    (layout["startup"] / "doctor_report.json").write_text(
        json.dumps(doctor_report, indent=2), encoding="utf-8"
    )

    if doctor_report["overall"] == "FAIL":
        # Mandatory FAIL in doctor blocks start (per spec).
        failed = [c for c in doctor_report["checks"] if c["status"] == "FAIL"]
        _print_failure(
            "PREFLIGHT",
            EXIT_DOCTOR_FAIL,
            f"{len(failed)} mandatory doctor check(s) failed: "
            + ", ".join(c["name"] for c in failed),
            str(plan),
            "see doctor_report.json for per-check details",
            log_path=str(log_path),
        )
        return EXIT_DOCTOR_FAIL

    # STATE_CHECK
    sc = _sm.state_check(project_root=project)
    if sc["corrupt"]:
        _print_failure(
            "STATE_CHECK",
            EXIT_RESUME_FAILED,
            "execution_state.json is corrupt",
            str(project / ".repro" / "execution" / "execution_state.json"),
            "remove the corrupt state file or restore from checkpoints",
            log_path=str(log_path),
        )
        return EXIT_RESUME_FAILED

    exec_dir = project / ".repro" / "execution"
    es_path = exec_dir / "execution_state.json"
    if es_path.exists():
        try:
            state = json.loads(es_path.read_text())
            # Resume-required guard: do not silently re-claim when the project
            # was interrupted mid-task. Caller must use `reproctl resume`.
            if state.get("interrupted") is True and state.get("current_task"):
                print(
                    f"[startup] execution_state.interrupted=True with "
                    f"current_task={state.get('current_task')!r}; refusing to "
                    f"re-claim. Run `reproctl resume --project <root>`.",
                    file=sys.stderr,
                )
                return EXIT_RESUME_FAILED
        except Exception:
            state = None
    else:
        state = None

    # LOCK (only if not dry-run)
    # PLAN VALIDATION (canonical — R3F-6)
    # Use the canonical plan_schema module for full schema validation (mode,
    # dependency cycles, acceptance_tests, non_evidentiary, etc.) with a
    # legacy-fallback for non-frontmatter plans used in tests.
    plan_errors: list[str] = []
    plan_hash = ""
    try:
        plan_schema_obj = _plan_schema.load_plan(plan)
        plan_hash = plan_schema_obj._canonical_sha256 or _sha256_text(plan)
    except SystemExit:
        # Non-frontmatter legacy plan — use migrate_legacy_plan
        import json as _json

        try:
            legacy = _json.loads(plan.read_text())
        except Exception:
            import yaml as _yaml

            loaded = _yaml.safe_load(plan.read_text())
            # Handle YAML list of task dicts (e.g. `- id: t1` at file start)
            if isinstance(loaded, list):
                legacy = {"tasks": loaded}
            else:
                legacy = loaded
        if not isinstance(legacy, dict):
            _print_failure(
                "PLAN_SCHEMA",
                EXIT_INVALID_PLAN,
                f"plan is {type(legacy).__name__}, not a mapping",
                str(plan),
                "wrap plan in a YAML mapping (--- ... ---)",
                log_path=str(log_path),
            )
            return EXIT_INVALID_PLAN
        migrated = _plan_schema.migrate_legacy_plan(legacy)
        migrated_obj = _plan_schema._dict_to_plan(
            migrated, plan.read_text().encode("utf-8"), loaded_from=plan
        )
        schema_errors = [
            e
            for e in _plan_schema.validate_plan(migrated_obj)
            if e.field != "tasks" or "circular" not in e.message
        ]
        schema_errors = [
            e for e in schema_errors if not (e.field == "deps" and "unknown task" in e.message)
        ]
        schema_errors = [e for e in schema_errors if not (e.field == "schema_version")]
        if schema_errors:
            plan_errors = [str(e) for e in schema_errors]
        else:
            plan_hash = _sha256_text(plan)
    if plan_errors:
        _print_failure(
            "PLAN_SCHEMA",
            EXIT_INVALID_PLAN,
            "plan validation failed: " + "; ".join(plan_errors),
            str(plan),
            "fix plan schema errors above",
            log_path=str(log_path),
        )
        return EXIT_INVALID_PLAN

    lock_info: dict | None = None
    if not args.dry_run:
        try:
            lock_info = _sm.lock_acquire(
                project_root=project,
                command="start",
                plan_hash=plan_hash,
                plugin_version=boot["plugin_version"],
            )
        except _lock.LockHeld as e:
            _print_failure(
                "LOCK",
                EXIT_ALREADY_RUNNING,
                str(e),
                str(project / ".repro" / "run.lock"),
                "run `reproctl stop --project <root>` or remove the stale lock",
                log_path=str(log_path),
            )
            return EXIT_ALREADY_RUNNING

    # EXECUTE_NEXT (claim ONE safe atomic task)
    if args.dry_run:
        claim = _sm.claim_one(project_root=project, plan_path=plan, dry_run=True)
    else:
        claim = _sm.claim_one(project_root=project, plan_path=plan)

    # READY summary
    gpu_label = _gpu_label()
    es_path = project / ".repro" / "execution" / "execution_state.json"
    es_label = "missing" if not es_path.exists() else "present"

    ready_state = {
        "plugin_version": boot["plugin_version"],
        "git_commit": disc["git_commit"],
        "git_dirty": disc["git_dirty"],
        "gpu_label": gpu_label,
        "execution_state_label": es_label,
        "last_completed_task": _last_completed(es_path),
        "next_task": claim,
        "log_path": str(log_path),
    }

    # Write startup_summary.md
    summary_md = _build_summary_md(
        boot, disc, doctor_report, sc, ready_state, claim, plan_hash, args
    )
    (layout["startup"] / "startup_summary.md").write_text(summary_md, encoding="utf-8")

    # Write startup_state.json
    startup_state = {
        **boot,
        "discover": disc,
        "doctor": {
            "overall": doctor_report["overall"],
            "summary": doctor_report["summary"],
        },
        "state_check": sc,
        "plan_hash": plan_hash,
        "dry_run": args.dry_run,
        "lock_acquired": bool(lock_info),
        "next_task": claim,
        "started_at": boot["started_at"],
        "completed_at": _now(),
    }
    (layout["startup"] / "startup_state.json").write_text(
        json.dumps(startup_state, indent=2), encoding="utf-8"
    )

    # Cursor / shell stdout summary
    _print_success_summary({**ready_state, "execution_state_label": es_label}, cfg)

    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    plugin = plugin_root()
    project = Path(args.project).resolve() if args.project else None
    if not project or not project.exists():
        _print_failure(
            "DOCTOR",
            EXIT_BAD_CONFIG,
            "missing or nonexistent --project",
            str(args.project),
            "pass --project <PROJECT_ROOT>",
        )
        return EXIT_BAD_CONFIG
    plan = Path(args.plan).resolve() if args.plan else None
    if plan is not None and not plan.exists():
        plan = None
    report = _doctor.run(
        project_root=project, plan_path=plan, expected_cuda=args.expected_cuda or None
    )
    out_path = project / ".repro" / "startup" / "doctor_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return EXIT_OK if report["overall"] != "FAIL" else EXIT_DOCTOR_FAIL


def cmd_status(args: argparse.Namespace) -> int:
    plugin = plugin_root()
    project = Path(args.project).resolve() if args.project else None
    if not project or not project.exists():
        _print_failure(
            "STATUS",
            EXIT_BAD_CONFIG,
            "missing or nonexistent --project",
            str(args.project),
            "pass --project <PROJECT_ROOT>",
        )
        return EXIT_BAD_CONFIG

    es_path = project / ".repro" / "execution" / "execution_state.json"
    state = {}
    if es_path.exists():
        try:
            state = json.loads(es_path.read_text())
        except Exception:
            state = {}

    lock_path = project / ".repro" / "run.lock"
    lock_info = _lock.inspect(lock_path)

    print(
        json.dumps(
            {
                "project_root": str(project),
                "plugin_version": __version__,
                "execution_state": state,
                "lock": lock_info,
                "checked_at": _now(),
            },
            indent=2,
        )
    )
    return EXIT_OK


def cmd_resume(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve() if args.project else None
    if not project or not project.exists():
        _print_failure(
            "RESUME",
            EXIT_BAD_CONFIG,
            "missing or nonexistent --project",
            str(args.project),
            "pass --project <PROJECT_ROOT>",
        )
        return EXIT_BAD_CONFIG

    es_path = project / ".repro" / "execution" / "execution_state.json"
    if es_path.exists():
        try:
            state = json.loads(es_path.read_text())
            plan = Path(state.get("plan_path", ""))
        except Exception:
            plan = None
    else:
        plan = None

    if plan is None or not plan.exists():
        _print_failure(
            "RESUME",
            EXIT_RESUME_FAILED,
            "no plan recorded in execution_state; cannot resume",
            str(es_path),
            "re-run `reproctl start --plan <PLAN_PATH>`",
            log_path=str(project / ".repro" / "startup" / "startup.log"),
        )
        return EXIT_RESUME_FAILED

    # Re-acquire the lock to fence the resumed project
    try:
        plan_hash = _plan_legacy.validate(plan)
        _lock.acquire(
            project / ".repro" / "run.lock",
            command="resume",
            plan_hash=plan_hash,
            project_root=str(project),
            plugin_version=__version__,
        )
    except _lock.LockHeld as e:
        _print_failure(
            "RESUME",
            EXIT_ALREADY_RUNNING,
            str(e),
            str(project / ".repro" / "run.lock"),
            "run `reproctl stop` first",
        )
        return EXIT_ALREADY_RUNNING

    try:
        summary = _recovery.run(project_root=project, plan_path=plan)
    except SystemExit as e:
        return int(e.code)
    print(json.dumps(summary, indent=2))
    return EXIT_OK


def cmd_stop(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve() if args.project else None
    if not project or not project.exists():
        _print_failure(
            "STOP",
            EXIT_BAD_CONFIG,
            "missing or nonexistent --project",
            str(args.project),
            "pass --project <PROJECT_ROOT>",
        )
        return EXIT_BAD_CONFIG
    out = _stop.run(project_root=project, force=getattr(args, "force", False))
    print(json.dumps(out, indent=2))
    if not out.get("lock_cleared"):
        _print_failure(
            "STOP",
            EXIT_INTERNAL,
            "lock was not cleared after stop",
            str(project / ".repro" / "run.lock"),
            "remove the lock file manually",
        )
        return EXIT_INTERNAL
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify the startup evidence chain (state files + lock + plan hash)."""
    project = Path(args.project).resolve() if args.project else None
    if not project or not project.exists():
        _print_failure(
            "VERIFY",
            EXIT_BAD_CONFIG,
            "missing or nonexistent --project",
            str(args.project),
            "pass --project <PROJECT_ROOT>",
        )
        return EXIT_BAD_CONFIG

    results = []
    # 1. startup_state.json present and valid
    ss = project / ".repro" / "startup" / "startup_state.json"
    if not ss.exists():
        results.append(
            {"check": "startup_state", "status": "FAIL", "message": "missing startup_state.json"}
        )
    else:
        try:
            json.loads(ss.read_text())
            results.append({"check": "startup_state", "status": "PASS"})
        except Exception as e:
            results.append({"check": "startup_state", "status": "FAIL", "message": str(e)})

    # 2. doctor_report.json present
    dr = project / ".repro" / "startup" / "doctor_report.json"
    results.append(
        {
            "check": "doctor_report",
            "status": "PASS" if dr.exists() else "FAIL",
            "message": "" if dr.exists() else "missing doctor_report.json",
        }
    )

    # 3. execution_state.json integrity
    es = project / ".repro" / "execution" / "execution_state.json"
    if not es.exists():
        results.append({"check": "execution_state", "status": "FAIL", "message": "missing"})
    else:
        try:
            json.loads(es.read_text())
            results.append({"check": "execution_state", "status": "PASS"})
        except Exception as e:
            results.append({"check": "execution_state", "status": "FAIL", "message": str(e)})

    # 4. plan_hash stable
    es_state = {}
    if es.exists():
        try:
            es_state = json.loads(es.read_text())
        except Exception:
            pass
    if es_state.get("plan_hash"):
        # Plan path needs to be in state; if not, skip
        plan_path = Path(es_state.get("plan_path", ""))
        if plan_path.exists():
            from startup import plan_validate as _pv

            cur = _pv.validate(plan_path)
            results.append(
                {
                    "check": "plan_hash",
                    "status": "PASS" if cur == es_state["plan_hash"] else "FAIL",
                    "message": f"current={cur[:12]} recorded={es_state['plan_hash'][:12]}",
                }
            )
        else:
            results.append(
                {"check": "plan_hash", "status": "SKIP", "message": "no plan_path in state"}
            )
    else:
        results.append({"check": "plan_hash", "status": "SKIP", "message": "no plan_hash recorded"})

    overall = "PASS" if all(r["status"] in ("PASS", "SKIP") for r in results) else "FAIL"
    print(json.dumps({"overall": overall, "checks": results}, indent=2))
    return EXIT_OK if overall == "PASS" else EXIT_RESUME_FAILED


def cmd_watchdog(args: argparse.Namespace) -> int:
    """Single-pass watchdog inspection.

    Reports running tasks, their pids, heartbeats, and log freshness.
    Exits 0 on success (any state), 1 on fatal error.
    """
    project = Path(args.project).resolve() if args.project else None
    if not project or not project.exists():
        print(
            json.dumps(
                {
                    "command": "watchdog",
                    "status": "ERROR",
                    "code": EXIT_BAD_CONFIG,
                    "message": "missing or nonexistent --project",
                    "project": str(args.project),
                }
            )
        )
        return EXIT_BAD_CONFIG

    # Open the canonical SQLite store if present
    db_path = project / ".repro" / "execution" / "state.sqlite3"
    summary: dict[str, Any] = {
        "command": "watchdog",
        "status": "OK",
        "project": str(project),
        "db_present": db_path.exists(),
        "tasks": [],
    }
    if db_path.exists():
        try:
            # Lazy import so the watchdog command doesn't require torch
            import sqlite3

            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
            try:
                rows = conn.execute(
                    "SELECT id, state, pid, log_path, started_at, updated_at "
                    "FROM tasks ORDER BY rowid"
                ).fetchall()
            finally:
                conn.close()
            for r in rows:
                summary["tasks"].append(
                    {
                        "id": r[0],
                        "state": r[1],
                        "pid": r[2],
                        "log_path": r[3],
                        "started_at": r[4],
                        "updated_at": r[5],
                    }
                )
        except Exception as e:
            summary["status"] = "DEGRADED"
            summary["error"] = repr(e)
    print(json.dumps(summary, indent=2))
    return EXIT_OK


def cmd_version(args: argparse.Namespace) -> int:
    plugin = plugin_root()
    manifest = plugin / ".cursor-plugin" / "plugin.json"
    plugin_version = "unknown"
    try:
        plugin_version = json.loads(manifest.read_text()).get("version", "unknown")
    except Exception:
        pass
    print(
        json.dumps(
            {
                "reproctl": __version__,
                "plugin": plugin_version,
                "plugin_root": str(plugin),
                "platform": platform_tag(),
            },
            indent=2,
        )
    )
    return EXIT_OK


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _gpu_label() -> str:
    if os.environ.get("REPRO_FAKE_GPU") == "0":
        return "none"
    try:
        import torch  # type: ignore

        if not torch.cuda.is_available():
            return "none"
        return f"{torch.cuda.device_count()}× {torch.cuda.get_device_name(0)}"
    except ImportError:
        return "unknown (torch missing)"
    except Exception as e:
        return f"probe-failed ({e})"


def _last_completed(es_path: Path) -> str | None:
    if not es_path.exists():
        return None
    try:
        s = json.loads(es_path.read_text())
        return s.get("last_completed_task")
    except Exception:
        return None


def _build_summary_md(
    boot: dict,
    disc: dict,
    doctor: dict,
    sc: dict,
    ready_state: dict,
    claim: dict,
    plan_hash: str,
    args: argparse.Namespace,
) -> str:
    nxt = claim.get("id") if isinstance(claim, dict) else None
    last = ready_state.get("last_completed_task") or "(none)"
    dry = " (DRY RUN)" if args.dry_run else ""
    lines = [
        f"# Repro Agent Startup Summary{dry}",
        "",
        f"- Plugin Version: `{ready_state['plugin_version']}`",
        f"- Project: `{boot['project_root']}`",
        f"- Mode: `{boot['mode']}`",
        f"- Started: `{boot['started_at']}`",
        f"- Git Commit: `{disc['git_commit']}`",
        f"- Git Dirty: **{disc['git_dirty']}**"
        + (" (uncommitted changes present)" if disc["git_dirty"] else ""),
        f"- GPU: {ready_state['gpu_label']}",
        f"- Plan Hash: `{plan_hash[:16]}...`",
        f"- Execution State: {ready_state['execution_state_label']}",
        f"- Last Completed Task: {last}",
        f"- Next Task: {nxt or '(none)'}",
        f"- Doctor Overall: **{doctor['overall']}** "
        f"(PASS={doctor['summary'].get('PASS', 0)}, "
        f"WARNING={doctor['summary'].get('WARNING', 0)}, "
        f"FAIL={doctor['summary'].get('FAIL', 0)})",
        "",
        "## Doctor Checks",
        "",
        "| Check | Status | Message |",
        "|---|---|---|",
    ]
    for c in doctor["checks"]:
        lines.append(f"| {c['name']} | {c['status']} | {c.get('message', '')} |")
    lines.extend(
        [
            "",
            "## Status / Stop Commands",
            "",
            "```",
            f"reproctl status --project {boot['project_root']}",
            f"reproctl stop   --project {boot['project_root']}",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reproctl",
        description=("Deep Learning Paper Reproduction Controller — unified startup system"),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common_project(p: argparse.ArgumentParser) -> None:
        p.add_argument("--project", help="project root path")
        p.add_argument("--log-level", default="", choices=["", "DEBUG", "INFO", "WARNING", "ERROR"])

    p = sub.add_parser("start", help="Bootstrap & start the project")
    add_common_project_project = add_common_project
    add_common_project_project(p)
    p.add_argument("--plan", help="path to the plan file")
    p.add_argument("--mode", choices=list(VALID_MODES), default="strict")
    p.add_argument(
        "--dry-run", action="store_true", help="check-only, do not acquire lock or claim tasks"
    )
    p.add_argument(
        "--self-test",
        dest="self_test",
        action="store_true",
        help="R3F-6: run doctor + plan validation in isolation, write "
        "startup_verification_report.json, exit 0. Does NOT acquire "
        "lock or claim tasks.",
    )
    p.add_argument("--expected-cuda", default="", help="expected CUDA version (e.g. 12.0)")

    p = sub.add_parser("doctor", help="Run preflight checks (no state mutation)")
    add_common_project(p)
    p.add_argument("--plan", default="")
    p.add_argument("--expected-cuda", default="")

    p = sub.add_parser("status", help="Show project state, lock, plan hash")
    add_common_project(p)

    p = sub.add_parser("resume", help="Resume an interrupted project")
    add_common_project(p)

    p = sub.add_parser("stop", help="Stop gracefully and clear the lock")
    add_common_project(p)
    p.add_argument(
        "--force",
        action="store_true",
        help="R3F-8: after SIGTERM, wait 2s then send SIGKILL to "
        "unresponsive processes. Also verifies lock was cleared.",
    )

    p = sub.add_parser("verify", help="Verify the startup evidence chain")
    add_common_project(p)

    p = sub.add_parser("watchdog", help="Inspect running tasks and report heartbeat / log status")
    add_common_project(p)
    p.add_argument("--once", action="store_true", help="single-pass inspection instead of one loop")

    sub.add_parser("version", help="Print plugin + CLI version")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cmds = {
        "start": cmd_start,
        "doctor": cmd_doctor,
        "status": cmd_status,
        "resume": cmd_resume,
        "stop": cmd_stop,
        "verify": cmd_verify,
        "watchdog": cmd_watchdog,
        "version": cmd_version,
    }
    return cmds[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
