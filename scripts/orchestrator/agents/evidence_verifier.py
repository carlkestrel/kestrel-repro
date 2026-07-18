"""
Evidence Verifier Agent - NORA-style specialist for evidence chain verification.

This agent verifies evidence chains and ensures reproducibility documentation.
"""

from __future__ import annotations

import json
from typing import Any

from .base import (
    AgentRegistry,
    AgentResult,
    HandoffContext,
    SpecialistAgent,
    utc_now,
)


class EvidenceVerifierAgent(SpecialistAgent):
    """
    Agent for evidence verification and chain building.

    Responsibilities:
    - Verify evidence completeness
    - Build evidence chains
    - Check reproducibility documentation
    - Prepare handoff for ReviewAuditorAgent
    """

    agent_type = "evidence-verifier"
    agent_name = "EvidenceVerifierAgent"
    description = "Verifies evidence chains and ensures reproducibility documentation"
    capabilities = [
        "evidence_verification",
        "chain_building",
        "documentation_check",
        "claim_validation",
    ]
    next_agents = ["review-auditor"]

    def execute(self, context: HandoffContext) -> AgentResult:
        """Execute evidence verification."""
        metric_targets = context.data.get("metric_targets", [])
        data_contracts = context.data.get("data_contracts", [])
        hardware_info = context.data.get("hardware_info", {})
        fit_recommendation = context.data.get("fit_recommendation", {})
        config = context.data.get("config", {})

        evidence = self._collect_evidence()
        chain = self._build_evidence_chain(evidence, context.data)
        completeness = self._check_completeness(chain, metric_targets, data_contracts)

        verification_result = {
            "evidence": evidence,
            "chain": chain,
            "completeness": completeness,
            "verified": completeness.get("score", 0) >= 80,
        }

        self.prepare_handoff(
            context,
            {
                "evidence": evidence,
                "chain": chain,
                "completeness": completeness,
                "verification_result": verification_result,
            },
        )

        return AgentResult(
            agent_type=self.agent_type,
            agent_id=self.agent_id,
            status="success",
            output=verification_result,
            handoff={
                "evidence": evidence,
                "chain": chain,
                "verification_result": verification_result,
                "next_agent": "review-auditor",
            },
            metadata={
                "chain_length": len(chain),
                "evidence_count": len(evidence),
                "completeness_score": completeness.get("score", 0),
            },
        )

    def _collect_evidence(self) -> list[dict[str, Any]]:
        """Collect available evidence from the project."""
        evidence = []

        evidence_dir = self.project_root / "artifacts" / "runs"
        if evidence_dir.exists():
            for run_dir in evidence_dir.iterdir():
                if run_dir.is_dir():
                    evidence.append(
                        {
                            "type": "run",
                            "path": str(run_dir),
                            "run_id": run_dir.name,
                        }
                    )

        evidence_dir = self.project_root / ".repro" / "audit"
        if evidence_dir.exists():
            for report_file in evidence_dir.glob("*.md"):
                evidence.append(
                    {
                        "type": "report",
                        "path": str(report_file),
                        "name": report_file.stem,
                    }
                )

        return evidence

    def _build_evidence_chain(
        self, evidence: list[dict[str, Any]], context_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Build evidence chain linking claims to evidence."""
        chain = []

        claims = context_data.get("claims", [])
        repositories = context_data.get("repositories", [])
        primary_repo = context_data.get("primary_repo", {})

        if primary_repo:
            chain.append(
                {
                    "type": "source",
                    "title": "Primary Repository",
                    "evidence": primary_repo,
                    "links": [],
                }
            )

        for claim in claims:
            chain_entry = {
                "type": "claim",
                "claim": claim,
                "evidence": [],
                "status": "unverified",
            }

            for item in evidence:
                if self._evidence_supports_claim(item, claim):
                    chain_entry["evidence"].append(item)
                    chain_entry["status"] = "verified"

            chain.append(chain_entry)

        for item in evidence:
            if not any(item["path"] in e.get("path", "") for e in chain if e.get("evidence")):
                chain.append(
                    {
                        "type": "artifact",
                        "artifact": item,
                        "links": [],
                        "status": "unlinked",
                    }
                )

        return chain

    def _evidence_supports_claim(self, evidence: dict[str, Any], claim: dict[str, Any]) -> bool:
        """Check if evidence supports a claim."""
        evidence_str = json.dumps(evidence, default=str).lower()
        claim_type = claim.get("type", "").lower()

        claim_keywords = {
            "accuracy": ["accuracy", "correct", "error"],
            "speedup": ["speed", "fast", "time"],
            "improvement": ["improve", "better", "gain"],
        }

        keywords = claim_keywords.get(claim_type, [claim_type])
        return any(kw in evidence_str for kw in keywords)

    def _check_completeness(
        self,
        chain: list[dict[str, Any]],
        metric_targets: list[dict[str, Any]],
        data_contracts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Check completeness of evidence chain."""
        completeness = {
            "score": 0,
            "required": [],
            "missing": [],
            "issues": [],
        }

        for target in metric_targets:
            metric = target.get("metric", "unknown")
            found = any(
                entry.get("type") == "claim" and entry.get("claim", {}).get("type") == metric
                for entry in chain
            )
            if found:
                completeness["score"] += 20
            else:
                completeness["missing"].append(f"Evidence for metric: {metric}")
                completeness["required"].append(metric)

        for contract in data_contracts:
            contract_type = contract.get("contract_type", "unknown")
            checks = contract.get("validation_checks", [])
            for check in checks:
                completeness["required"].append(f"{contract_type}: {check}")

        artifact_count = sum(1 for e in chain if e.get("type") in {"run", "artifact"})
        completeness["score"] = min(100, completeness["score"] + artifact_count * 10)

        if completeness["score"] >= 80:
            completeness["status"] = "complete"
        elif completeness["score"] >= 50:
            completeness["status"] = "partial"
        else:
            completeness["status"] = "incomplete"
            completeness["issues"].append("Evidence chain is incomplete")

        return completeness

    def generate_report(self, chain: list[dict[str, Any]], completeness: dict[str, Any]) -> str:
        """Generate evidence verification report."""
        lines = [
            "# Evidence Verification Report",
            "",
            f"**Generated**: {utc_now()}",
            f"**Completeness Score**: {completeness.get('score', 0)}%",
            f"**Status**: {completeness.get('status', 'unknown')}",
            "",
            "## Evidence Chain",
            "",
        ]

        for i, entry in enumerate(chain, 1):
            entry_type = entry.get("type", "unknown")
            lines.append(f"### {i}. {entry_type.upper()}")
            lines.append(f"- Status: {entry.get('status', 'unknown')}")

            if entry.get("claim"):
                lines.append(f"- Claim: {entry['claim']}")

            evidence = entry.get("evidence", [])
            lines.append(f"- Supporting Evidence: {len(evidence)} items")

            if entry.get("artifact"):
                lines.append(f"- Artifact: {entry['artifact'].get('path', 'N/A')}")

            lines.append("")

        if completeness.get("missing"):
            lines.append("## Missing Evidence")
            for item in completeness["missing"]:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines)


AgentRegistry.register(EvidenceVerifierAgent)
