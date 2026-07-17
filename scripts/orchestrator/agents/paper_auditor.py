"""
Paper Auditor Agent - NORA-style specialist for paper analysis and verification.

This agent analyzes papers, extracts claims, and verifies reproducibility.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .base import (
    AgentResult,
    AgentRegistry,
    HandoffContext,
    SpecialistAgent,
    utc_now,
)


class PaperAuditorAgent(SpecialistAgent):
    """
    Agent for auditing papers and extracting claims.

    Responsibilities:
    - Analyze paper structure and claims
    - Extract method descriptions
    - Identify reproducibility requirements
    - Prepare handoff for MetricAuditorAgent
    """

    agent_type = "paper-auditor"
    agent_name = "PaperAuditorAgent"
    description = "Analyzes papers, extracts claims, and identifies reproducibility requirements"
    capabilities = [
        "paper_analysis",
        "claim_extraction",
        "method_extraction",
        "requirement_analysis",
    ]
    next_agents = ["metric-auditor"]

    def execute(self, context: HandoffContext) -> AgentResult:
        """Execute paper auditing."""
        paper_path = context.data.get("paper_path", "")
        primary_repo = context.data.get("primary_repo", {})
        repositories = context.data.get("repositories", [])

        if paper_path:
            paper_analysis = self._analyze_paper(paper_path)
        else:
            paper_analysis = self._mock_analysis(primary_repo.get("description", ""))

        claims = self._extract_claims(paper_analysis)
        requirements = self._extract_requirements(claims)
        method_summary = self._summarize_method(paper_analysis)

        self.prepare_handoff(context, {
            "paper_analysis": paper_analysis,
            "claims": claims,
            "requirements": requirements,
            "method_summary": method_summary,
        })

        return AgentResult(
            agent_type=self.agent_type,
            agent_id=self.agent_id,
            status="success",
            output={
                "claims": claims,
                "requirements": requirements,
                "method_summary": method_summary,
                "claim_count": len(claims),
                "requirement_count": len(requirements),
            },
            handoff={
                "claims": claims,
                "requirements": requirements,
                "method_summary": method_summary,
                "next_agent": "metric-auditor",
            },
            metadata={
                "paper_path": paper_path,
                "repository": primary_repo.get("full_name"),
            },
        )

    def _analyze_paper(self, paper_path: str) -> dict[str, Any]:
        """Analyze paper from file path."""
        if not paper_path or not Path(paper_path).exists():
            return self._mock_analysis("")

        try:
            content = Path(paper_path).read_text(encoding="utf-8", errors="ignore")

            sections = self._extract_sections(content)
            tables = self._extract_tables(content)
            figures = self._extract_figures(content)

            return {
                "sections": sections,
                "tables": tables,
                "figures": figures,
                "word_count": len(content.split()),
                "has_code_available": "github" in content.lower() or "code" in content.lower(),
            }
        except Exception as e:
            return {"error": str(e)}

    def _mock_analysis(self, description: str) -> dict[str, Any]:
        """Mock analysis when paper is not available."""
        return {
            "sections": {
                "introduction": "Introduction section",
                "method": "Method section",
                "experiments": "Experiments section",
                "results": "Results section",
            },
            "tables": [],
            "figures": [],
            "word_count": 8000,
            "has_code_available": True,
            "mock": True,
        }

    def _extract_sections(self, content: str) -> dict[str, str]:
        """Extract major sections from paper."""
        sections = {}

        section_patterns = [
            (r"1?\.\s*INTRODUCTION", "introduction"),
            (r"2?\.\s*RELATED\s*WORK", "related_work"),
            (r"3?\.\s*METHOD", "method"),
            (r"4?\.\s*EXPERIMENTS", "experiments"),
            (r"5?\.\s*RESULTS", "results"),
            (r"6?\.\s*CONCLUSION", "conclusion"),
        ]

        for pattern, name in section_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                sections[name] = content[match.start():match.start() + 1000]

        return sections

    def _extract_tables(self, content: str) -> list[dict[str, Any]]:
        """Extract tables from paper."""
        tables = []
        table_pattern = r"TABLE\s*[IVX\d]+\s*:?\s*([^\n]+)\n([\s\S]*?)(?=\n\n|\n[A-Z]|$)"

        for match in re.finditer(table_pattern, content, re.IGNORECASE):
            tables.append({
                "title": match.group(1).strip(),
                "content": match.group(2).strip()[:500],
            })

        return tables

    def _extract_figures(self, content: str) -> list[dict[str, Any]]:
        """Extract figures from paper."""
        figures = []
        fig_pattern = r"FIG\.?\s*[IVX\d]+\s*:?\s*([^\n]+)"

        for match in re.finditer(fig_pattern, content, re.IGNORECASE):
            figures.append({
                "caption": match.group(1).strip(),
            })

        return figures

    def _extract_claims(self, paper_analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract claims from paper analysis."""
        claims = []

        claim_types = [
            ("accuracy", r"accuracy.*?([0-9]+\.?[0-9]*)\s*%", r"%"),
            ("speedup", r"speedup.*?([0-9]+\.?[0-9]*)\s*[x×]", r"x"),
            ("improvement", r"improvement.*?([0-9]+\.?[0-9]*)\s*%", r"%"),
            ("performance", r"performance.*?([0-9]+\.?[0-9]*)", r""),
        ]

        method = paper_analysis.get("sections", {}).get("method", "")
        for claim_type, pattern, unit in claim_types:
            matches = re.findall(pattern, method, re.IGNORECASE)
            for match in matches:
                claims.append({
                    "type": claim_type,
                    "value": float(match),
                    "unit": unit,
                    "source": "method_section",
                })

        if not claims:
            claims.append({
                "type": "baseline",
                "value": 0.0,
                "unit": "",
                "source": "unknown",
                "note": "No quantitative claims found",
            })

        return claims

    def _extract_requirements(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract reproducibility requirements from claims."""
        requirements = []

        for claim in claims:
            if claim["type"] == "accuracy":
                requirements.append({
                    "type": "metric_target",
                    "metric": "accuracy",
                    "target": claim["value"],
                    "threshold": claim["value"] * 0.95,
                    "unit": "%",
                })
            elif claim["type"] == "speedup":
                requirements.append({
                    "type": "metric_target",
                    "metric": "speedup",
                    "target": claim["value"],
                    "threshold": claim["value"] * 0.8,
                    "unit": "x",
                })

        requirements.append({
            "type": "dataset",
            "description": "Dataset as specified in paper experiments",
            "required": True,
        })

        requirements.append({
            "type": "hardware",
            "description": "GPU memory and compute requirements",
            "required": True,
        })

        return requirements

    def _summarize_method(self, paper_analysis: dict[str, Any]) -> dict[str, Any]:
        """Summarize the method from paper."""
        sections = paper_analysis.get("sections", {})

        return {
            "has_method_section": "method" in sections,
            "method_preview": sections.get("method", "")[:500] if sections else "",
            "complexity": "medium" if len(sections) > 3 else "simple",
            "has_equations": "equation" in str(sections).lower() or "$" in str(sections),
        }


AgentRegistry.register(PaperAuditorAgent)
