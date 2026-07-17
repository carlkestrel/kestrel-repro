"""OSTAR CLI — `reproctl soak <subcommand>`.

Usage:
    reproctl soak plan [--project .] [--duration 8h]
    reproctl soak start [--project .] [--duration 8h] [--auto-repair safe]
    reproctl soak status [--project .]
    reproctl soak pause [--project .]
    reproctl soak resume [--project .]
    reproctl soak stop [--project .]
    reproctl soak report [--project .] [--format markdown|html|json]

Exit codes:
    0  - Success
    2  - Bad config
    3  - Guard failed
    4  - Already running
    5  - Rehearsal failed
    6  - Test failed
    7  - Max repairs reached
    8  - Resume failed
    9  - Hardware safety
    10 - Internal error
    11 - Manual stop
    12 - Duration ended
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

# Allow running directly
_THIS = Path(__file__).resolve()
_PKG = _THIS.parent.parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from scripts.ostar import constants as _C
from scripts.ostar import config as _cfg
from scripts.ostar import hardware_monitor as _hw
from scripts.ostar import guard as _guard
from scripts.ostar import soak_engine as _engine
from scripts.ostar import soak_state as _state
from scripts.ostar import reporter as _report


# ─────────────────────────────────────────────────────────────────────────────
# Path helpers
# ─────────────────────────────────────────────────────────────────────────────

def _project_of(args: argparse.Namespace) -> Path:
    p = getattr(args, "project", None)
    if p:
        return Path(p).resolve()
    return Path.cwd()


def _soak_root_of(project: Path) -> Path:
    return project / "soak"


# ─────────────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _print_err(stage: str, code: int, reason: str,
               related: str = "", fix: str = "") -> None:
    print("OSTAR FAILED", file=sys.stderr)
    print(f"  Stage:       {stage}", file=sys.stderr)
    print(f"  Exit Code:   {code}", file=sys.stderr)
    print(f"  Reason:      {reason}", file=sys.stderr)
    if related:
        print(f"  Related:     {related}", file=sys.stderr)
    if fix:
        print(f"  Fix:         {fix}", file=sys.stderr)


def _json_out(data: dict) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


# ─────────────────────────────────────────────────────────────────────────────
# Subcommands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_plan(args: argparse.Namespace) -> int:
    """Run pre-flight rehearsal (30 minutes) before starting the full soak."""
    project = _project_of(args)
    soak_root = _soak_root_of(project)
    cfg = _cfg.OSTARConfig.from_args(vars(args))
    cfg.project_root = project
    cfg.soak_root = soak_root

    print(f"[OSTAR] Planning soak for: {project}")
    print(f"[OSTAR] Soak root: {soak_root}")

    # Quick guard check
    guard = _guard.Guard(project)
    g_result = guard.run(soak_root=soak_root)
    guard_path = soak_root / "guard_result.json"
    guard_path.write_text(
        json.dumps(g_result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"[OSTAR] Guard result: {'PASS' if g_result.passed else 'FAIL'}")
    for check in g_result.checks:
        icon = "✅" if check["status"] == "PASS" else "❌"
        print(f"  {icon} {check['name']}: {check['message']}")

    if not g_result.passed:
        _print_err("GUARD", _C.EXIT_GUARD_FAIL,
                   f"{len([c for c in g_result.checks if c['status'] == 'FAIL'])} checks failed",
                   "guard_result.json",
                   "Fix failures before starting soak")
        return _C.EXIT_GUARD_FAIL

    # Print soak plan
    end_time = cfg.resolved_end_time_utc(
        datetime.now(timezone.utc).astimezone(
            __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo(cfg.timezone)
        )
    )
    print(f"[OSTAR] Duration: {cfg.duration_seconds / 3600:.1f} hours")
    print(f"[OSTAR] End time: {end_time.isoformat()}")
    print(f"[OSTAR] Auto-repair level: {cfg.auto_repair_level}")
    print(f"[OSTAR] Max repairs: {cfg.max_repairs}")
    print(f"[OSTAR] GPU temp limit: {cfg.gpu_temperature_limit or 'default'}°C")
    print(f"[OSTAR] Disk reserve: {cfg.disk_reserve_gb} GB")
    print(f"[OSTAR] Start time: {_now()}")

    # Run rehearsal
    print(f"[OSTAR] Running 30-minute rehearsal...")
    engine = _engine.SoakEngine(project, cfg, soak_root)
    result = engine.run_rehearsal()

    if result.status == "REHEARSAL_FAILED":
        _print_err("REHEARSAL", _C.EXIT_REHEARSAL_FAIL,
                   "rehearsal did not complete successfully",
                   str(soak_root),
                   "Fix rehearsal failures before starting full soak")
        return _C.EXIT_REHEARSAL_FAIL

    print(f"[OSTAR] Rehearsal PASSED ✅")
    print(f"[OSTAR] Plan ready. Run `reproctl soak start` to begin the full soak.")
    return _C.EXIT_OK


def cmd_start(args: argparse.Namespace) -> int:
    """Start the overnight soak test."""
    project = _project_of(args)
    soak_root = _soak_root_of(project)

    # Check for already running
    existing_pid = _read_pid(soak_root)
    if existing_pid:
        proc_alive = _pid_alive(existing_pid)
        if proc_alive:
            _print_err("START", _C.EXIT_ALREADY_RUNNING,
                       f"soak already running (PID {existing_pid})",
                       str(soak_root / "ostar.pid"),
                       "Run `reproctl soak stop` first or `reproctl soak status`")
            return _C.EXIT_ALREADY_RUNNING
        else:
            print(f"[OSTAR] Cleaning stale PID {existing_pid}")

    cfg = _cfg.OSTARConfig.from_args(vars(args))
    cfg.project_root = project
    cfg.soak_root = soak_root

    # Validate config
    errors = cfg.validate()
    if errors:
        for err in errors:
            print(f"[OSTAR] Config error: {err}", file=sys.stderr)
        return _C.EXIT_BAD_CONFIG

    print(f"[OSTAR] Starting overnight soak for: {project}")
    print(f"[OSTAR] Duration: {cfg.duration_seconds / 3600:.1f}h")
    print(f"[OSTAR] Auto-repair: {cfg.auto_repair_level}")
    print(f"[OSTAR] Soak root: {soak_root}")

    # Fork subprocess
    if not args.dry_run:
        pid = _fork_child(project, cfg, soak_root)
        if pid:
            _write_pid(soak_root, pid)
            print(f"[OSTAR] Soak started (PID {pid})")
            print(f"[OSTAR] Log: {soak_root / 'logs' / f'soak_{pid}.log'}")
            print(f"[OSTAR] Run `reproctl soak status` to monitor")
        return _C.EXIT_OK
    else:
        # Dry-run: run one cycle only
        engine = _engine.SoakEngine(project, cfg, soak_root)
        result = engine.run()
        _json_out(result.__dict__)
        return _C.EXIT_OK if result.status == "COMPLETED" else result.verdict


def cmd_status(args: argparse.Namespace) -> int:
    """Show current soak run status."""
    project = _project_of(args)
    soak_root = _soak_root_of(project)

    pid = _read_pid(soak_root)
    alive = _pid_alive(pid) if pid else False

    # Read heartbeat
    hb_path = soak_root / "heartbeat.json"
    heartbeat = None
    if hb_path.exists():
        try:
            heartbeat = json.loads(hb_path.read_text())
        except Exception:
            heartbeat = {"corrupt": True}

    # Read state
    state_path = soak_root / "current_state.json"
    state = None
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception:
            state = {"corrupt": True}

    # Try state store
    try:
        store = _state.SoakStateStore(soak_root)
        summary = store.status_summary()
    except Exception as e:
        summary = {"error": str(e)}

    # Read guard result
    guard_path = soak_root / "guard_result.json"
    guard = None
    if guard_path.exists():
        try:
            guard = json.loads(guard_path.read_text())
        except Exception:
            pass

    # Hardware snapshot
    hw = _hw.HardwareMonitor(project_root=project)
    hw_snap = hw.snapshot()

    output = {
        "project": str(project),
        "pid": pid,
        "alive": alive,
        "status": state.get("status") if state else "UNKNOWN",
        "verdict": state.get("verdict") if state else None,
        "heartbeat": heartbeat,
        "state": state,
        "summary": summary,
        "guard": guard,
        "hardware": hw_snap.to_dict() if hw_snap else None,
        "checked_at": _now(),
    }

    _json_out(output)

    # Human-readable summary
    print(f"\n{'=' * 60}")
    print(f"OSTAR Status — {project}")
    print(f"{'=' * 60}")
    print(f"Process: {'ALIVE' if alive else 'NOT RUNNING'} (PID {pid or 'N/A'})")
    if state:
        print(f"Status:  {state.get('status', 'unknown')}")
        if state.get("verdict"):
            print(f"Verdict: {state['verdict']}")
    if hw_snap and hw_snap.gpu_available:
        print(f"GPU:     {hw_snap.gpu_count}x {hw_snap.gpu_names[0]}")
        if hw_snap.gpu_temps_c:
            print(f"Temp:    {hw_snap.gpu_temps_c[0]}°C")
        print(f"GPU Mem: {hw_snap.gpu_memory_reserved_gb[0]:.1f}/{hw_snap.gpu_memory_total_gb[0]:.1f} GB "
              f"({hw_snap.gpu_memory_used_pct[0]:.1f}%)")
    print(f"CPU RAM: {hw_snap.cpu_memory_used_pct:.1f}% "
          f"({hw_snap.cpu_memory_available_gb:.1f} GB free)")
    print(f"Disk:    {hw_snap.disk_free_gb:.1f} GB free")
    if heartbeat:
        age = time.time() - heartbeat.get("timestamp", 0)
        print(f"Heartbeat: {age:.0f}s ago")
    print(f"{'=' * 60}")
    return _C.EXIT_OK


def cmd_pause(args: argparse.Namespace) -> int:
    """Pause the running soak."""
    project = _project_of(args)
    soak_root = _soak_root_of(project)
    pid = _read_pid(soak_root)
    if not pid or not _pid_alive(pid):
        print("[OSTAR] No soak process running")
        return _C.EXIT_OK
    os.kill(pid, signal.SIGSTOP)
    print(f"[OSTAR] Soak paused (PID {pid})")
    return _C.EXIT_OK


def cmd_resume(args: argparse.Namespace) -> int:
    """Resume a paused soak."""
    project = _project_of(args)
    soak_root = _soak_root_of(project)
    pid = _read_pid(soak_root)
    if not pid or not _pid_alive(pid):
        print("[OSTAR] No soak process to resume")
        return _C.EXIT_RESUME_FAILED
    os.kill(pid, signal.SIGCONT)
    print(f"[OSTAR] Soak resumed (PID {pid})")
    return _C.EXIT_OK


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the soak gracefully."""
    project = _project_of(args)
    soak_root = _soak_root_of(project)
    pid = _read_pid(soak_root)
    if not pid:
        print("[OSTAR] No soak PID file found")
        return _C.EXIT_OK

    if _pid_alive(pid):
        print(f"[OSTAR] Sending SIGTERM to PID {pid}...")
        os.kill(pid, signal.SIGTERM)
        # Wait up to 10 seconds for graceful exit
        for _ in range(20):
            time.sleep(0.5)
            if not _pid_alive(pid):
                break
        if _pid_alive(pid):
            print(f"[OSTAR] Graceful stop failed, sending SIGKILL...")
            os.kill(pid, signal.SIGKILL)
    else:
        print(f"[OSTAR] PID {pid} already dead")

    _write_pid(soak_root, 0)
    print("[OSTAR] Soak stopped")
    return _C.EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    """Generate or display the morning report."""
    project = _project_of(args)
    soak_root = _soak_root_of(project)
    fmt = getattr(args, "format", "markdown") or "markdown"

    try:
        store = _state.SoakStateStore(soak_root)
        summary = store.status_summary()
        run_id = summary.get("run_id")
        if not run_id:
            print("[OSTAR] No soak run found")
            return _C.EXIT_BAD_CONFIG

        output_dir = soak_root / "reports"
        result = _report.generate_all_reports(store, run_id, output_dir)

        if fmt == "json":
            _json_out(result)
        else:
            md_path = output_dir / "overnight_summary.md"
            if md_path.exists():
                print(md_path.read_text(encoding="utf-8"))
            else:
                print(f"[OSTAR] Report not yet available. Run: {md_path}")
                _json_out(result)
        return _C.EXIT_OK
    except Exception as e:
        _print_err("REPORT", _C.EXIT_INTERNAL, str(e))
        return _C.EXIT_INTERNAL


