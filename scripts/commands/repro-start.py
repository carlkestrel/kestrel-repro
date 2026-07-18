#!/usr/bin/env python3
"""repro-start: Unified guided startup entry point.

Usage:
    python scripts/commands/repro-start.py --project <ROOT> [--plan <PLAN>]
                                          [--mode strict|optimized]
                                          [--auto-proceed] [--dry-run]

What this script does:
1. Auto-detect project root (or use --project).
2. Run doctor checks (preflight).
3. Collect or prompt for authorization contract.
4. Write canonical plan + auth contract.
5. Call reproctl run (or emit plan for dry-run).

This script is the "human-in-the-loop" guided entry. For daemon/resume
use cases, call reproctl directly.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve()
PLUGIN_ROOT = THIS.parents[2]
SCRIPTS = PLUGIN_ROOT / "scripts"
REPROCTL = SCRIPTS / "reproctl.py"

DESCRIPTION = """
repro-start — Guided experiment startup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mode overview (Chinese explanation / 模式说明):
  strict    — Safe mode: requires explicit human approval for each gate.
                安全模式：每个关卡需人工确认。
  optimized — Auto-approved low-risk gates; blocks high-risk ones.
                自动模式：低风险关卡自动通过，高风险关卡需确认。
  diagnose  — Dry-run validation of plan + dependencies.
                诊断模式：仅验证计划与依赖，不执行。
  test      — Isolated test mode with small resources.
                测试模式：小规模隔离测试。
  extend    — Extended run mode with full budgets.
                扩展模式：完整资源预算运行。

Authorisation:
  Without an auth contract, repro-start runs in restricted (audit-only) mode.
  All tasks that require approval will block waiting for human decision.
  Run `reproctl doctor --project <root>` to see which gates need approval.
