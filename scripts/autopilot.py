#!/usr/bin/env python3
"""
Autopilot - NORA-style continuous execution controller for dl-paper-repro.

This module provides a unified entry point that wraps the orchestrator
functionality with NORA-style commands for continuous paper reproduction.

Usage:
    python autopilot.py run --project . --until blocked-or-complete
    python autopilot.py status --project .
    python autopilot.py recover --project .
    python autopilot.py takeover --project .

Exit codes:
    0  - Success (COMPLETE, PAUSED, STOPPED)
    3  - Doctor check failed
    7  - BLOCKED
    10 - Internal error
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Path setup
# ──────────────────────────────────────────────────────────────────────────────

THIS = Path(__file__).resolve()
PACKAGE_ROOT = THIS.parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from scripts.orchestrator.controller import (
    BLOCKED,
    COMPLETE,
    PAUSED,
    STOPPED,
    WAITING_APPROVAL,
    Controller,
)
from scripts.orchestrator.process_manager import ProcessManager
from scripts.orchestrator.state_store import StateStore

# ──────────────────────────────────────────────────────────────────────────────
# Exit codes
# ──────────────────────────────────────────────────────────────────────────────

EXIT_OK = 0
EXIT_DOCTOR_FAIL = 3
EXIT_NOT_FOUND = 4
EXIT_BLOCKED = 7
EXIT_WAITING_APPROVAL = 8
EXIT_RESUME_FAILED = 8
EXIT_STOPPED = 9
EXIT_INTERNAL = 10

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

AUTOPILOT_VERSION = "1.0.0"
DEFAULT_PLAN_PATH = ".repro/plan.yaml"
DEFAULT_POLICY_PATH = ".repro/automation_policy.yaml"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_project(project: str | None) -> Path:
    """Resolve and validate project root."""
    if not project:
        raise SystemExit(EXIT_INTERNAL)
    path = Path(project).resolve()
    if not path.exists():
        print(f"ERROR: Project not found: {path}", file=sys.stderr)
        raise SystemExit(EXIT_NOT_FOUND)
    return path


def _output(payload: Any, pretty: bool = True) -> None:
    """Print structured output."""
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(json.dumps(payload, default=str))


def _store(project: Path) -> StateStore:
    """Get StateStore instance."""
    return StateStore(project)


def _read_pid(project: Path) -> int | None:
    """Read autopilot PID from file."""
    pid_path = project / ".repro" / "execution" / "autopilot.pid"
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text().strip())
    except ValueError:
        return None


def _write_pid(project: Path, pid: int) -> None:
    """Write autopilot PID to file."""
    pid_path = project / ".repro" / "execution" / "autopilot.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(pid), encoding="utf-8")


def _heartbeat_path(project: Path) -> Path:
    return project / ".repro" / "execution" / "autopilot.heartbeat"


def _heartbeat(project: Path, owner: str, pid: int, detail: dict | None = None) -> None:
    """Write heartbeat to file."""
    hb = _heartbeat_path(project)
    payload = {
        "owner": owner,
        "pid": pid,
        "timestamp": time.time(),
        "utc": _utc_now(),
        "detail": detail or {},
    }
    tmp = hb.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(tmp, hb)


# ──────────────────────────────────────────────────────────────────────────────
# Doctor check
# ──────────────────────────────────────────────────────────────────────────────

def _run_doctor(project: Path) -> dict:
    """Run doctor preflight checks."""
    sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
    from startup.doctor import run as doctor_run
    plan_path = project / DEFAULT_PLAN_PATH
    result = doctor_run(
        project_root=project,
        plan_path=plan_path if plan_path.exists() else None,
    )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot run command
# ──────────────────────────────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> int:
    """
    Run the continuous autopilot loop.
    
    This wraps the orchestrator controller with NORA-style behavior:
    - Continuous execution until blocked or complete
    - Automatic recovery on startup
    - GPU/process monitoring
    - Evidence tracking
    """
    project = _resolve_project(args.project)

    # Doctor check first
    if not args.skip_doctor:
        print("Running preflight checks...")
        doctor_result = _run_doctor(project)
        if doctor_result["overall"] == "FAIL":
            print(f"\nDoctor FAILED: {doctor_result['summary']}")
            print("\nFailed checks:")
            for check in doctor_result["checks"]:
                if check["status"] == "FAIL":
                    print(f"  - {check['name']}: {check['message']}")
            return EXIT_DOCTOR_FAIL
        print(f"Doctor: {doctor_result['summary']}")

    # Find plan
    plan_path = Path(args.plan) if args.plan else project / DEFAULT_PLAN_PATH
    if not plan_path.exists():
        # Try to find any yaml in .repro/
        repro_dir = project / ".repro"
        if repro_dir.exists():
            yaml_files = list(repro_dir.glob("*.yaml")) + list(repro_dir.glob("*.yml"))
            if yaml_files:
                plan_path = yaml_files[0]
        if not plan_path.exists():
            print(f"ERROR: Plan not found. Create {DEFAULT_PLAN_PATH} or use --plan <path>",
                  file=sys.stderr)
            return EXIT_NOT_FOUND

    print(f"Starting autopilot with plan: {plan_path}")
    print(f"Automation mode: {args.automation}")
    print(f"Run until: {args.until}")
    print("-" * 60)

    # Create autopilot lock
    pid_path = project / ".repro" / "execution" / "autopilot.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    existing_pid = _read_pid(project)
    if existing_pid:
        manager = ProcessManager()
        if manager.is_alive(existing_pid):
            print(f"WARNING: Autopilot already running with PID {existing_pid}")
            print("Use 'autopilot.py stop' to stop it first")
            return EXIT_INTERNAL
        else:
            print(f"Cleaning up stale PID file from previous run (PID {existing_pid})")

    _write_pid(project, os.getpid())

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\nReceived shutdown signal, stopping gracefully...")
        store = _store(project)
        store.set_control_state("PAUSED")
        _write_pid(project, 0)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the controller
    try:
        controller = Controller(
            project_root=project,
            plan_path=plan_path,
            mode=args.mode,
            automation=args.automation,
            policy_path=args.policy,
            resume=args.resume,
            poll_interval=args.poll_interval,
        )

        # Write initial heartbeat
        _heartbeat(project, "autopilot", os.getpid(), {
            "plan": str(plan_path),
            "mode": args.mode or "default",
            "automation": args.automation,
        })

        # Run until blocked or complete
        result = controller.run()

        # Handle result
        status = result["status"]
        reason = result.get("reason", "")

        print("\n" + "=" * 60)
        print(f"Autopilot finished: {status}")
        if reason:
            print(f"Reason: {reason}")
        print("=" * 60)

        # Print task summary
        tasks = result.get("tasks", [])
        if tasks:
            counts: dict[str, int] = {}
            for task in tasks:
                st = task.get("status", "UNKNOWN")
                counts[st] = counts.get(st, 0) + 1
            print("\nTask summary:")
            for st, count in sorted(counts.items()):
                print(f"  {st}: {count}")

        # Print recovery info
        recovery = result.get("recovery", {})
        if recovery:
            print("\nRecovery info:")
            for k, v in recovery.items():
                if v:
                    print(f"  {k}: {v}")

        _write_pid(project, 0)

        if status == COMPLETE:
            return EXIT_OK
        elif status in {PAUSED, STOPPED}:
            return EXIT_STOPPED
        elif status == WAITING_APPROVAL:
            return EXIT_WAITING_APPROVAL
        elif status == BLOCKED:
            _output(result)
            return EXIT_BLOCKED
        else:
            return EXIT_INTERNAL

    except Exception as e:
        print(f"ERROR: Autopilot failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        _write_pid(project, 0)
        return EXIT_INTERNAL


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot status command
# ──────────────────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    """Show autopilot status."""
    project = _resolve_project(args.project)
    store = _store(project)

    status = store.status_summary()

    # Add autopilot-specific info
    pid = _read_pid(project)
    if pid:
        manager = ProcessManager()
        alive = manager.is_alive(pid)
        status["autopilot"] = {
            "pid": pid,
            "running": alive,
            "status": "RUNNING" if alive else "STALE",
        }
    else:
        status["autopilot"] = {
            "pid": None,
            "running": False,
            "status": "NOT_RUNNING",
        }

    # Read heartbeat
    hb = _heartbeat_path(project)
    if hb.exists():
        try:
            status["heartbeat"] = json.loads(hb.read_text())
        except json.JSONDecodeError:
            status["heartbeat"] = "corrupt"
    else:
        status["heartbeat"] = None

    # Control state
    control = store.control_state()
    status["control_state"] = control

    _output(status)

    # Print human-readable summary
    print(f"\n{'=' * 60}")
    print(f"Project: {project}")
    print(f"Autopilot: {status['autopilot']['status']}", end="")
    if pid:
        print(f" (PID {pid})", end="")
    print()
    print(f"Control state: {control}")

    counts = status.get("counts", {})
    if counts:
        print("\nTask counts:")
        for st, count in sorted(counts.items()):
            bar = "█" * min(count, 20)
            print(f"  {st:15s}: {count:3d} {bar}")

    pending = status.get("pending_approvals", [])
    if pending:
        print(f"\nPending approvals: {len(pending)}")
        for apr in pending[:5]:
            print(f"  - {apr.get('task_id', 'unknown')}: {apr.get('approval_id', 'unknown')}")

    print("=" * 60)

    return EXIT_OK


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot recover command
# ──────────────────────────────────────────────────────────────────────────────

def cmd_recover(args: argparse.Namespace) -> int:
    """Recover from interrupted state."""
    project = _resolve_project(args.project)

    print("Running recovery...")

    store = _store(project)

    # Check if autopilot is running
    pid = _read_pid(project)
    if pid:
        manager = ProcessManager()
        if manager.is_alive(pid):
            print(f"Autopilot is running with PID {pid}")
            print("Use 'stop' first before recovering")
            return EXIT_INTERNAL

    # Run recovery through the store
    try:
        # Get current state
        status = store.status_summary()
        running_tasks = [t for t in status.get("tasks", []) if t.get("status") == "RUNNING"]

        if not running_tasks:
            print("No running tasks to recover")
        else:
            print(f"\nFound {len(running_tasks)} RUNNING tasks")
            for task in running_tasks:
                print(f"  - {task.get('id')}: PID {task.get('pid')}")

        # Check heartbeats
        hb = _heartbeat_path(project)
        if hb.exists():
            try:
                hb_data = json.loads(hb.read_text())
                age = time.time() - hb_data.get("timestamp", 0)
                print(f"\nLast heartbeat: {age:.1f}s ago")
                if age > 300:
                    print("WARNING: Heartbeat is stale (>5 min)")
            except json.JSONDecodeError:
                print("WARNING: Heartbeat file is corrupt")

        # Run doctor check
        if not args.skip_doctor:
            print("\nRunning preflight checks...")
            doctor_result = _run_doctor(project)
            if doctor_result["overall"] == "FAIL":
                print(f"WARNING: Doctor FAILED - {doctor_result['summary']}")
            else:
                print(f"Doctor: {doctor_result['summary']}")

        # Resume
        print("\nResuming autopilot...")
        args_dict = vars(args)
        args_dict["resume"] = True
        args_dict["skip_doctor"] = True

        return cmd_run(argparse.Namespace(**args_dict))

    except Exception as e:
        print(f"ERROR: Recovery failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return EXIT_INTERNAL


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot pause/stop/continue commands
# ──────────────────────────────────────────────────────────────────────────────

def cmd_pause(args: argparse.Namespace) -> int:
    """Pause the autopilot."""
    project = _resolve_project(args.project)
    store = _store(project)
    store.set_control_state("PAUSED")
    print(f"Autopilot paused: {project}")
    return EXIT_OK


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the autopilot."""
    project = _resolve_project(args.project)
    store = _store(project)
    store.set_control_state("STOPPED")

    # Terminate running tasks
    manager = ProcessManager()
    store = _store(project)
    terminated = []
    for task in store.list_tasks({"RUNNING"}):
        pid = task.get("pid")
        if pid and manager.is_alive(pid):
            manager.terminate(int(pid), grace_seconds=2.0)
            terminated.append(pid)

    _write_pid(project, 0)

    print(f"Autopilot stopped: {project}")
    if terminated:
        print(f"Terminated {len(terminated)} running tasks: {terminated}")

    return EXIT_OK


