"""
NORA-style Specialist Agent Base and Registry.

This module implements NORA's Specialist Agent architecture adapted for paper reproduction:
- Base class for all specialist agents
- Agent registry for dynamic discovery
- Agent collaboration via handoff mechanism
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentResult:
    """Result of a specialist agent execution."""
    agent_type: str
    agent_id: str
    status: str  # "success", "partial", "failed"
    output: dict[str, Any]
    handoff: dict[str, Any] | None = None
    timestamp: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HandoffContext:
    """Context passed between agents during handoff."""
    project_root: Path
    current_agent: str
    next_agent: str | None
    data: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now)

    def add_to_history(self, agent: str, action: str, result: dict[str, Any]) -> None:
        """Add an entry to the handoff history."""
        self.history.append({
            "agent": agent,
            "action": action,
            "result": result,
            "timestamp": utc_now(),
        })

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "project_root": str(self.project_root),
            "current_agent": self.current_agent,
            "next_agent": self.next_agent,
            "data": self.data,
            "history": self.history,
            "timestamp": self.timestamp,
        }


class SpecialistAgent(ABC):
    """
    Base class for NORA-style Specialist Agents.

    Each agent:
    1. Has a specific role (e.g., repo-scout, paper-audit, hardware-fit)
    2. Produces output that can be handed off to another agent
    3. Can receive handoff from a previous agent
    4. Has a defined set of capabilities
    """

    agent_type: str = "base"
    agent_name: str = "SpecialistAgent"
    description: str = "Base specialist agent"
    capabilities: list[str] = []
    next_agents: list[str] = []

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.agent_id = f"{self.agent_type}-{utc_now()}"

    @abstractmethod
    def execute(self, context: HandoffContext) -> AgentResult:
        """
        Execute the agent's specialized task.

        Args:
            context: Handoff context from previous agent

        Returns:
            AgentResult with output and optional handoff
        """
        pass

    def can_handoff_to(self, target_agent: str) -> bool:
        """Check if this agent can handoff to target."""
        return target_agent in self.next_agents

    def prepare_handoff(self, context: HandoffContext, data: dict[str, Any],
                       next_agent: str | None = None) -> HandoffContext:
        """Prepare handoff context for next agent."""
        context.add_to_history(self.agent_type, "execute", data)
        context.current_agent = self.agent_type
        context.next_agent = next_agent
        context.data.update(data)
        return context


class AgentRegistry:
    """
    Registry for specialist agents.

    Enables:
    - Dynamic agent discovery
    - Agent lookup by type
    - Agent collaboration
    """

    _agents: dict[str, type[SpecialistAgent]] = {}

    @classmethod
    def register(cls, agent_class: type[SpecialistAgent]) -> None:
        """Register an agent class."""
        if not issubclass(agent_class, SpecialistAgent):
            raise TypeError(f"{agent_class} must be a SpecialistAgent subclass")
        agent = agent_class.__new__(agent_class)
        agent.agent_type = getattr(agent_class, "agent_type", agent_class.__name__.lower())
        cls._agents[agent.agent_type] = agent_class

    @classmethod
    def get(cls, agent_type: str) -> type[SpecialistAgent] | None:
        """Get agent class by type."""
        return cls._agents.get(agent_type)

    @classmethod
    def create(cls, agent_type: str, project_root: str | Path) -> SpecialistAgent | None:
        """Create an agent instance by type."""
        agent_class = cls._agents.get(agent_type)
        if agent_class is None:
            return None
        return agent_class(project_root)

    @classmethod
    def list_agents(cls) -> list[dict[str, Any]]:
        """List all registered agents."""
        return [
            {
                "type": agent_type,
                "name": getattr(cls._agents[agent_type], "agent_name", agent_type),
                "description": getattr(cls._agents[agent_type], "description", ""),
                "capabilities": getattr(cls._agents[agent_type], "capabilities", []),
                "next_agents": getattr(cls._agents[agent_type], "next_agents", []),
            }
            for agent_type in cls._agents
        ]

    @classmethod
    def get_handoff_chain(cls, start_agent: str) -> list[str]:
        """Get the handoff chain starting from an agent."""
        chain = [start_agent]
        current = start_agent
        visited = {start_agent}

        while True:
            agent_class = cls._agents.get(current)
            if agent_class is None:
                break
            next_agents = getattr(agent_class, "next_agents", [])
            if not next_agents:
                break
            next_agent = next_agents[0]
            if next_agent in visited:
                break
            chain.append(next_agent)
            visited.add(next_agent)
            current = next_agent

        return chain


class AgentOrchestrator:
    """
    Orchestrates specialist agents in a pipeline.

    Coordinates:
    - Agent execution order
    - Handoff between agents
    - Result collection
    - Error handling
    """

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.results: list[AgentResult] = []
        self.context: HandoffContext | None = None

    def run(self, start_agent: str,
            initial_data: dict[str, Any] | None = None,
            chain: list[str] | None = None) -> AgentResult:
        """
        Run agent pipeline starting from start_agent.

        Args:
            start_agent: Type of starting agent
            initial_data: Initial data for the pipeline
            chain: Optional explicit chain override

        Returns:
            Final AgentResult from the last agent
        """
        if chain is None:
            chain = AgentRegistry.get_handoff_chain(start_agent)

        initial_data = initial_data or {}
        self.context = HandoffContext(
            project_root=self.project_root,
            current_agent=start_agent,
            next_agent=chain[1] if len(chain) > 1 else None,
            data=initial_data.copy(),
        )

        self.results = []

        for agent_type in chain:
            if self.context is None:
                break

            agent = AgentRegistry.create(agent_type, self.project_root)
            if agent is None:
                result = AgentResult(
                    agent_type=agent_type,
                    agent_id="unknown",
                    status="failed",
                    output={"error": f"Agent {agent_type} not found"},
                )
                self.results.append(result)
                break

            try:
                result = agent.execute(self.context)
                self.results.append(result)

                if result.handoff:
                    self.context.data.update(result.handoff)
                    self.context.next_agent = result.handoff.get("next_agent")

                if result.status == "failed" and not result.handoff:
                    break

            except Exception as exc:
                result = AgentResult(
                    agent_type=agent_type,
                    agent_id=agent.agent_id,
                    status="failed",
                    output={"error": str(exc)},
                )
                self.results.append(result)
                break

        return self.results[-1] if self.results else AgentResult(
            agent_type="orchestrator",
            agent_id="orchestrator",
            status="failed",
            output={"error": "No agents executed"},
        )

    def get_results(self) -> list[AgentResult]:
        """Get all agent results."""
        return self.results.copy()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the orchestration."""
        return {
            "total_agents": len(self.results),
            "successful": sum(1 for r in self.results if r.status == "success"),
            "partial": sum(1 for r in self.results if r.status == "partial"),
            "failed": sum(1 for r in self.results if r.status == "failed"),
            "chain": [r.agent_type for r in self.results],
            "final_status": self.results[-1].status if self.results else "none",
        }