"""

MODES = ("strict", "optimized", "diagnose", "test", "extend")


def _print_header():
    print("\033[1;36m" + "=" * 60 + "\033[0m")
    print("\033[1;36m  repro-start — Guided experiment startup\033[0m")
    print("\033[1;36m" + "=" * 60 + "\033[0m\n")


def _resolve_project(project: str | None) -> Path:
    """Auto-detect or validate project root."""
    if project:
        p = Path(project).resolve()
        if not p.exists():
            print(f"[ERROR] project not found: {p}", file=sys.stderr)
            sys.exit(2)
        return p

    # Auto-detect: walk up from CWD looking for .repro/execution/state.sqlite3
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".repro" / "execution" / "state.sqlite3").exists():
            return parent
        if (parent / "plan.yaml").exists() or (parent / "plan.md").exists():
            return parent

    print(f"[ERROR] Could not auto-detect project root.", file=sys.stderr)
    print(f"  CWD: {cwd}", file=sys.stderr)
    print(f"  Pass --project explicitly.", file=sys.stderr)
    sys.exit(2)


def _resolve_plan(project: Path, plan: str | None) -> Path | None:
    """Resolve plan path, optionally auto-detecting."""
    if plan:
        p = Path(plan).resolve()
        if not p.exists():
            print(f"[ERROR] plan not found: {p}", file=sys.stderr)
            sys.exit(5)
        return p

    # Auto-detect
    for candidate in ["plan.yaml", "plan.md", "PLAN.md"]:
        p = project / candidate
        if p.exists():
            print(f"[INFO] Auto-detected plan: {p}")
            return p

    return None


def _run_doctor(project: Path, plan: Path | None) -> dict:
    """Run doctor checks via reproctl."""
    args = [sys.executable, str(REPROCTL), "doctor",
             "--project", str(project)]
    if plan:
        args += ["--plan", str(plan)]
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=120,
    )
    if result.returncode == 0:
        return {"overall": "PASS", "report": {}}
    # Parse doctor output for report
    try:
        return {"overall": "FAIL", "report": json.loads(result.stdout)}
    except (json.JSONDecodeError, ValueError):
        return {"overall": "FAIL", "report": {"raw": result.stdout[:500]}}


def _collect_auth_contract(project: Path, mode: str) -> dict:
    """Collect authorization contract (simplified: from env or prompt).

    In a full implementation, this would:
    - Read existing .repro/auth_contract.json
    - Prompt the user if missing
    - Validate contract covers the current plan hash
    For now: create a minimal permissive contract in .repro/ or use defaults.
    """
    auth_path = project / ".repro" / "auth_contract.json"
    if auth_path.exists():
        try:
            with open(auth_path) as f:
                return json.load(f)
        except Exception:
            pass  # fall through to default

    # Minimal default contract (audit-only)
    default = {
        "contract_id": f"default-{os.getpid()}",
        "created_at": "2026-01-01T00:00:00Z",
        "automation": "safe-auto" if mode != "strict" else "manual",
        "granted": ["read_only", "safe", "compute_metrics"],
        "denied": ["destructive", "external_publish"],
        "policies": {
            "network": "deny",
            "clone": "deny",
            "download": "allow",
            "gpu": "deny",
        },
        "budgets": {
            "time_minutes": 0,
            "disk_gb": 0,
            "vram_gb": 0,
        },
    }
    # Write default if in project root
    try:
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_path, "w") as f:
            json.dump(default, f, indent=2)
        print(f"[INFO] Created default auth contract at {auth_path}")
    except OSError:
        pass
    return default


def _write_startup_summary(project: Path, mode: str,
                             plan: Path | None,
                             doctor_result: dict,
                             auth: dict) -> None:
    """Write startup summary JSON to .repro/startup/."""
    summary_dir = project / ".repro" / "startup"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "started_at": "2026-01-01T00:00:00Z",
        "mode": mode,
        "project_root": str(project),
        "plan_path": str(plan) if plan else None,
        "doctor": doctor_result,
        "auth_contract_id": auth.get("contract_id"),
        "automation": auth.get("automation"),
    }
    summary_path = summary_dir / "startup_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[INFO] Startup summary: {summary_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repro-start",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project", dest="project",
        help="Project root (auto-detected if not provided)",
    )
    parser.add_argument(
        "--plan", dest="plan",
        help="Plan file path (auto-detected if not provided)",
    )
    parser.add_argument(
        "--mode", dest="mode", default="strict",
        choices=MODES,
        help="Execution mode (default: strict)",
    )
    parser.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="Validate plan and emit summary without executing",
    )
    parser.add_argument(
        "--auto-proceed", dest="auto_proceed", action="store_true",
        help="Enable AUTO_PROCEED for low-risk gates",
    )
    args = parser.parse_args(argv)

    _print_header()

    # Step 1: Resolve project and plan
    project = _resolve_project(args.project)
    plan = _resolve_plan(project, args.plan)

    print(f"  Project : {project}")
    print(f"  Plan    : {plan or '(not found)'}")
    print(f"  Mode    : {args.mode}")
    print()

    # Step 2: Doctor checks
    print("[1/5] Running doctor checks...")
    doctor_result = _run_doctor(project, plan)
    if doctor_result.get("overall") == "FAIL":
        print("[WARN] Some doctor checks failed.", file=sys.stderr)
        print(f"       See doctor report for details.", file=sys.stderr)
        # Continue anyway for diagnose/test modes; block for strict
        if args.mode == "strict":
            print("[ERROR] Doctor failures block strict-mode start.", file=sys.stderr)
            return 3

    # Step 3: Collect authorization
    print("[2/5] Checking authorization contract...")
    auth = _collect_auth_contract(project, args.mode)
    print(f"       Contract: {auth.get('contract_id', 'unknown')}")

    # Step 4: Write startup summary
    print("[3/5] Writing startup summary...")
    _write_startup_summary(project, args.mode, plan, doctor_result, auth)

    # Step 5: Execute or dry-run
    if args.dry_run:
        print("[4/5] Dry-run mode: skipping execution.")
        print("[5/5] Plan validation complete.")
        print()
        print("\033[1;32m✓ repro-start (dry-run) completed successfully\033[0m")
        return 0

    print("[4/5] Starting execution...")
    env = os.environ.copy()
    if args.auto_proceed:
        env["AUTO_PROCEED"] = "true"

    reproctl_args = [
        sys.executable, str(REPROCTL), "run",
        "--project", str(project),
        "--mode", args.mode,
        "--automation", auth.get("automation", "safe-auto"),
    ]
    if plan:
        reproctl_args += ["--plan", str(plan)]

    print(f"[5/5] Executing: {' '.join(reproctl_args[:4])} ...")
    result = subprocess.run(reproctl_args, env=env, timeout=None)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
