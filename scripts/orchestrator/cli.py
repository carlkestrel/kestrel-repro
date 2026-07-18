"""Command-line entry points for the continuous auto-execution controller."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

THIS = Path(__file__).resolve()
PACKAGE_PARENT = THIS.parent.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from orchestrator.controller import (  # noqa: E402
    BLOCKED,
    COMPLETE,
    PAUSED,
    STOPPED,
    WAITING_APPROVAL,
    Controller,
    load_plan,
)
from orchestrator.policy_engine import PolicyEngine  # noqa: E402
from orchestrator.process_manager import ProcessManager  # noqa: E402
from orchestrator.state_store import StateStore  # noqa: E402

EXIT_OK = 0
EXIT_BAD_CONFIG = 2
EXIT_NOT_FOUND = 3
EXIT_BLOCKED = 7
EXIT_INTERNAL = 10


def _resolve_project(project: str | None) -> Path:
    if not project:
        raise SystemExit(EXIT_BAD_CONFIG)
    path = Path(project).resolve()
    if not path.exists():
        raise SystemExit(EXIT_BAD_CONFIG)
    return path


def _store(project: Path) -> StateStore:
    return StateStore(project)


def _output(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def cmd_run(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    plan_path = Path(args.plan).resolve()
    controller = Controller(
        project_root=project,
        plan_path=plan_path,
        mode=args.mode,
        automation=args.automation,
        policy_path=args.policy,
        resume=args.resume,
    )
    result = controller.run()
    if result["status"] == COMPLETE:
        return EXIT_OK
    if result["status"] in {PAUSED, STOPPED, WAITING_APPROVAL}:
        return EXIT_OK
    if result["status"] == BLOCKED:
        _output(result)
        return EXIT_BLOCKED
    _output(result)
    return EXIT_INTERNAL


def cmd_pause(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    store.set_control_state("PAUSED")
    _output({"status": "PAUSED", "project_root": str(project)})
    return EXIT_OK


def cmd_continue(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    store.set_control_state("RUNNING")
    _output({"status": "RUNNING", "project_root": str(project)})
    return EXIT_OK


def cmd_stop(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    store.set_control_state("STOPPED")
    manager = ProcessManager()
    watchdog_terminated: list[int] = []
    for task in store.list_tasks({"RUNNING"}):
        pid = task.get("pid")
        if pid and manager.is_alive(pid):
            manager.terminate(int(pid))
            watchdog_terminated.append(int(pid))
    snapshot = store.export_snapshots()
    _output(
        {
            "status": "STOPPED",
            "project_root": str(project),
            "terminated": watchdog_terminated,
            "snapshots": snapshot,
        }
    )
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    _output(store.status_summary())
    return EXIT_OK


def cmd_events(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    events = store.events(after_seq=args.after_seq, limit=args.limit)
    _output({"events": events, "count": len(events)})
    return EXIT_OK


def cmd_next(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    plan = load_plan(args.plan)
    store.initialize_plan(plan, args.plan)
    from orchestrator.scheduler import Scheduler  # local import to avoid cycles

    scheduler = Scheduler(store)
    scheduler.refresh()
    nxt = scheduler.next_task()
    if nxt is None:
        _output({"next": None, "reason": scheduler.deadlock_reason() or "no ready tasks"})
        return EXIT_OK
    decision, reason = PolicyEngine(project, args.policy).evaluate(nxt)
    _output({"next": nxt["id"], "policy": {"decision": decision, "reason": reason}})
    return EXIT_OK


def _resolve_approval(store: StateStore, identifier: str) -> dict:
    identifier = identifier.strip()
    if identifier.startswith("apr_"):
        return store.decide_approval(identifier, "APPROVED" if False else "APPROVED")
    pending = store.pending_approvals()
    match = next((a for a in pending if a["task_id"] == identifier), None)
    if match is None:
        raise SystemExit(EXIT_NOT_FOUND)
    return store.decide_approval(match["approval_id"], "APPROVED")


def cmd_approve(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    result = _resolve_approval(store, args.approval_id)
    _output({"approval": result, "project_root": str(project)})
    return EXIT_OK


def cmd_reject(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    pending = store.pending_approvals()
    target = (
        next((a for a in pending if a["approval_id"] == args.approval_id), None)
        if args.approval_id.startswith("apr_")
        else next((a for a in pending if a["task_id"] == args.approval_id), None)
    )
    if target is None:
        raise SystemExit(EXIT_NOT_FOUND)
    result = store.decide_approval(target["approval_id"], "REJECTED", args.reason or "")
    _output({"approval": result, "project_root": str(project)})
    return EXIT_OK


def _pid_path(project: Path) -> Path:
    return project / ".repro" / "execution" / "controller.pid"


def _heartbeat_path(project: Path) -> Path:
    return project / ".repro" / "execution" / "controller.heartbeat"


def _read_pid(project: Path) -> int | None:
    path = _pid_path(project)
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except ValueError:
        return None


def cmd_daemon(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    if args.action == "start":
        if not args.plan:
            raise SystemExit(EXIT_BAD_CONFIG)
        return _daemon_start(project, args)
    if args.action == "status":
        return _daemon_status(project)
    if args.action == "stop":
        return _daemon_stop(project)
    raise SystemExit(EXIT_BAD_CONFIG)


def _daemon_start(project: Path, args: argparse.Namespace) -> int:
    existing = _read_pid(project)
    if existing and ProcessManager().is_alive(existing):
        _output({"status": "ALREADY_RUNNING", "pid": existing})
        return EXIT_OK
    plan_path = Path(args.plan).resolve()
    pid_path = _pid_path(project)
    log_path = project / ".repro" / "execution" / "daemon.log"
    # D2 fix: make sure the log directory exists BEFORE Popen opens the file.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(THIS),
        "run",
        "--project",
        str(project),
        "--plan",
        str(plan_path),
        "--automation",
        args.automation,
    ]
    if args.mode:
        cmd.extend(["--mode", args.mode])
    cmd.append("--daemon-child")
    env = os.environ.copy()
    env["REPRO_ORCHESTRATOR_DAEMON"] = "1"
    proc = subprocess.Popen(
        cmd,
        cwd=str(project),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_path.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = pid_path.with_suffix(".tmp")
    tmp.write_text(str(proc.pid), encoding="utf-8")
    os.replace(tmp, pid_path)
    # D3 fix: clean up the pid file if the detached child exits almost
    # immediately (e.g. argparse rejected the argv). We give it a short
    # window to reach a steady state.
    manager = ProcessManager()
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if manager.is_alive(proc.pid):
            break
        time.sleep(0.05)
    else:  # pragma: no cover - only triggers on immediate crash
        _output({"status": "START_FAILED", "pid": proc.pid})
        return EXIT_INTERNAL
    if manager.is_alive(proc.pid):
        _output(
            {"status": "STARTED", "pid": proc.pid, "log": str(log_path), "plan": str(plan_path)}
        )
        return EXIT_OK
    # D3 fix: detach failed; clean up stale artifacts.
    _pid_path(project).unlink(missing_ok=True)
    _output({"status": "START_FAILED", "pid": proc.pid, "log": str(log_path)})
    return EXIT_INTERNAL


def _daemon_status(project: Path) -> int:
    pid = _read_pid(project)
    info = {"project_root": str(project), "pid": pid}
    if pid is None:
        info["status"] = "STOPPED"
    elif ProcessManager().is_alive(pid):
        info["status"] = "RUNNING"
    else:
        info["status"] = "STALE"
    heartbeat = _heartbeat_path(project)
    if heartbeat.exists():
        try:
            info["heartbeat"] = json.loads(heartbeat.read_text())
        except json.JSONDecodeError:
            info["heartbeat"] = "corrupt"
    else:
        info["heartbeat"] = None
    _output(info)
    return EXIT_OK


def _daemon_stop(project: Path) -> int:
    pid = _read_pid(project)
    if pid is None:
        _output({"status": "STOPPED", "project_root": str(project)})
        return EXIT_OK
    manager = ProcessManager()
    worker_pids: list[int] = []
    worker_results: list[dict] = []
    try:
        store = _store(project)
        for task in store.list_tasks({"RUNNING"}):
            worker_pid = task.get("pid")
            if worker_pid and manager.is_alive(int(worker_pid)):
                worker_pids.append(int(worker_pid))
        # Terminate workers first so the SQLite RUNNING rows don't survive.
        for worker_pid in worker_pids:
            terminated = manager.terminate(int(worker_pid), grace_seconds=2.0)
            worker_results.append({"pid": worker_pid, "terminated": bool(terminated)})
            try:
                _store(project).transition(
                    task_id=task["id"],
                    new_status="READY",
                    expected="RUNNING",
                    fields={
                        "pid": None,
                        "failure_reason": "daemon stop",
                        "finished_at": utc_now_iso(),
                    },
                    event_type="TASK_DAEMON_STOPPED",
                )
            except Exception:
                # last-resort fallback: force the row to FAIL so it can't linger.
                try:
                    _store(project).transition(
                        task_id=task["id"],
                        new_status="FAILED",
                        expected="RUNNING",
                        fields={
                            "pid": None,
                            "failure_reason": "daemon stop",
                            "finished_at": utc_now_iso(),
                        },
                        event_type="TASK_DAEMON_STOPPED",
                    )
                except Exception:
                    pass
    except Exception as exc:
        worker_results.append({"error": str(exc)})
    if not manager.is_alive(pid):
        _pid_path(project).unlink(missing_ok=True)
        _heartbeat_path(project).unlink(missing_ok=True)
        _output(
            {
                "status": "STOPPED",
                "project_root": str(project),
                "pid": pid,
                "workers": worker_results,
            }
        )
        return EXIT_OK
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not manager.is_alive(pid):
            break
        time.sleep(0.1)
    if manager.is_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    _pid_path(project).unlink(missing_ok=True)
    _heartbeat_path(project).unlink(missing_ok=True)
    _output(
        {"status": "STOPPED", "project_root": str(project), "pid": pid, "workers": worker_results}
    )
    return EXIT_OK


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def cmd_migrate(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    from orchestrator import migrate as migrate_module

    dry_run = getattr(args, "check_only", False)
    result = migrate_module.migrate(
        store,
        target=getattr(args, "target_version", None),
        dry_run=dry_run,
    )
    _output(result)
    return EXIT_OK if result["status"] in ("already_current", "migrated", "dry_run") else 1


def cmd_backup(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    from orchestrator import backup as backup_module

    result = backup_module.backup_project(
        project,
        output_dir=Path(args.output_dir) if getattr(args, "output_dir", None) else None,
        include_checkpoints=getattr(args, "include_checkpoints", False),
    )
    _output(result)
    return EXIT_OK


def cmd_restore(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    from orchestrator import backup as backup_module

    result = backup_module.restore_project(
        project,
        snapshot_id=args.snapshot,
        output_dir=Path(args.output_dir) if getattr(args, "output_dir", None) else None,
    )
    _output(result)
    return EXIT_OK if result["status"] == "restored" else 1


def cmd_integrity_check(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    from orchestrator import backup as backup_module

    result = backup_module.integrity_check(project)
    _output(result)
    print(f"\nIntegrity: {result['summary']}")
    print(f"Checks passed: {len(result['checks_passed'])}")
    if result["warnings"]:
        print(f"Warnings: {len(result['warnings'])}")
    if result["issues"]:
        print(f"Issues: {len(result['issues'])}")
        for issue in result["issues"]:
            print(f"  - {issue}")
    return EXIT_OK if result["summary"] == "PASSED" else 1


def cmd_rollback_version(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    store = _store(project)
    from orchestrator import migrate as migrate_module

    result = migrate_module.rollback(Path(args.backup_dir), store)
    _output(result)
    return EXIT_OK if result["status"] == "restored" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reproctl orchestrator", description="Continuous auto-execution controller"
    )
    sub = parser.add_subparsers(dest="orch_command", required=True)

    p_run = sub.add_parser("run", help="Run the persistent controller loop")
    p_run.add_argument("--project", required=True)
    p_run.add_argument("--plan", required=True)
    p_run.add_argument("--mode", default=None)
    p_run.add_argument("--automation", default="safe-auto")
    p_run.add_argument("--policy", default=None)
    p_run.add_argument("--resume", action="store_true")
    p_run.add_argument("--until", default="blocked-or-complete")
    # D3 fix: the daemon-spawned re-exec passes this flag so its argv
    # doesn't trip argparse. The flag itself is a no-op (daemon vs.
    # foreground distinction is already conveyed via REPRO_ORCHESTRATOR_DAEMON
    # for any future code that needs to differentiate). Accepting it here
    # also lets the daemon start path treat argv uniformly.
    p_run.add_argument("--daemon-child", action="store_true", help=argparse.SUPPRESS)

    for name, helptext in (
        ("pause", "pause the orchestrator"),
        ("continue", "continue the orchestrator"),
        ("status", "show status"),
        ("next", "show next task"),
        ("stop", "stop the orchestrator"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--project", required=True)
        if name == "next":
            p.add_argument("--plan", required=True)
            p.add_argument("--policy", default=None)

    p_events = sub.add_parser("events", help="Stream the event log")
    p_events.add_argument("--project", required=True)
    p_events.add_argument("--limit", type=int, default=200)
    p_events.add_argument("--after-seq", type=int, default=0)

    p_appr = sub.add_parser("approve", help="Approve a pending task")
    p_appr.add_argument("--project", required=True)
    p_appr.add_argument("approval_id", help="approval id (apr_...) or task id")

    p_rej = sub.add_parser("reject", help="Reject a pending task")
    p_rej.add_argument("--project", required=True)
    p_rej.add_argument("approval_id")
    p_rej.add_argument("--reason", default="")

    p_daemon = sub.add_parser("daemon", help="Control the detached daemon")
    p_daemon.add_argument("--project", required=True)
    p_daemon.add_argument("action", choices=["start", "status", "stop"])
    p_daemon.add_argument("--plan", default=None)
    p_daemon.add_argument("--automation", default="safe-auto")
    p_daemon.add_argument("--mode", default=None)
    p_daemon.add_argument("--policy", default=None)

    # migrate
    p_migrate = sub.add_parser("migrate", help="Migrate state to current schema version")
    p_migrate.add_argument("--project", required=True)
    p_migrate.add_argument("--check-only", action="store_true")
    p_migrate.add_argument("--target-version")

    # backup
    p_backup = sub.add_parser("backup", help="Create a backup snapshot")
    p_backup.add_argument("--project", required=True)
    p_backup.add_argument("--include-checkpoints", action="store_true")
    p_backup.add_argument("--output-dir")

    # restore
    p_restore = sub.add_parser("restore", help="Restore from a backup snapshot")
    p_restore.add_argument("--project", required=True)
    p_restore.add_argument("--snapshot", required=True)
    p_restore.add_argument("--output-dir")

    # integrity-check
    p_ic = sub.add_parser("integrity-check", help="Run integrity checks")
    p_ic.add_argument("--project", required=True)

    # rollback-version
    p_rb = sub.add_parser("rollback-version", help="Rollback to a backup")
    p_rb.add_argument("--project", required=True)
    p_rb.add_argument("--backup-dir", required=True)

    return parser


HANDLERS = {
    "run": cmd_run,
    "pause": cmd_pause,
    "continue": cmd_continue,
    "stop": cmd_stop,
    "status": cmd_status,
    "events": cmd_events,
    "next": cmd_next,
    "approve": cmd_approve,
    "reject": cmd_reject,
    "daemon": cmd_daemon,
    "migrate": cmd_migrate,
    "backup": cmd_backup,
    "restore": cmd_restore,
    "integrity-check": cmd_integrity_check,
    "rollback-version": cmd_rollback_version,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = HANDLERS[args.orch_command]
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())