def cmd_continue(args: argparse.Namespace) -> int:
    """Continue a paused autopilot."""
    project = _resolve_project(args.project)
    store = _store(project)
    control = store.control_state()
    if control == "PAUSED":
        store.set_control_state("RUNNING")
        print(f"Autopilot continued: {project}")
    else:
        print(f"Autopilot is {control}, nothing to continue")
    return EXIT_OK


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot takeover command
# ──────────────────────────────────────────────────────────────────────────────

def cmd_takeover(args: argparse.Namespace) -> int:
    """
    Take over an existing reproduction project.
    
    This command:
    1. Detects the project type (paper repo, existing repro project, etc.)
    2. Reads existing state
    3. Generates/updates task graph
    4. Prepares for autopilot execution
    """
    project = _resolve_project(args.project)

    print(f"Takeover analysis for: {project}")
    print("-" * 60)

    # Detect project type
    project_type = _detect_project_type(project)
    print(f"Detected project type: {project_type}")

    # Check for existing repro state
    repro_dir = project / ".repro"
    has_repro = repro_dir.exists()

    if has_repro:
        print("\nExisting .repro directory found")
        execution_dir = repro_dir / "execution"
        if execution_dir.exists():
            # Check for state files
            state_files = list(execution_dir.glob("*.json")) + list(execution_dir.glob("*.sqlite*"))
            print(f"  State files: {len(state_files)}")

            # Read execution state if exists
            exec_state = execution_dir / "execution_state.json"
            if exec_state.exists():
                try:
                    state = json.loads(exec_state.read_text())
                    print(f"  Last task: {state.get('current_task', 'unknown')}")
                    print(f"  Plan hash: {state.get('plan_hash', 'unknown')[:16]}...")
                except Exception:
                    pass
    else:
        print("\nNo existing .repro directory - fresh project")

    # Check for primary repo
    primary = project / "primary"
    if primary.exists():
        print(f"\nPrimary repository: {primary}")
        git_dir = primary / ".git"
        if git_dir.exists():
            try:
                sha = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=str(primary),
                    stderr=subprocess.DEVNULL, text=True
                ).strip()
                print(f"  Commit: {sha[:12]}")
            except Exception:
                pass

    # Check for plan
    plan_path = project / DEFAULT_PLAN_PATH
    if plan_path.exists():
        print(f"\nPlan file: {plan_path}")
    else:
        print(f"\nNo plan file found at {DEFAULT_PLAN_PATH}")
        if project_type == "paper_repro":
            print("  Consider creating a plan with reproctl plan command")

    # Generate takeover report
    report = {
        "project": str(project),
        "project_type": project_type,
        "has_repro_state": has_repro,
        "plan_exists": plan_path.exists(),
        "plan_path": str(plan_path) if plan_path.exists() else None,
        "autopilot_ready": has_repro and plan_path.exists(),
        "recommendation": _get_takeover_recommendation(project_type, has_repro, plan_path.exists()),
    }

    print("\n" + "=" * 60)
    _output(report, pretty=False)

    return EXIT_OK


