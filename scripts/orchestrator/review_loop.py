"""
NORA-style Review Loop - Iterative verification for paper reproduction.

This module implements NORA's auto-review-loop adapted for paper reproduction:
- Iterative verification (up to max_iterations)
- Evidence collection and validation
- Failure analysis and fix suggestions
- Automatic progression or stop on repeated failures
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .event_journal import EventJournal
from .state_store import StateStore
from .verifier import Verifier


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ReviewResult:
    """Result of a review iteration."""

    iteration: int
    status: str  # "pass", "fail", "block"
    verdict: str  # "GO", "PIVOT", "NO-GO"
    evidence: dict[str, Any]
    failures: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)


@dataclass
class ReviewLoopConfig:
    """Configuration for the review loop."""

    max_iterations: int = 3
    auto_stop_on_fail: bool = True
    block_on_repeated_fail: bool = True
    consecutive_fail_threshold: int = 2
    collect_evidence: bool = True
    generate_suggestions: bool = True
    record_metrics: bool = True


class ReviewLoop:
    """
    NORA-style iterative review loop adapted for paper reproduction.

    Workflow:
    1. Verify evidence from completed tasks
    2. Analyze failures and collect metrics
    3. Generate fix suggestions
    4. Check if criteria are met (GO/PIVOT/NO-GO)
    5. If failed and iterations remain, continue
    6. If repeated failures, block or pivot

    Adapted from NORA's auto-review-loop for reproduction verification:
    - GO: Evidence validates the reproduction
    - PIVOT: Strategy change needed (e.g., different approach)
    - NO-GO: Reproduction failed, stop further attempts
    """

    def __init__(
        self,
        project_root: str | Path,
        state_store: StateStore,
        event_journal: EventJournal | None = None,
        verifier: Verifier | None = None,
        config: ReviewLoopConfig | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.state_store = state_store
        self.event_journal = event_journal
        self.verifier = verifier or Verifier(project_root, state_store, None)
        self.config = config or ReviewLoopConfig()
        self._iteration = 0
        self._results: list[ReviewResult] = []
        self._consecutive_fails = 0

    def run(self, context: dict[str, Any] | None = None) -> ReviewResult:
        """
        Run the review loop with up to max_iterations.

        Args:
            context: Optional context including:
                - task_ids: List of task IDs to review
                - required_metrics: Dict of required metric thresholds
                - evidence_patterns: Required evidence patterns

        Returns:
            Final ReviewResult with GO/PIVOT/NO-GO verdict
        """
        context = context or {}
        task_ids = context.get("task_ids", [])
        required_metrics = context.get("required_metrics", {})
        evidence_patterns = context.get("evidence_patterns", [])

        self._results = []
        self._consecutive_fails = 0

        for iteration in range(1, self.config.max_iterations + 1):
            self._iteration = iteration
            result = self._review_iteration(
                iteration, task_ids, required_metrics, evidence_patterns
            )
            self._results.append(result)

            self.state_store.record_event(
                "REVIEW_ITERATION",
                payload={
                    "iteration": iteration,
                    "status": result.status,
                    "verdict": result.verdict,
                    "failures": result.failures,
                    "suggestions": result.suggestions,
                },
            )

            if result.verdict == "GO":
                return result

            if result.status == "fail":
                self._consecutive_fails += 1

            if result.status == "block":
                break

            if (
                self.config.auto_stop_on_fail
                and self._consecutive_fails >= self.config.consecutive_fail_threshold
            ):
                result.verdict = "NO-GO"
                result.suggestions.append(
                    f"Stopped after {self._consecutive_fails} consecutive failures"
                )
                break

            time.sleep(0.1)

        return self._aggregate_results()

    def _review_iteration(
        self,
        iteration: int,
        task_ids: list[str],
        required_metrics: dict[str, float],
        evidence_patterns: list[str],
    ) -> ReviewResult:
        """Execute a single review iteration."""
        evidence = self._collect_evidence(task_ids)
        failures = self._analyze_failures(evidence, required_metrics, evidence_patterns)
        suggestions = self._generate_suggestions(failures, evidence)
        metrics = self._collect_metrics(evidence)

        if not failures:
            status = "pass"
            verdict = "GO"
        elif self._should_pivot(failures, evidence):
            status = "fail"
            verdict = "PIVOT"
        else:
            status = "fail"
            verdict = "NO-GO"

        return ReviewResult(
            iteration=iteration,
            status=status,
            verdict=verdict,
            evidence=evidence,
            failures=failures,
            suggestions=suggestions,
            metrics=metrics,
        )

    def _collect_evidence(self, task_ids: list[str]) -> dict[str, Any]:
        """Collect evidence from tasks."""
        evidence: dict[str, Any] = {
            "tasks": [],
            "artifacts": [],
            "metrics": {},
            "logs": [],
        }

        tasks = self.state_store.list_tasks()
        if task_ids:
            tasks = [t for t in tasks if t["id"] in task_ids]

        for task in tasks:
            task_evidence = {
                "task_id": task["id"],
                "name": task["name"],
                "status": task["status"],
                "gate": task["gate"],
            }

            if task["status"] == "PASS":
                task_evidence["passed"] = True
                evidence["tasks"].append(task_evidence)
            elif task["status"] == "FAIL":
                task_evidence["passed"] = False
                task_evidence["failure_reason"] = task.get("failure_reason")
                evidence["tasks"].append(task_evidence)
            elif task["status"] in {"RUNNING", "VERIFYING"}:
                evidence["tasks"].append(task_evidence)

        evidence["pass_rate"] = self._calculate_pass_rate(evidence["tasks"])
        return evidence

    def _analyze_failures(
        self,
        evidence: dict[str, Any],
        required_metrics: dict[str, float],
        evidence_patterns: list[str],
    ) -> list[dict[str, Any]]:
        """Analyze failures and missing evidence."""
        failures: list[dict[str, Any]] = []

        failed_tasks = [t for t in evidence.get("tasks", []) if not t.get("passed")]
        for task in failed_tasks:
            failures.append(
                {
                    "type": "task_failure",
                    "task_id": task["task_id"],
                    "reason": task.get("failure_reason", "unknown"),
                }
            )

        if required_metrics:
            for metric_name, threshold in required_metrics.items():
                actual = evidence.get("metrics", {}).get(metric_name)
                if actual is None:
                    failures.append(
                        {
                            "type": "missing_metric",
                            "metric": metric_name,
                            "required": threshold,
                        }
                    )
                elif actual < threshold:
                    failures.append(
                        {
                            "type": "metric_below_threshold",
                            "metric": metric_name,
                            "actual": actual,
                            "required": threshold,
                        }
                    )

        for pattern in evidence_patterns:
            if not self._pattern_exists(evidence, pattern):
                failures.append(
                    {
                        "type": "missing_evidence",
                        "pattern": pattern,
                    }
                )

        return failures

    def _generate_suggestions(
        self, failures: list[dict[str, Any]], evidence: dict[str, Any]
    ) -> list[str]:
        """Generate fix suggestions based on failures."""
        suggestions: list[str] = []

        for failure in failures:
            if failure["type"] == "task_failure":
                suggestions.append(
                    f"Fix task {failure['task_id']}: {failure.get('reason', 'unknown error')}"
                )
            elif failure["type"] == "missing_metric":
                suggestions.append(
                    f"Collect metric {failure['metric']} (required: {failure['required']})"
                )
            elif failure["type"] == "metric_below_threshold":
                suggestions.append(
                    f"Improve metric {failure['metric']}: "
                    f"current={failure['actual']:.4f}, required={failure['required']:.4f}"
                )
            elif failure["type"] == "missing_evidence":
                suggestions.append(f"Generate evidence matching pattern: {failure['pattern']}")

        if evidence.get("pass_rate", 0) < 0.8:
            suggestions.append(f"Pass rate {evidence['pass_rate']:.1%} below 80% threshold")

        return suggestions

    def _collect_metrics(self, evidence: dict[str, Any]) -> dict[str, float]:
        """Collect summary metrics."""
        metrics: dict[str, float] = {}

        if evidence.get("tasks"):
            total = len(evidence["tasks"])
            passed = sum(1 for t in evidence["tasks"] if t.get("passed"))
            metrics["pass_rate"] = passed / total if total > 0 else 0
            metrics["total_tasks"] = total
            metrics["passed_tasks"] = passed
            metrics["failed_tasks"] = total - passed

        return metrics

    def _should_pivot(self, failures: list[dict[str, Any]], evidence: dict[str, Any]) -> bool:
        """Determine if strategy should pivot based on failure patterns."""
        failure_types = [f["type"] for f in failures]

        if "missing_metric" in failure_types and "task_failure" in failure_types:
            return True

        if evidence.get("pass_rate", 0) > 0.5:
            return True

        return False

    def _pattern_exists(self, evidence: dict[str, Any], pattern: str) -> bool:
        """Check if evidence pattern exists."""
        evidence_str = json.dumps(evidence, default=str)
        return pattern.lower() in evidence_str.lower()

    def _calculate_pass_rate(self, tasks: list[dict]) -> float:
        """Calculate pass rate from task list."""
        if not tasks:
            return 0.0
        passed = sum(1 for t in tasks if t.get("passed"))
        return passed / len(tasks)

    def _aggregate_results(self) -> ReviewResult:
        """Aggregate all iteration results into final verdict."""
        if not self._results:
            return ReviewResult(
                iteration=0,
                status="block",
                verdict="NO-GO",
                evidence={},
                failures=[{"type": "no_results", "reason": "No review iterations completed"}],
                suggestions=["Check system configuration and retry"],
            )

        last_result = self._results[-1]

        all_failures = []
        all_suggestions = []
        for result in self._results:
            all_failures.extend(result.failures)
            all_suggestions.extend(result.suggestions)

        unique_suggestions = list(dict.fromkeys(all_suggestions))

        if self._consecutive_fails >= self.config.consecutive_fail_threshold:
            verdict = "NO-GO"
        else:
            verdict = last_result.verdict

        return ReviewResult(
            iteration=len(self._results),
            status="block" if verdict == "NO-GO" else "fail",
            verdict=verdict,
            evidence=last_result.evidence,
            failures=all_failures,
            suggestions=unique_suggestions,
            metrics=last_result.metrics,
        )

    def get_results(self) -> list[ReviewResult]:
        """Get all review results."""
        return self._results.copy()

    def get_latest_result(self) -> ReviewResult | None:
        """Get the most recent review result."""
        return self._results[-1] if self._results else None

    def get_verdict_summary(self) -> dict[str, Any]:
        """Get a summary of the verdict."""
        latest = self.get_latest_result()
        if latest is None:
            return {"verdict": "UNKNOWN", "iterations": 0}

        return {
            "verdict": latest.verdict,
            "iterations": len(self._results),
            "final_status": latest.status,
            "pass_rate": latest.metrics.get("pass_rate", 0),
            "failure_count": len(latest.failures),
            "consecutive_fails": self._consecutive_fails,
            "suggestions": latest.suggestions,
        }


class ReviewLoopFactory:
    """Factory for creating configured ReviewLoop instances."""

    _registry: dict[str, ReviewLoopConfig] = {}

    @classmethod
    def register(cls, name: str, config: ReviewLoopConfig) -> None:
        """Register a named configuration."""
        cls._registry[name] = config

    @classmethod
    def get(cls, name: str) -> ReviewLoopConfig | None:
        """Get a named configuration."""
        return cls._registry.get(name)

    @classmethod
    def create_strict(cls) -> ReviewLoopConfig:
        """Create a strict review loop config (fewer iterations)."""
        return ReviewLoopConfig(
            max_iterations=2,
            auto_stop_on_fail=True,
            block_on_repeated_fail=True,
            consecutive_fail_threshold=1,
        )

    @classmethod
    def create_lenient(cls) -> ReviewLoopConfig:
        """Create a lenient review loop config (more iterations)."""
        return ReviewLoopConfig(
            max_iterations=5,
            auto_stop_on_fail=False,
            block_on_repeated_fail=False,
            consecutive_fail_threshold=3,
        )

    @classmethod
    def create_nora_style(cls) -> ReviewLoopConfig:
        """Create NORA-style review loop config."""
        return ReviewLoopConfig(
            max_iterations=4,
            auto_stop_on_fail=True,
            block_on_repeated_fail=True,
            consecutive_fail_threshold=2,
            collect_evidence=True,
            generate_suggestions=True,
            record_metrics=True,
        )


ReviewLoopFactory.register("strict", ReviewLoopFactory.create_strict())
ReviewLoopFactory.register("lenient", ReviewLoopFactory.create_lenient())
ReviewLoopFactory.register("nora", ReviewLoopFactory.create_nora_style())
