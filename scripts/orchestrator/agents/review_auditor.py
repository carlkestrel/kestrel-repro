"""
Review Auditor Agent - NORA-style specialist for final review and verdict.

This agent performs final review and generates GO/PIVOT/NO-GO verdict.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import (
    AgentResult,
    AgentRegistry,
    HandoffContext,
    SpecialistAgent,
    utc_now,
)


class ReviewAuditorAgent(SpecialistAgent):
    """
    Agent for final review and verdict.

    Responsibilities:
    - Synthesize all agent results
    - Generate final verdict (GO/PIVOT/NO-GO)
    - Create summary report
    - Determine next steps
    """

    agent_type = "review-auditor"
    agent_name = "ReviewAuditorAgent"
    description = "Performs final review and generates GO/PIVOT/NO-GO verdict"
    capabilities = [
        "final_review",
        "verdict_generation",
        "report_generation",
        "recommendation",
    ]
    next_agents = []

    def execute(self, context: HandoffContext) -> AgentResult:
        """Execute final review."""
        evidence = context.data.get("evidence", {})
        chain = context.data.get("chain", [])
        verification_result = context.data.get("verification_result", {})
        hardware_info = context.data.get("hardware_info", {})
        fit_recommendation = context.data.get("fit_recommendation", {})
        metric_targets = context.data.get("metric_targets", [])
        requirements = context.data.get("requirements", [])

        completeness = verification_result.get("completeness", {})

        scores = self._calculate_scores(
            evidence, chain, completeness, fit_recommendation
        )

        verdict = self._generate_verdict(scores)

        summary = self._generate_summary(
            scores, verdict, chain, metric_targets, requirements
        )

        recommendations = self._generate_recommendations(
            verdict, scores, fit_recommendation, requirements
        )

        self.prepare_handoff(context, {
            "scores": scores,
            "verdict": verdict,
            "summary": summary,
            "recommendations": recommendations,
        })

        return AgentResult(
            agent_type=self.agent_type,
            agent_id=self.agent_id,
            status="success",
            output={
                "scores": scores,
                "verdict": verdict,
                "summary": summary,
                "recommendations": recommendations,
            },
            handoff={
                "verdict": verdict,
                "scores": scores,
                "summary": summary,
                "recommendations": recommendations,
                "next_agent": None,
            },
            metadata={
                "evidence_count": len(chain),
                "completeness_score": completeness.get("score", 0),
                "hardware_fit": fit_recommendation.get("status", "unknown"),
            },
        )

    def _calculate_scores(
        self,
        evidence: dict[str, Any],
        chain: list[dict[str, Any]],
        completeness: dict[str, Any],
        fit_recommendation: dict[str, Any],
    ) -> dict[str, float]:
        """Calculate overall scores."""
        scores = {
            "evidence": 0,
            "hardware": 0,
            "completeness": 0,
            "overall": 0,
        }

        chain_length = len([e for e in chain if e.get("type") in {"claim", "artifact"}])
        scores["evidence"] = min(100, chain_length * 20)

        completeness_score = completeness.get("score", 0)
        scores["completeness"] = completeness_score

        fit_score = fit_recommendation.get("score", 0)
        scores["hardware"] = fit_score

        scores["overall"] = (
            scores["evidence"] * 0.3 +
            scores["completeness"] * 0.4 +
            scores["hardware"] * 0.3
        )

        return scores

    def _generate_verdict(self, scores: dict[str, float]) -> str:
        """Generate GO/PIVOT/NO-GO verdict."""
        overall = scores.get("overall", 0)
        evidence = scores.get("evidence", 0)
        hardware = scores.get("hardware", 0)

        if overall >= 70 and evidence >= 50 and hardware >= 50:
            return "GO"
        elif overall >= 40 or hardware >= 30:
            return "PIVOT"
        else:
            return "NO-GO"

    def _generate_summary(
        self,
        scores: dict[str, float],
        verdict: str,
        chain: list[dict[str, Any]],
        metric_targets: list[dict[str, Any]],
        requirements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate summary report."""
        summary = {
            "timestamp": utc_now(),
            "verdict": verdict,
            "scores": scores,
            "metrics": {
                "target_count": len(metric_targets),
                "met_count": 0,
                "total_count": len(requirements),
            },
            "evidence": {
                "chain_length": len(chain),
                "verified_count": sum(1 for e in chain if e.get("status") == "verified"),
            },
        }

        for entry in chain:
            if entry.get("status") == "verified":
                summary["metrics"]["met_count"] += 1

        return summary

    def _generate_recommendations(
        self,
        verdict: str,
        scores: dict[str, float],
        fit_recommendation: dict[str, Any],
        requirements: list[dict[str, Any]],
    ) -> list[str]:
        """Generate recommendations based on verdict."""
        recommendations = []

        if verdict == "GO":
            recommendations.append("Proceed with full training")
            recommendations.append("Run comprehensive evaluation")
            recommendations.append("Generate final report")
        elif verdict == "PIVOT":
            recommendations.append("Consider alternative approach")
            if scores.get("evidence", 0) < 50:
                recommendations.append("Collect more evidence before proceeding")
            if scores.get("hardware", 0) < 50:
                recommendations.append("Optimize for available hardware or reduce scope")
            recommendations.append("Review metric targets and adjust if needed")
        else:
            recommendations.append("Do not proceed with current approach")
            if scores.get("evidence", 0) < 30:
                recommendations.append("Critical: Insufficient evidence - gather more data")
            if scores.get("hardware", 0) < 30:
                recommendations.append("Critical: Hardware incompatible - consider different platform")
            recommendations.append("Review paper requirements against capabilities")
            recommendations.append("May need to pivot to different paper")

        issues = fit_recommendation.get("issues", [])
        for issue in issues:
            recommendations.append(f"Fix: {issue}")

        return recommendations

    def generate_final_report(
        self,
        verdict: str,
        scores: dict[str, float],
        summary: dict[str, Any],
        recommendations: list[str],
        chain: list[dict[str, Any]],
    ) -> str:
        """Generate final report markdown."""
        lines = [
            "# Paper Reproduction Final Report",
            "",
            f"**Generated**: {utc_now()}",
            f"**Verdict**: {verdict}",
            "",
            "## Scores",
            "",
            "| Component | Score |",
            "|-----------|-------|",
            f"| Evidence | {scores.get('evidence', 0):.1f}% |",
            f"| Hardware Fit | {scores.get('hardware', 0):.1f}% |",
            f"| Completeness | {scores.get('completeness', 0):.1f}% |",
            f"| **Overall** | **{scores.get('overall', 0):.1f}%** |",
            "",
            "## Evidence Chain",
            "",
        ]

        for i, entry in enumerate(chain, 1):
            entry_type = entry.get("type", "unknown")
            status = entry.get("status", "unknown")
            lines.append(f"{i}. [{entry_type.upper()}] {status}")

            if entry.get("claim"):
                claim = entry["claim"]
                lines.append(f"   - Claim: {claim.get('type', 'unknown')} = {claim.get('value', 'N/A')}")

            evidence_count = len(entry.get("evidence", []))
            lines.append(f"   - Supporting Evidence: {evidence_count} items")
            lines.append("")

        lines.append("## Recommendations")
        lines.append("")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

        return "\n".join(lines)


AgentRegistry.register(ReviewAuditorAgent)