def _detect_project_type(project: Path) -> str:
    """Detect the type of project."""
    # Check for paper reproduction markers
    primary = project / "primary"
    if primary.exists():
        # Check for training scripts
        train_files = list(primary.rglob("train*.py"))
        if train_files:
            return "paper_repro"
        return "code_repo"

    # Check for .repro but no primary
    repro_dir = project / ".repro"
    if repro_dir.exists():
        return "existing_repro"

    # Check for experiment markers
    if (project / "experiments").exists():
        return "experiment"

    return "unknown"


def _get_takeover_recommendation(project_type: str, has_repro: bool, has_plan: bool) -> str:
    """Get recommendation for next steps."""
    if project_type == "paper_repro" and has_repro and has_plan:
        return "READY: Run 'autopilot.py run --project .' to continue reproduction"
    elif project_type == "paper_repro" and not has_plan:
        return "NEEDS_PLAN: Create plan with 'reproctl plan' or manually"
    elif project_type == "paper_repro" and not has_repro:
        return "NEEDS_INIT: Run 'reproctl init' to initialize repro state"
    elif project_type == "existing_repro":
        return "EXISTING_STATE: Check status with 'autopilot.py status --project .'"
    else:
        return "UNKNOWN: Manual analysis required"


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot events command
# ──────────────────────────────────────────────────────────────────────────────

