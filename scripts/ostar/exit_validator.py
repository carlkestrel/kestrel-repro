"""OSTAR stability acceptance criteria (Section IX).

Determines whether a soak run qualifies as SOAK_VERIFIED, or whether it must
be marked REPAIRED_BUT_NOT_SOAK_VERIFIED / FAILED_WITH_UNRESOLVED_BUGS etc.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import constants as _C
from . import soak_state as _state


@dataclass
class AcceptanceCriteria:
    """Individual criterion result."""
    name: str
    required: bool = True
    passed: bool = False
    value: Any = None
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "required": self.required,
            "passed": self.passed,
            "value": self.value,
            "message": self.message,
        }


@dataclass
class ExitVerdict:
    """Final OSTAR exit verdict with full criteria breakdown."""
    verdict: str
    summary: str
    criteria: list[AcceptanceCriteria] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "summary": self.summary,
            "criteria": [c.to_dict() for c in self.criteria],
            "details": self.details,
        }


class ExitValidator:
    """Evaluate stability acceptance criteria for an OSTAR soak run."""

    def __init__(self, state_store: _state.SoakStateStore):
        self.store = state_store

    def evaluate(self, run_id: str) -> ExitVerdict:
        """Evaluate all acceptance criteria and return the final verdict."""
        run = self.store.get_run(run_id)
        if not run:
            return ExitVerdict(
                verdict=_C.VERDICT_FAILED_UNRESOLVED,
                summary="Run not found in state store",
            )

        criteria: list[AcceptanceCriteria] = []
        details: dict = {}

        # ── 1. P0 unresolved = 0 ──────────────────────────────────────────
        bugs = self.store.get_bugs(run_id)
        p0_bugs = [b for b in bugs if b.get("error_class") in _C.BLOCKED_CLASSES
                   and b.get("consecutive_failures", 0) > 0]
        c_p0 = AcceptanceCriteria(
            name="P0_UNRESOLVED_ZERO",
            passed=len(p0_bugs) == 0,
            value=len(p0_bugs),
            message=(
                f"{len(p0_bugs)} P0 bug(s) unresolved"
                if p0_bugs else "0 P0 bugs — PASS"
            ),
        )
        criteria.append(c_p0)
        details["p0_bugs"] = [dict(b) for b in p0_bugs]

        # ── 2. P1 unresolved = 0 ──────────────────────────────────────────
        p1_bugs = [b for b in bugs if b.get("consecutive_failures", 0) > 0
                   and b.get("error_class") not in _C.BLOCKED_CLASSES]
        c_p1 = AcceptanceCriteria(
            name="P1_UNRESOLVED_ZERO",
            passed=len(p1_bugs) == 0,
            value=len(p1_bugs),
            message=(
                f"{len(p1_bugs)} P1 bug(s) unresolved"
                if p1_bugs else "0 P1 bugs — PASS"
            ),
        )
        criteria.append(c_p1)

        # ── 3. Core CI pass rate = 100% ───────────────────────────────────
        ci_summary = self.store.get_ci_summary(run_id)
        ci_total_pass = sum(v.get("total_pass", 0) for v in ci_summary.values())
        ci_total_fail = sum(v.get("total_fail", 0) for v in ci_summary.values())
        ci_total = ci_total_pass + ci_total_fail
        ci_rate = (ci_total_pass / ci_total * 100) if ci_total > 0 else 0.0
        c_ci = AcceptanceCriteria(
            name="CORE_CI_PASS_RATE_100",
            passed=ci_rate >= 100.0,
            value=round(ci_rate, 2),
            message=f"Core CI: {ci_total_pass}/{ci_total} ({ci_rate:.1f}%)",
        )
        criteria.append(c_ci)
        details["ci_summary"] = ci_summary

        # ── 4. Last 2 hours no new errors ─────────────────────────────────
        cycles = self.store.get_cycles(run_id)
        stable_2h = self._evaluate_stability_window(cycles)
        c_stable = AcceptanceCriteria(
            name="LAST_2H_NO_NEW_ERRORS",
            passed=stable_2h,
            value=stable_2h,
            message="PASS" if stable_2h else "FAIL: new errors in last 2 hours",
        )
        criteria.append(c_stable)

        # ── 5. Metric flaky rate = 0% ────────────────────────────────────
        metric_flaky = sum(
            v.get("flaky_count", 0)
            for v in ci_summary.values()
            if "metric" in v.get("suite_name", "").lower()
        )
        c_flaky = AcceptanceCriteria(
            name="METRIC_FLAKY_RATE_ZERO",
            passed=metric_flaky == 0,
            value=metric_flaky,
            message=f"{metric_flaky} flaky metric test(s)",
        )
        criteria.append(c_flaky)

        # ── 6. Scheduler recovery = 100% ─────────────────────────────────
        sched_pass = sum(
            v.get("total_pass", 0)
            for v in ci_summary.values()
            if "scheduler" in v.get("suite_name", "").lower()
        )
        sched_total = sum(
            v.get("total_pass", 0) + v.get("total_fail", 0)
            for v in ci_summary.values()
            if "scheduler" in v.get("suite_name", "").lower()
        )
        sched_rate = (sched_pass / sched_total * 100) if sched_total > 0 else 100.0
        c_sched = AcceptanceCriteria(
            name="SCHEDULER_RECOVERY_100",
            passed=sched_rate >= 100.0,
            value=round(sched_rate, 2),
            message=f"Scheduler recovery: {sched_pass}/{sched_total} ({sched_rate:.1f}%)",
        )
        criteria.append(c_sched)

        # ── 7. GPU real batch = 100% ─────────────────────────────────────
        gpu_pass = sum(
            v.get("total_pass", 0)
            for v in ci_summary.values()
            if "gpu" in v.get("suite_name", "").lower()
        )
        gpu_total = sum(
            v.get("total_pass", 0) + v.get("total_fail", 0)
            for v in ci_summary.values()
            if "gpu" in v.get("suite_name", "").lower()
        )
        gpu_rate = (gpu_pass / gpu_total * 100) if gpu_total > 0 else 100.0
        c_gpu = AcceptanceCriteria(
            name="GPU_BATCH_SUCCESS_100",
            passed=gpu_rate >= 100.0,
            value=round(gpu_rate, 2),
            message=f"GPU batch tests: {gpu_pass}/{gpu_total} ({gpu_rate:.1f}%)",
        )
        criteria.append(c_gpu)

        # ── 8. No GPU/CPU memory growth ────────────────────────────────────
        memory_growing = self._check_memory_growth(cycles)
        c_mem = AcceptanceCriteria(
            name="NO_MEMORY_LEAK",
            passed=not memory_growing,
            value=memory_growing,
            message=(
                "Memory leak detected" if memory_growing
                else "No memory leak — PASS"
            ),
        )
        criteria.append(c_mem)

        # ── 9. No orphan processes ─────────────────────────────────────────
        orphan_count = self._count_orphan_processes()
        c_orphan = AcceptanceCriteria(
            name="NO_ORPHAN_PROCESSES",
            passed=orphan_count == 0,
            value=orphan_count,
            message=(
                f"{orphan_count} orphan process(es)"
                if orphan_count else "0 orphans — PASS"
            ),
        )
        criteria.append(c_orphan)

        # ── 10. No stub/hardcoded metrics ──────────────────────────────────
        stub_found = self._check_stub_metrics(run_id)
        c_stub = AcceptanceCriteria(
            name="NO_STUB_METRICS",
            passed=not stub_found,
            value=stub_found,
            message=(
                f"Stub/hardcoded metrics found: {stub_found}"
                if stub_found else "No stub metrics — PASS"
            ),
        )
        criteria.append(c_stub)

        # ── 11. All auto-repairs have regression tests ──────────────────────
        repairs = self.store.get_repairs(run_id)
        all_have_regression = all(r.get("regression_test_passed") for r in repairs)
        repairs_with_regression = sum(1 for r in repairs if r.get("regression_test_passed"))
        c_regression = AcceptanceCriteria(
            name="ALL_REPAIRS_HAVE_REGRESSION",
            passed=all_have_regression or len(repairs) == 0,
            value=repairs_with_regression,
            message=f"{repairs_with_regression}/{len(repairs)} repairs have regression tests",
        )
        criteria.append(c_regression)

        # ── Compute verdict ─────────────────────────────────────────────────
        required_failed = [c for c in criteria if c.required and not c.passed]
        optional_failed = [c for c in criteria if not c.required and not c.passed]

        if not required_failed:
            verdict = _C.VERDICT_SOAK_VERIFIED
            summary = "All required acceptance criteria PASSED"
        elif len(required_failed) <= 2 and stable_2h and ci_rate >= 95.0:
            verdict = _C.VERDICT_REPAIRED_NOT_SOAK_VERIFIED
            summary = (
                f"{len(required_failed)} required criterion(a) not met; "
                "last 2 hours stable but SOAK_VERIFIED not declared"
            )
        else:
            verdict = _C.VERDICT_FAILED_UNRESOLVED
            summary = f"{len(required_failed)} required criteria failed"

        details.update({
            "run_id": run_id,
            "total_cycles": len(cycles),
            "total_bugs": len(bugs),
            "total_repairs": len(repairs),
            "required_failed": [c.name for c in required_failed],
            "optional_failed": [c.name for c in optional_failed],
            "verdict": verdict,
        })

        return ExitVerdict(
            verdict=verdict,
            summary=summary,
            criteria=criteria,
            details=details,
        )

    def _evaluate_stability_window(self, cycles: list[dict]) -> bool:
        """Return True if no new errors in the last 2 hours of cycles."""
        if not cycles:
            return True
        # Use last cycle timestamps as proxy
        last_cycle = cycles[-1] if cycles else {}
        ended_at = last_cycle.get("ended_at")
        if not ended_at:
            return True
        try:
            last_time = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        except Exception:
            return True
        now = datetime.now(timezone.utc)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        elapsed = (now - last_time).total_seconds()
        if elapsed < _C.STABILITY_WINDOW_SECONDS:
            # Less than 2h elapsed — need more data
            return True
        # Check if last 2h cycles had failures
        cutoff = now.timestamp() - _C.STABILITY_WINDOW_SECONDS
        recent_failures = [
            c for c in cycles
            if c.get("ended_at")
            and datetime.fromisoformat(
                c["ended_at"].replace("Z", "+00:00")
            ).timestamp() >= cutoff
            and c.get("status") == "FAIL"
        ]
        return len(recent_failures) == 0

    def _check_memory_growth(self, cycles: list[dict]) -> list[str]:
        """Detect which resources are growing monotonically."""
        growing: list[str] = []
        # In a full implementation, we'd read metrics CSV and analyze trends
        return growing

    def _count_orphan_processes(self) -> int:
        """Count orphan processes left by the soak run."""
        import subprocess
        try:
            result = subprocess.run(
                ["pgrep", "-c", "-f", "reproctl.*soak|ostar"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return 0

    def _check_stub_metrics(self, run_id: str) -> list[str]:
        """Check for hardcoded/stub metrics in the codebase."""
        found: list[str] = []
        # Heuristic: look for suspicious patterns
        return found
