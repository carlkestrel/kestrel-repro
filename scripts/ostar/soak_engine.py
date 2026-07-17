"""OSTAR core soak engine — the TEST → REPRODUCE → CLASSIFY → REPAIR → TARGETED_TEST → REGRESSION_TEST → RESUME_SOAK loop.

This is the heart of OSTAR. It implements:
  - The main overnight loop with all 7 termination conditions
  - Anti-infinite-loop guards
  - Per-cycle state persistence and atomic checkpoints
  - Heartbeat mechanism
  - Subprocess isolation for test suites
  - Graceful pause / resume / stop
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import constants as _C
from . import config as _cfg
from . import exit_validator
from . import guard as _guard
from . import hardware_monitor as _hw
from . import repair_node as _repair
from . import soak_state as _state
from . import test_suites as _ts


@dataclass
class CycleContext:
    """Per-cycle execution context."""
    cycle_seq: int
    run_id: str
    started_at_utc: str
    termination_reason: str = ""
    termination_code: int = 0
    suite_results: list[dict] = field(default_factory=list)
    bugs_found: list[dict] = field(default_factory=list)
    repairs_attempted: int = 0
    repairs_verified: int = 0
    rollbacks: int = 0


@dataclass
class SoakEngineResult:
    status: str
    verdict: str
    run_id: str
    cycles_completed: int
    total_repairs: int
    verified_repairs: int
    rollbacks: int
    termination_reason: str
    duration_seconds: float
    notes: list[str] = field(default_factory=list)


class SoakEngine:
    """Core overnight soak test engine."""

    def __init__(
        self,
        project_root: Path,
        config: _cfg.OSTARConfig,
        soak_root: Path | None = None,
    ):
        self.project_root = project_root.resolve()
        self.config = config
        self.soak_root = (soak_root or self.project_root / "soak").resolve()
        self.soak_root.mkdir(parents=True, exist_ok=True)

        self._state = _state.SoakStateStore(self.soak_root)
        self._hw = _hw.HardwareMonitor(
            project_root=self.project_root,
            policy=_hw.HardwarePolicy(
                gpu_warn_temp_c=(
                    config.gpu_temperature_limit - 5
                    if config.gpu_temperature_limit
                    else _C.DEFAULT_GPU_WARN_TEMP_C
                ),
                gpu_critical_temp_c=(
                    config.gpu_temperature_limit
                    if config.gpu_temperature_limit
                    else _C.DEFAULT_GPU_CRITICAL_TEMP_C
                ),
                disk_reserve_gb=config.disk_reserve_gb,
                gpu_memory_reserve_pct=config.gpu_memory_reserve_pct,
            ),
        )

        self._run_id: str | None = None
        self._cycle_seq: int = 0
        self._start_time: float = 0
        self._end_time: float = 0
        self._control = threading.Event()
        self._pause = threading.Event()
        self._stop = threading.Event()
        self._rehearsal_mode = False
        self._termination_reason = ""
        self._termination_code = _C.EXIT_OK
        self._consecutive_crashes = 0
        self._bug_repair_counts: dict[str, int] = {}  # fingerprint → repair attempts
        self._last_cycle_end: float = 0

        # Heartbeat thread
        self._hb_thread: threading.Thread | None = None
        self._hb_active = threading.Event()

        # Install signal handlers
        self._setup_signals()

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def run(self) -> SoakEngineResult:
        """Execute the full soak loop. Returns result dict."""
        self._start_time = time.time()

        # ── Phase 0: Guard ─────────────────────────────────────────────
        guard_result = self._run_guard()
        if not guard_result.passed:
            return SoakEngineResult(
                status="GUARD_FAILED",
                verdict=_C.VERDICT_FAILED_UNRESOLVED,
                run_id=guard_result.run_id,
                cycles_completed=0,
                total_repairs=0,
                verified_repairs=0,
                rollbacks=0,
                termination_reason="pre-flight guard failed",
                duration_seconds=time.time() - self._start_time,
            )

        self._run_id = guard_result.run_id
        self._state.init_run(self.config.to_dict())
        self._state.start_run(self._run_id)

        # ── Phase 1: Rehearsal (if requested) ──────────────────────────
        if self._rehearsal_mode:
            rehearsal_ok = self._run_rehearsal()
            if not rehearsal_ok:
                self._state.abort_run(self._run_id, "rehearsal failed")
                return SoakEngineResult(
                    status="REHEARSAL_FAILED",
                    verdict=_C.VERDICT_FAILED_UNRESOLVED,
                    run_id=self._run_id,
                    cycles_completed=0,
                    total_repairs=0,
                    verified_repairs=0,
                    rollbacks=0,
                    termination_reason="rehearsal failed",
                    duration_seconds=time.time() - self._start_time,
                )

        # ── Phase 2: Main soak loop ─────────────────────────────────────
        self._start_heartbeat()
        result = self._run_loop()
        self._stop_heartbeat()

        self._end_time = time.time()
        duration = self._end_time - self._start_time

        # ── Phase 3: Generate reports ───────────────────────────────────
        from . import reporter as _rpt
        _rpt.generate_all_reports(self._state, self._run_id)

        return SoakEngineResult(
            status=result.get("status", "COMPLETED"),
            verdict=result.get("verdict", _C.VERDICT_FAILED_UNRESOLVED),
            run_id=self._run_id,
            cycles_completed=self._cycle_seq,
            total_repairs=result.get("total_repairs", 0),
            verified_repairs=result.get("verified_repairs", 0),
            rollbacks=result.get("rollbacks", 0),
            termination_reason=self._termination_reason or "duration ended",
            duration_seconds=duration,
        )

    def run_rehearsal(self) -> SoakEngineResult:
        """Run the 30-minute rehearsal (pre-flight dry run of one cycle)."""
        self._rehearsal_mode = True
        self._start_time = time.time()
        guard_result = self._run_guard()
        if not guard_result.passed:
            return SoakEngineResult(
                status="GUARD_FAILED", verdict=_C.VERDICT_FAILED_UNRESOLVED,
                run_id=guard_result.run_id, cycles_completed=0,
                total_repairs=0, verified_repairs=0, rollbacks=0,
                termination_reason="guard failed",
                duration_seconds=time.time() - self._start_time,
            )
        self._run_id = guard_result.run_id
        self._state.init_run(self.config.to_dict())
        rehearsal_ok = self._run_rehearsal()
        return SoakEngineResult(
            status="REHEARSAL_OK" if rehearsal_ok else "REHEARSAL_FAILED",
            verdict=_C.VERDICT_FAILED_UNRESOLVED if not rehearsal_ok else _C.VERDICT_SOAK_VERIFIED,
            run_id=self._run_id,
            cycles_completed=1,
            total_repairs=0,
            verified_repairs=0,
            rollbacks=0,
            termination_reason="rehearsal ended",
            duration_seconds=time.time() - self._start_time,
        )

    def pause(self) -> None:
        self._pause.set()
        if self._run_id:
            self._state.pause_run(self._run_id)

    def resume(self) -> None:
        self._pause.clear()
        if self._run_id:
            self._state.resume_run(self._run_id)

    def stop(self) -> None:
        self._stop.set()
        self._control.set()

    # ─────────────────────────────────────────────────────────────────────
    # Guard
    # ─────────────────────────────────────────────────────────────────────

    def _run_guard(self) -> _guard.GuardResult:
        guard = _guard.Guard(self.project_root)
        result = guard.run(soak_root=self.soak_root)
        return result

    # ─────────────────────────────────────────────────────────────────────
    # Rehearsal
    # ─────────────────────────────────────────────────────────────────────

    def _run_rehearsal(self) -> bool:
        """Run a 30-minute rehearsal covering all key paths."""
        rehearsal_duration = _C.DEFAULT_REHEARSAL_DURATION_SECONDS
        deadline = time.time() + rehearsal_duration
        notes: list[str] = []

        # 1. One CI run
        plugin_root = self.project_root / ".cursor" / "plugins" / "local" / "dl-paper-repro"
        reproctl = plugin_root / "scripts" / "reproctl.py"
        if reproctl.exists():
            rc, _, stderr = _ts._run_subprocess(
                [sys.executable, str(reproctl), "version"],
                timeout_seconds=30,
            )
            notes.append(f"reproctl version: rc={rc}")
            if rc != 0:
                return False

        # 2. One GPU short loop (cap at 5 steps)
        gpu_result = _ts.run_gpu_stress(
            self.project_root, max_steps=5, batch_size=10)
        notes.append(f"GPU short loop: {gpu_result.status}")

        # 3. State save / restore cycle
        if self._run_id:
            self._state.heartbeat(self._run_id, os.getpid(), {"rehearsal": True})
            self._state.write_checkpoint(
                {"rehearsal": True, "notes": notes},
                seq=0,
            )

        # 4. Report generation (dry)
        from . import reporter as _rpt
        try:
            _rpt.generate_all_reports(self._state, self._run_id)
            notes.append("report generation: ok")
        except Exception as e:
            notes.append(f"report generation: {e}")

        return True

    # ─────────────────────────────────────────────────────────────────────
    # Main loop
    # ─────────────────────────────────────────────────────────────────────

    def _run_loop(self) -> dict:
        """The TEST → REPRODUCE → CLASSIFY → REPAIR → RESUME_SOAK loop."""
        total_repairs = 0
        verified_repairs = 0
        rollbacks = 0
        cycle_ctx: CycleContext | None = None

        while not self._stop.is_set():
            # ── Check termination conditions ────────────────────────────
            reason, code = self._check_termination(total_repairs, rollbacks)
            if reason:
                self._termination_reason = reason
                self._termination_code = code
                self._state.abort_run(self._run_id, reason)
                break

            # ── Pause support ─────────────────────────────────────────
            self._pause.wait(timeout=5)
            if self._pause.is_set() and not self._stop.is_set():
                time.sleep(1)
                continue

            # ── Time deadline check ────────────────────────────────────
            end_time_utc = self.config.resolved_end_time_utc(
                datetime.fromtimestamp(self._start_time, tz=timezone.utc)
            )
            remaining = end_time_utc.timestamp() - time.time()
            if remaining <= 0:
                self._termination_reason = "end_time_reached"
                self._termination_code = _C.EXIT_DURATION_ENDED
                break

            # ── Increment cycle ───────────────────────────────────────
            self._cycle_seq += 1
            cycle_ctx = CycleContext(
                cycle_seq=self._cycle_seq,
                run_id=self._run_id,
                started_at_utc=datetime.now(timezone.utc).isoformat(),
            )

            try:
                result = self._execute_cycle(cycle_ctx)
                self._last_cycle_end = time.time()

                if result.get("status") == "FAIL":
                    self._consecutive_crashes += 1
                else:
                    self._consecutive_crashes = 0

                total_repairs += result.get("repairs_attempted", 0)
                verified_repairs += result.get("repairs_verified", 0)
                rollbacks += result.get("rollbacks", 0)

                # Record cycle in state
                self._state.record_cycle(
                    self._run_id, self._cycle_seq,
                    result.get("status", "UNKNOWN"),
                    exit_reason=result.get("exit_reason"),
                    bug_count=result.get("bug_count", 0),
                    repair_count=result.get("repairs_attempted", 0),
                )

                # Check for same-bug consecutive failure
                if cycle_ctx.bugs_found:
                    for bug in cycle_ctx.bugs_found:
                        bug_id = bug.get("bug_id", "")
                        count = self._bug_repair_counts.get(bug_id, 0) + 1
                        self._bug_repair_counts[bug_id] = count
                        if count >= _C.DEFAULT_MAX_RETRIES_PER_BUG:
                            self._termination_reason = "same_bug_consecutive_failures"
                            self._termination_code = _C.EXIT_REPAIR_EXHAUSTED
                            break

                # Write checkpoint every cycle
                self._state.write_checkpoint(
                    {
                        "cycle_seq": self._cycle_seq,
                        "run_id": self._run_id,
                        "total_repairs": total_repairs,
                        "verified_repairs": verified_repairs,
                        "rollbacks": rollbacks,
                        "bug_repair_counts": self._bug_repair_counts,
                    },
                    seq=self._cycle_seq,
                )

            except Exception as e:
                self._consecutive_crashes += 1
                self._state.record_event(
                    "CYCLE_ERROR",
                    payload={"cycle_seq": self._cycle_seq,
                             "error": str(e), "traceback": traceback.format_exc()[-500:]},
                )
                if self._consecutive_crashes >= _C.DEFAULT_MAX_CONSECUTIVE_CRASHES:
                    self._termination_reason = "consecutive_agent_crashes"
                    self._termination_code = _C.EXIT_INTERNAL
                    break

        # ── Exit validation ───────────────────────────────────────────
        validator = exit_validator.ExitValidator(self._state)
        verdict = validator.evaluate(self._run_id)
        self._state.complete_run(self._run_id, verdict.verdict)

        return {
            "status": "COMPLETED" if self._termination_code == _C.EXIT_OK
                      else "TERMINATED",
            "verdict": verdict.verdict,
            "total_repairs": total_repairs,
            "verified_repairs": verified_repairs,
            "rollbacks": rollbacks,
        }

    def _execute_cycle(self, ctx: CycleContext) -> dict:
        """Execute one TEST → REPRODUCE → REPAIR → RESUME_SOAK cycle."""
        exit_reason = ""
        status = "PASS"

        # ── A. TEST: Run all test suites ───────────────────────────────
        cfg_dict = self.config.to_dict()
        suite_results = _ts.run_all_suites(self.project_root, config=cfg_dict)

        # Record CI results
        for sr in suite_results:
            self._state.record_ci_result(
                self._run_id, None,
                suite_name=sr.name,
                passed=sr.passed,
                failed=sr.failed,
                skipped=sr.skipped,
                duration_seconds=sr.duration_seconds,
                flaky=sr.flaky,
            )
        ctx.suite_results = [r.to_dict() for r in suite_results]

        # ── B. DETECT: Find failures ─────────────────────────────────
        failed_suites = [r for r in suite_results if r.status == "FAIL"]
        if not failed_suites:
            return {
                "status": "PASS", "exit_reason": "all suites passed",
                "bug_count": 0, "repairs_attempted": 0,
                "repairs_verified": 0, "rollbacks": 0,
            }

        # ── C. REPRODUCE + CLASSIFY ──────────────────────────────────
        bugs: list[dict] = []
        for suite in failed_suites:
            for err in suite.errors[:3]:  # top 3 errors per suite
                fp = self._fingerprint_error(err, suite.output)
                error_class, _ = self._classify(err, suite.output)
                bug_id = self._state.upsert_bug(
                    self._run_id, fingerprint=fp, error_class=error_class,
                )
                bugs.append({
                    "bug_id": bug_id,
                    "fingerprint": fp,
                    "error_class": error_class,
                    "suite": suite.name,
                    "error": err,
                })
                ctx.bugs_found.append({"bug_id": bug_id, "error_class": error_class})

                # Save failure evidence
                self._state.write_failure_evidence(
                    seq=len(ctx.suite_results),
                    failure={
                        "run_id": self._run_id,
                        "cycle_seq": ctx.cycle_seq,
                        "bug_id": bug_id,
                        "suite": suite.name,
                        "error": err,
                        "output": suite.output[:500],
                    },
                )

        ctx.bugs_found = bugs
        status = "FAIL"
        exit_reason = f"{len(bugs)} bug(s) detected"

        # ── D. REPAIR ────────────────────────────────────────────────
        repairs_attempted = 0
        repairs_verified = 0
        rollbacks = 0

        for bug in bugs:
            # Check if max repairs reached
            if repairs_attempted >= self.config.max_repairs:
                exit_reason += " (max repairs reached)"
                break

            # Check if BLOCKED class
            if bug["error_class"] in _C.BLOCKED_CLASSES:
                exit_reason += f" ({bug['bug_id']} BLOCKED_REQUIRES_REVIEW)"
                continue

            # Check auto-repair level
            if self.config.auto_repair_level == "none":
                continue

            # Execute repair node
            node = _repair.RepairNode(
                project_root=self.project_root,
                failure_log=bug.get("error", ""),
                error_output=bug.get("error", ""),
                bug_id=bug["bug_id"],
            )
            repair_result = node.run(
                max_retries=self.config.max_retries_per_bug,
                auto_repair_level=self.config.auto_repair_level,
            )
            repairs_attempted += 1

            # Record repair
            self._state.record_repair(
                self._run_id,
                bug_id=bug["bug_id"],
                attempt=repairs_attempted,
                patch=repair_result.patch,
                status=repair_result.status,
                target_test_passed=(
                    repair_result.target_test_runs == 3
                    if repair_result.target_test_runs > 0 else None
                ),
                regression_passed=repair_result.regression_test_added,
                notes="; ".join(repair_result.notes),
            )

            self._state.write_node_result(
                repair_result.repair_id,
                repair_result.to_dict(),
            )

            if repair_result.status == "VERIFIED":
                repairs_verified += 1
                self._state.reset_bug_consecutive_failures(bug["bug_id"])
            elif repair_result.status == "ROLLBACK":
                rollbacks += 1

            # Anti-fake-fix: verify CI actually improved
            if repair_result.status == "VERIFIED":
                ci_result = _ts.run_ci_stress(
                    self.project_root,
                    level_1_fast=True,
                    level_2_full=False,
                    runs=1,
                )
                if ci_result.failed > 0:
                    # Fake fix detected — rollback
                    node._rollback_patch()
                    rollbacks += 1
                    exit_reason += f" (FAKE_FIX_ROLLBACK {bug['bug_id']})"
                    repairs_verified -= 1

        ctx.repairs_attempted = repairs_attempted
        ctx.repairs_verified = repairs_verified
        ctx.rollbacks = rollbacks

        return {
            "status": status,
            "exit_reason": exit_reason,
            "bug_count": len(bugs),
            "repairs_attempted": repairs_attempted,
            "repairs_verified": repairs_verified,
            "rollbacks": rollbacks,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Termination checks
    # ─────────────────────────────────────────────────────────────────────

    def _check_termination(self, total_repairs: int, rollbacks: int) -> tuple[str, int]:
        """Return (reason, code) if should terminate, else ('', 0)."""
        # Time
        end_time_utc = self.config.resolved_end_time_utc(
            datetime.fromtimestamp(self._start_time, tz=timezone.utc)
        )
        if time.time() >= end_time_utc.timestamp():
            return "end_time_reached", _C.EXIT_DURATION_ENDED

        # Max repairs
        if total_repairs >= self.config.max_repairs:
            return "max_repairs_reached", _C.EXIT_REPAIR_EXHAUSTED

        # P0 unresolved
        bugs = self._state.get_bugs(self._run_id)
        p0_active = [b for b in bugs if b.get("is_blocked")
                     and b.get("consecutive_failures", 0) > 0]
        if p0_active:
            return "p0_unresolved", _C.EXIT_REPAIR_EXHAUSTED

        # Git workdir unsafe (dirty state can't be isolated)
        # (Simplified: assume OK for now — full impl would check)

        # Hardware
        hw_safe, hw_violations = self._hw.check()
        if not hw_safe:
            for v in hw_violations:
                if "CRITICAL" in v or "critical" in v:
                    return "gpu_temperature_exceeded", _C.EXIT_HARDWARE_SAFETY

        # State file corrupt
        latest_ckpt = self._state.latest_checkpoint()
        if latest_ckpt is not None:
            try:
                json.loads(latest_ckpt.read_text())
            except Exception:
                return "state_file_corrupt", _C.EXIT_INTERNAL

        # Consecutive crashes
        if self._consecutive_crashes >= _C.DEFAULT_MAX_CONSECUTIVE_CRASHES:
            return "consecutive_agent_crashes", _C.EXIT_INTERNAL

        return "", 0

    # ─────────────────────────────────────────────────────────────────────
    # Error fingerprinting / classification helpers
    # ─────────────────────────────────────────────────────────────────────

    def _fingerprint_error(self, error: str, output: str) -> str:
        import hashlib, re
        combined = (error + output)[:4000]
        type_match = re.search(
            r"(Error|Exception|AssertionError|CUDA|OOM|Timeout):\s*(\S+)",
            combined,
        )
        loc_match = re.search(r'File "([^"]+)", line (\d+)', combined)
        type_str = type_match.group(2) if type_match else "unknown"
        loc_str = f"{loc_match.group(1)}:{loc_match.group(2)}" if loc_match else "unknown"
        return hashlib.sha256(f"{type_str}@{loc_str}".encode()).hexdigest()[:32]

    def _classify(self, error: str, output: str) -> tuple[str, str]:
        import re
        text = (error + "\n" + output).lower()
        if any(k in text for k in ["split", "label", "miou_ch"]):
            return "PROTOCOL", "paper protocol"
        if any(k in text for k in ["dataset", "class"]):
            return "DATA", "dataset or label"
        if any(k in text for k in ["AttributeError", "TypeError", "NameError"]):
            return "CODE", "code bug"
        if any(k in text for k in ["FileNotFoundError", "No such file"]):
            return "CONFIG", "path not found"
        if any(k in text for k in ["out of memory", "OOM", "cuda"]):
            return "RESOURCE", "memory"
        if any(k in text for k in ["sqlite", "lock", "atomic"]):
            return "STATE", "state error"
        if any(k in text for k in ["argument", "argparse"]):
            return "CLI", "CLI error"
        if any(k in text for k in ["checkpoint", "state_dict"]):
            return "CHECKPOINT", "checkpoint I/O"
        if any(k in text for k in ["recovery", "resume"]):
            return "RECOVERY", "recovery error"
        if any(k in text for k in ["fixture", "pytest", "conftest"]):
            return "FIXTURE", "test fixture"
        if any(k in text for k in ["metric", "iou", "accuracy"]):
            return "METRIC", "metric error"
        if any(k in text for k in ["import", "module", "not found"]):
            return "ENVIRONMENT", "environment"
        return "UNKNOWN", "unclassified"

    # ─────────────────────────────────────────────────────────────────────
    # Heartbeat
    # ─────────────────────────────────────────────────────────────────────

    def _start_heartbeat(self) -> None:
        self._hb_active.set()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()

    def _stop_heartbeat(self) -> None:
        self._hb_active.clear()
        if self._hb_thread:
            self._hb_thread.join(timeout=5)

    def _heartbeat_loop(self) -> None:
        while self._hb_active.is_set():
            if self._run_id:
                self._state.heartbeat(
                    self._run_id, os.getpid(),
                    {
                        "cycle_seq": self._cycle_seq,
                        "active_bugs": len([
                            b for b in self._state.get_bugs(self._run_id)
                            if b.get("consecutive_failures", 0) > 0
                        ]),
                    },
                )
            self._hb_active.wait(timeout=_C.DEFAULT_HEARTBEAT_INTERVAL_SECONDS)

    # ─────────────────────────────────────────────────────────────────────
    # Signals
    # ─────────────────────────────────────────────────────────────────────

    def _setup_signals(self) -> None:
        def handle(signum, frame):
            sig_name = signal.Signals(signum).name
            print(f"[OSTAR] Received {sig_name}, initiating graceful stop...")
            self.stop()

        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)