def cmd_events(args: argparse.Namespace) -> int:
    """Stream the event log."""
    project = _resolve_project(args.project)
    store = _store(project)

    events = store.events(after_seq=args.after_seq, limit=args.limit)

    if args.tail:
        # Tail mode - keep watching for new events
        last_seq = events[-1]["seq"] if events else 0
        print(f"Tailing events from seq {last_seq}...")
        try:
            while True:
                time.sleep(args.poll_interval)
                new_events = store.events(after_seq=last_seq, limit=100)
                for event in new_events:
                    print(json.dumps(event, default=str))
                    last_seq = event["seq"]
        except KeyboardInterrupt:
            pass
    else:
        _output({"events": events, "count": len(events)})

    return EXIT_OK


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot approve/reject commands
# ──────────────────────────────────────────────────────────────────────────────

def cmd_approve(args: argparse.Namespace) -> int:
    """Approve a pending task."""
    project = _resolve_project(args.project)
    store = _store(project)

    approval_id = args.approval_id.strip()

    # Find the approval
    pending = store.pending_approvals()
    target = None

    if approval_id.startswith("apr_"):
        target = next((a for a in pending if a.get("approval_id") == approval_id), None)
    else:
        target = next((a for a in pending if a.get("task_id") == approval_id), None)

    if target is None:
        print(f"Approval not found: {approval_id}")
        return EXIT_NOT_FOUND

    result = store.decide_approval(target["approval_id"], "APPROVED")
    print(f"Approved: {target.get('task_id')}")
    return EXIT_OK


