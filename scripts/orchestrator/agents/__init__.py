"""
NORA-style Specialist Agents for Paper Reproduction.

This package contains the specialist agents that implement the NORA architecture:
- RepoScoutAgent: Discovers and evaluates GitHub repositories
- PaperAuditorAgent: Analyzes papers and extracts claims
- MetricAuditorAgent: Audits metrics and data contracts
- HardwareFitAgent: Evaluates hardware compatibility
- EvidenceVerifierAgent: Verifies evidence chains
- ReviewAuditorAgent: Generates final verdict

Usage:
    from scripts.orchestrator.agents.base import AgentOrchestrator, AgentRegistry

    orchestrator = AgentOrchestrator(project_root)
    result = orchestrator.run("repo-scout", {"query": "transformer"})
"""

from .base import (
    AgentOrchestrator,
    AgentRegistry,
    AgentResult,
    HandoffContext,
    SpecialistAgent,
)

# Import all agents to register them
from . import repo_scout  # noqa: F401, E402
from . import paper_auditor  # noqa: F401, E402
from . import metric_auditor  # noqa: F401, E402
from . import hardware_fit  # noqa: F401, E402
from . import evidence_verifier  # noqa: F401, E402
from . import review_auditor  # noqa: F401, E402

__all__ = [
    "AgentOrchestrator",
    "AgentRegistry",
    "AgentResult",
    "HandoffContext",
    "SpecialistAgent",
]