# ─────────────────────────────────────────────────────────────────────────────
# Subprocess fork
# ─────────────────────────────────────────────────────────────────────────────

def _fork_child(project: Path, cfg: _cfg.OSTARConfig,
                soak_root: Path) -> int | None:
    """Fork a child process to run the soak engine."""
    logs_dir = soak_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    pid = os.fork()
    if pid != 0:
        return pid  # parent returns child PID

    # Child: run the engine
    try:
        # Redirect stdout/stderr to log file
        log_file = logs_dir / f"soak_{os.getpid()}.log"
        log_fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        os.dup2(log_fd, 1)
        os.dup2(log_fd, 2)
        if log_fd > 2:
            os.close(log_fd)

        # Run engine
        engine = _engine.SoakEngine(project, cfg, soak_root)
        result = engine.run()

        # Write result
        result_path = soak_root / "soak_result.json"
        result_path.write_text(
            json.dumps(result.__dict__, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        os._exit(_C.EXIT_OK if result.status == "COMPLETED" else 1)
    except Exception as e:
        print(f"[OSTAR child] Fatal error: {e}", file=sys.stderr)
        traceback.print_exc()
        os._exit(_C.EXIT_INTERNAL)


def _read_pid(soak_root: Path) -> int | None:
    pid_path = soak_root / "ostar.pid"
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_pid(soak_root: Path, pid: int) -> None:
    pid_path = soak_root / "ostar.pid"
    pid_path.write_text(str(pid), encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reproctl soak",
        description="OSTAR — Overnight Soak Test and Controlled Auto-Repair",
    )
    sub = parser.add_subparsers(dest="soak_command", required=True)

    # ── plan ──────────────────────────────────────────────────────────────
    p_plan = sub.add_parser("plan", help="Run 30-minute pre-flight rehearsal")
    _add_common(p_plan)
    p_plan.add_argument("--duration", default="30m",
                       help="Rehearsal duration (default: 30m)")

    # ── start ───────────────────────────────────────────────────────────
    p_start = sub.add_parser("start", help="Start the overnight soak test")
    _add_common(p_start)
    _add_timing(p_start)
    _add_hardware(p_start)
    _add_repair(p_start)
    p_start.add_argument("--dry-run", action="store_true",
                        help="Run one cycle only (no daemon)")

    # ── status ───────────────────────────────────────────────────────────
    p_status = sub.add_parser("status", help="Show soak run status")
    _add_common(p_status)

    # ── pause ───────────────────────────────────────────────────────────
    p_pause = sub.add_parser("pause", help="Pause the running soak")
    _add_common(p_pause)

    # ── resume ───────────────────────────────────────────────────────────
    p_resume = sub.add_parser("resume", help="Resume a paused soak")
    _add_common(p_resume)

    # ── stop ─────────────────────────────────────────────────────────────
    p_stop = sub.add_parser("stop", help="Stop the soak gracefully")
    _add_common(p_stop)

    # ── report ───────────────────────────────────────────────────────────
    p_report = sub.add_parser("report", help="Generate/view the morning report")
    _add_common(p_report)
    p_report.add_argument("--format", "-f",
                         choices=["markdown", "html", "json"],
                         default="markdown",
                         help="Report format (default: markdown)")

    return parser


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--project", "-p", default=".",
                   help="Project root (default: current directory)")


def _add_timing(p: argparse.ArgumentParser) -> None:
    p.add_argument("--duration", default="8h",
                   help="Soak duration (default: 8h). Examples: 8h, 480m, 28800s")
    p.add_argument("--start-time", default=None,
                   help="Start time in HH:MM local or ISO format")
    p.add_argument("--end-time", default=None,
                   help="End time in HH:MM local or ISO format")
    p.add_argument("--timezone", default=_C.DEFAULT_TIMEZONE,
                   help=f"Timezone (default: {_C.DEFAULT_TIMEZONE})")


def _add_hardware(p: argparse.ArgumentParser) -> None:
    p.add_argument("--gpu-temperature-limit", type=int, default=None,
                   help="GPU temperature limit in °C (default: auto)")
    p.add_argument("--disk-reserve", type=float, default=None,
                   help="Minimum free disk in GB (default: 10)")


def _add_repair(p: argparse.ArgumentParser) -> None:
    p.add_argument("--auto-repair", dest="auto_repair_level",
                   choices=["none", "safe", "full"],
                   default="safe",
                   help="Auto-repair level (default: safe)")
    p.add_argument("--max-repairs", type=int, default=None,
                   help=f"Max total repairs (default: {_C.DEFAULT_MAX_REPAIRS})")
    p.add_argument("--max-retries", type=int, default=None,
                   help=f"Max retries per bug (default: {_C.DEFAULT_MAX_RETRIES_PER_BUG})")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    HANDLERS = {
        "plan": cmd_plan,
        "start": cmd_start,
        "status": cmd_status,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "stop": cmd_stop,
        "report": cmd_report,
    }

    handler = HANDLERS.get(args.soak_command)
    if handler is None:
        parser.print_help()
        return _C.EXIT_INTERNAL

    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\n[OSTAR] Interrupted")
        return _C.EXIT_MANUAL_STOP
    except Exception as e:
        import traceback
        traceback.print_exc()
        _print_err("INTERNAL", _C.EXIT_INTERNAL, str(e))
        return _C.EXIT_INTERNAL


if __name__ == "__main__":
    sys.exit(main())