def cmd_reject(args: argparse.Namespace) -> int:
    """Reject a pending task."""
    project = _resolve_project(args.project)
    store = _store(project)

    approval_id = args.approval_id.strip()

    # Find the approval
    pending = store.pending_approvals()
    target = None

    if approval_id.startswith("apr_"):
        target = next((a for a in pending if a.get("approval_id") == approval_id), None)
    else:
        target = next((a for a in pending if a.get("task_id") == approval_id), None)

    if target is None:
        print(f"Approval not found: {approval_id}")
        return EXIT_NOT_FOUND

    result = store.decide_approval(target["approval_id"], "REJECTED", args.reason or "")
    print(f"Rejected: {target.get('task_id')}")
    return EXIT_OK


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot daemon command
# ──────────────────────────────────────────────────────────────────────────────

def cmd_daemon(args: argparse.Namespace) -> int:
    """Control the autopilot daemon."""
    project = _resolve_project(args.project)

    if args.action == "start":
        return _daemon_start(project, args)
    elif args.action == "status":
        return _daemon_status(project)
    elif args.action == "stop":
        return _daemon_stop(project)
    else:
        return EXIT_INTERNAL


def _daemon_start(project: Path, args: argparse.Namespace) -> int:
    """Start the autopilot as a daemon."""
    existing = _read_pid(project)
    if existing and ProcessManager().is_alive(existing):
        print(f"Autopilot already running with PID {existing}")
        return EXIT_OK

    plan_path = Path(args.plan) if args.plan else project / DEFAULT_PLAN_PATH
    log_path = project / ".repro" / "execution" / "autopilot.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(THIS),
        "run",
        "--project", str(project),
        "--plan", str(plan_path),
        "--automation", args.automation,
    ]
    if args.mode:
        cmd.extend(["--mode", args.mode])
    if args.resume:
        cmd.append("--resume")

    env = os.environ.copy()
    env["AUTOPILOT_DAEMON"] = "1"

    proc = subprocess.Popen(
        cmd,
        cwd=str(project),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_path.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    # Wait for startup
    deadline = time.monotonic() + 5.0
    manager = ProcessManager()
    while time.monotonic() < deadline:
        if manager.is_alive(proc.pid):
            break
        time.sleep(0.1)

    if manager.is_alive(proc.pid):
        _write_pid(project, proc.pid)
        print(f"Autopilot started: PID {proc.pid}")
        print(f"Log: {log_path}")
        return EXIT_OK
    else:
        print("Autopilot failed to start")
        return EXIT_INTERNAL


def _daemon_status(project: Path) -> int:
    """Show daemon status."""
    pid = _read_pid(project)
    info = {"project": str(project), "pid": pid}

    if pid is None:
        info["status"] = "NOT_RUNNING"
    elif ProcessManager().is_alive(pid):
        info["status"] = "RUNNING"
    else:
        info["status"] = "STALE"

    hb = _heartbeat_path(project)
    if hb.exists():
        try:
            info["heartbeat"] = json.loads(hb.read_text())
        except json.JSONDecodeError:
            info["heartbeat"] = "corrupt"

    _output(info)
    return EXIT_OK


def _daemon_stop(project: Path) -> int:
    """Stop the daemon."""
    pid = _read_pid(project)
    if pid is None:
        print("Autopilot not running")
        return EXIT_OK

    manager = ProcessManager()

    # Stop running tasks first
    try:
        store = _store(project)
        for task in store.list_tasks({"RUNNING"}):
            wp = task.get("pid")
            if wp and manager.is_alive(int(wp)):
                manager.terminate(int(wp), grace_seconds=2.0)
        store.set_control_state("STOPPED")
    except Exception as e:
        print(f"Warning: Error stopping tasks: {e}")

    # Stop daemon
    if manager.is_alive(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    time.sleep(0.5)
    if manager.is_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    _write_pid(project, 0)
    print("Autopilot stopped")
    return EXIT_OK


# ──────────────────────────────────────────────────────────────────────────────
# L0-L3 loop command
# ──────────────────────────────────────────────────────────────────────────────

def cmd_l0l3(args: argparse.Namespace) -> int:
    """Run the L0-L3 automated verification loop."""
    project = _resolve_project(args.project)

    # Import L0L3Loop
    sys.path.insert(0, str(PACKAGE_ROOT))
    from scripts.l0_l3_loop import L0L3Loop

    primary = Path(args.primary) if args.primary else None

    loop = L0L3Loop(
        project_root=project,
        primary=primary,
        conda_env=args.conda_env,
    )

    summary = loop.run_all(
        stop_on_fail=not args.continue_on_fail,
        l1_steps=args.l1_steps,
        l2_epochs=args.l2_epochs,
    )

    # Save results
    output_path = Path(args.output) if args.output else None
    loop.save_results(output_path)

    _output(summary)

    return EXIT_OK if summary["all_passed"] else EXIT_BLOCKED


# ──────────────────────────────────────────────────────────────────────────────
# Report command
# ──────────────────────────────────────────────────────────────────────────────

def cmd_report(args: argparse.Namespace) -> int:
    """Generate reproduction report."""
    project = _resolve_project(args.project)

    # Import ReportGenerator
    sys.path.insert(0, str(PACKAGE_ROOT))
    from scripts.orchestrator.report_generator import ReportGenerator
    from scripts.orchestrator.state_store import StateStore

    store = StateStore(project)
    tasks = store.list_tasks()

    rg = ReportGenerator(project)

    if args.format == "markdown":
        md = rg.generate_markdown_report(tasks)
        print(md)
        report_path = project / ".repro" / "reports" / "reproduction_report.md"
        print(f"\nReport saved to: {report_path}")
    else:
        report = rg.generate_go_pivot_nogo(tasks)
        _output(report)

    return EXIT_OK


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autopilot.py",
        description="NORA-style continuous execution controller for paper reproduction",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run - continuous execution
    p_run = sub.add_parser("run", help="Run continuous autopilot until blocked or complete")
    p_run.add_argument("--project", required=True, help="Project root directory")
    p_run.add_argument("--plan", help=f"Plan file path (default: {DEFAULT_PLAN_PATH})")
    p_run.add_argument("--policy", help="Policy file path")
    p_run.add_argument("--mode", choices=["strict", "optimized"], help="Execution mode")
    p_run.add_argument("--automation", default="safe-auto",
                       choices=["safe-auto", "auto", "manual"],
                       help="Automation level (default: safe-auto)")
    p_run.add_argument("--until", default="blocked-or-complete",
                       choices=["blocked", "complete", "blocked-or-complete", "always"],
                       help="Run until condition (default: blocked-or-complete)")
    p_run.add_argument("--resume", action="store_true",
                       help="Resume from interrupted state")
    p_run.add_argument("--skip-doctor", action="store_true",
                       help="Skip preflight doctor checks")
    p_run.add_argument("--poll-interval", type=float, default=0.5,
                       help="Poll interval in seconds (default: 0.5)")

    # status
    p_status = sub.add_parser("status", help="Show autopilot status")
    p_status.add_argument("--project", required=True, help="Project root directory")

    # recover
    p_recover = sub.add_parser("recover", help="Recover from interrupted state")
    p_recover.add_argument("--project", required=True, help="Project root directory")
    p_recover.add_argument("--skip-doctor", action="store_true",
                          help="Skip preflight doctor checks")

    # pause/stop/continue
    p_pause = sub.add_parser("pause", help="Pause the autopilot")
    p_pause.add_argument("--project", required=True, help="Project root directory")

    p_stop = sub.add_parser("stop", help="Stop the autopilot")
    p_stop.add_argument("--project", required=True, help="Project root directory")

    p_cont = sub.add_parser("continue", help="Continue a paused autopilot")
    p_cont.add_argument("--project", required=True, help="Project root directory")

    # takeover
    p_takeover = sub.add_parser("takeover", help="Analyze and takeover an existing project")
    p_takeover.add_argument("--project", required=True, help="Project root directory")

    # events
    p_events = sub.add_parser("events", help="Stream the event log")
    p_events.add_argument("--project", required=True, help="Project root directory")
    p_events.add_argument("--after-seq", type=int, default=0, help="Start after sequence number")
    p_events.add_argument("--limit", type=int, default=100, help="Max events to return")
    p_events.add_argument("--tail", action="store_true", help="Tail the event log")
    p_events.add_argument("--poll-interval", type=float, default=1.0, help="Poll interval for tail")

    # approve/reject
    p_approve = sub.add_parser("approve", help="Approve a pending task")
    p_approve.add_argument("--project", required=True, help="Project root directory")
    p_approve.add_argument("approval_id", help="Approval ID or task ID")

    p_reject = sub.add_parser("reject", help="Reject a pending task")
    p_reject.add_argument("--project", required=True, help="Project root directory")
    p_reject.add_argument("approval_id", help="Approval ID or task ID")
    p_reject.add_argument("--reason", default="", help="Rejection reason")

    # daemon
    p_daemon = sub.add_parser("daemon", help="Control the autopilot daemon")
    p_daemon.add_argument("--project", required=True, help="Project root directory")
    p_daemon.add_argument("action", choices=["start", "status", "stop"],
                         help="Daemon action")
    p_daemon.add_argument("--plan", help="Plan file path")
    p_daemon.add_argument("--automation", default="safe-auto",
                          choices=["safe-auto", "auto", "manual"])
    p_daemon.add_argument("--mode", choices=["strict", "optimized"])
    p_daemon.add_argument("--resume", action="store_true")

    # version
    p_version = sub.add_parser("version", help="Show autopilot version")

    # l0l3 - L0-L3 loop
    p_l0l3 = sub.add_parser("l0l3", help="Run L0-L3 automated verification loop")
    p_l0l3.add_argument("--project", required=True, help="Project root directory")
    p_l0l3.add_argument("--primary", help="Primary repository directory")
    p_l0l3.add_argument("--conda-env", default="t4", help="Conda environment with torch")
    p_l0l3.add_argument("--l1-steps", type=int, default=50, help="L1: number of overfit steps")
    p_l0l3.add_argument("--l2-epochs", type=int, default=3, help="L2: number of mini loop epochs")
    p_l0l3.add_argument("--continue-on-fail", action="store_true", help="Continue to next stage on failure")
    p_l0l3.add_argument("--output", help="Output path for results JSON")

    # report - Generate reproduction report
    p_report = sub.add_parser("report", help="Generate reproduction report")
    p_report.add_argument("--project", required=True, help="Project root directory")
    p_report.add_argument("--format", default="markdown", choices=["markdown", "json"], help="Report format")

    return parser


HANDLERS = {
    "run": cmd_run,
    "status": cmd_status,
    "recover": cmd_recover,
    "pause": cmd_pause,
    "stop": cmd_stop,
    "continue": cmd_continue,
    "takeover": cmd_takeover,
    "events": cmd_events,
    "approve": cmd_approve,
    "reject": cmd_reject,
    "daemon": cmd_daemon,
    "l0l3": cmd_l0l3,
    "report": cmd_report,
    "version": lambda _: (print(f"Autopilot version {AUTOPILOT_VERSION}"), EXIT_OK)[1],
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return EXIT_INTERNAL

    try:
        return handler(args)
    except SystemExit as e:
        return int(e.code) if e.code else EXIT_OK
    except KeyboardInterrupt:
        print("\nInterrupted")
        return EXIT_STOPPED
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return EXIT_INTERNAL


if __name__ == "__main__":
    sys.exit(main())
