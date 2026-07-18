"""
Metric Auditor Agent - NORA-style specialist for data and metric auditing.

This agent validates metrics, checks numerical parity, and ensures reproducibility.
"""
from __future__ import annotations

from typing import Any

from .base import (
    AgentRegistry,
    AgentResult,
    HandoffContext,
    SpecialistAgent,
)


class MetricAuditorAgent(SpecialistAgent):
    """
    Agent for auditing metrics and data.

    Responsibilities:
    - Validate metric definitions
    - Check numerical parity
    - Audit data contracts
    - Prepare handoff for HardwareFitAgent
    """

    agent_type = "metric-auditor"
    agent_name = "MetricAuditorAgent"
    description = "Audits metrics, validates numerical parity, and checks data contracts"
    capabilities = [
        "metric_validation",
        "numerical_parity",
        "data_contract_audit",
        "threshold_checking",
    ]
    next_agents = ["hardware-fit"]

    def execute(self, context: HandoffContext) -> AgentResult:
        """Execute metric auditing."""
        claims = context.data.get("claims", [])
        requirements = context.data.get("requirements", [])
        method_summary = context.data.get("method_summary", {})

        metric_targets = self._extract_metric_targets(requirements)
        data_contracts = self._audit_data_contracts(requirements)

        parity_criteria = self._define_parity_criteria(metric_targets)

        self.prepare_handoff(context, {
            "metric_targets": metric_targets,
            "data_contracts": data_contracts,
            "parity_criteria": parity_criteria,
        })

        return AgentResult(
            agent_type=self.agent_type,
            agent_id=self.agent_id,
            status="success",
            output={
                "metric_targets": metric_targets,
                "data_contracts": data_contracts,
                "parity_criteria": parity_criteria,
                "metrics_defined": len(metric_targets),
                "contracts_defined": len(data_contracts),
            },
            handoff={
                "metric_targets": metric_targets,
                "data_contracts": data_contracts,
                "parity_criteria": parity_criteria,
                "next_agent": "hardware-fit",
            },
            metadata={
                "claims_count": len(claims),
                "requirements_count": len(requirements),
                "complexity": method_summary.get("complexity", "unknown"),
            },
        )

    def _extract_metric_targets(self, requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract metric targets from requirements."""
        targets = []

        for req in requirements:
            if req.get("type") == "metric_target":
                targets.append({
                    "metric": req.get("metric", "unknown"),
                    "target": req.get("target", 0.0),
                    "threshold": req.get("threshold", 0.0),
                    "unit": req.get("unit", ""),
                    "direction": "higher_is_better" if req.get("target", 0) > 0 else "lower_is_better",
                })

        if not targets:
            targets.append({
                "metric": "accuracy",
                "target": 90.0,
                "threshold": 85.0,
                "unit": "%",
                "direction": "higher_is_better",
            })

        return targets

    def _audit_data_contracts(self, requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Audit data contract requirements."""
        contracts = []

        for req in requirements:
            if req.get("type") == "dataset":
                contracts.append({
                    "contract_type": "dataset",
                    "description": req.get("description", "Dataset requirement"),
                    "required": req.get("required", True),
                    "validation_checks": [
                        "download_verification",
                        "checksum_validation",
                        "format_verification",
                        "split_integrity",
                    ],
                })

        contracts.append({
            "contract_type": "environment",
            "description": "Environment reproducibility contract",
            "required": True,
            "validation_checks": [
                "python_version",
                "package_versions",
                "cuda_version",
                "random_seeds",
            ],
        })

        return contracts

    def _define_parity_criteria(self, metric_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Define numerical parity criteria."""
        criteria = []

        for target in metric_targets:
            metric = target["metric"]
            tolerance = self._get_tolerance(metric)

            criteria.append({
                "metric": metric,
                "tolerance": tolerance,
                "relative_tolerance": tolerance / 100 if target["unit"] == "%" else 0.01,
                "absolute_tolerance": 1e-4,
                "method": "relative_and_absolute",
            })

        return criteria

    def _get_tolerance(self, metric: str) -> float:
        """Get acceptable tolerance for a metric."""
        tolerances = {
            "accuracy": 0.5,
            "loss": 0.01,
            "f1": 0.5,
            "precision": 0.5,
            "recall": 0.5,
            "speedup": 0.1,
            "throughput": 0.1,
            "latency": 0.1,
        }
        return tolerances.get(metric.lower(), 1.0)

    def validate_metric(
        self,
        metric_name: str,
        actual: float,
        target: float,
        threshold: float,
    ) -> dict[str, Any]:
        """Validate a single metric against target."""
        passes = actual >= threshold

        return {
            "metric": metric_name,
            "actual": actual,
            "target": target,
            "threshold": threshold,
            "passes": passes,
            "gap": target - actual,
            "gap_percentage": ((target - actual) / target * 100) if target != 0 else 0,
        }

    def check_parity(
        self,
        metric_name: str,
        expected: float,
        actual: float,
        criteria: dict[str, Any],
    ) -> dict[str, Any]:
        """Check numerical parity between expected and actual."""
        tolerance = criteria.get("relative_tolerance", 0.01)
        abs_tolerance = criteria.get("absolute_tolerance", 1e-4)

        if expected == 0:
            is_close = abs(actual) < abs_tolerance
        else:
            relative_diff = abs(actual - expected) / abs(expected)
            is_close = relative_diff <= tolerance

        is_also_close = abs(actual - expected) <= abs_tolerance

        return {
            "metric": metric_name,
            "expected": expected,
            "actual": actual,
            "tolerance": tolerance,
            "absolute_tolerance": abs_tolerance,
            "parity": is_close or is_also_close,
            "relative_diff": abs(actual - expected) / abs(expected) if expected != 0 else 0,
            "absolute_diff": abs(actual - expected),
        }


AgentRegistry.register(MetricAuditorAgent)
