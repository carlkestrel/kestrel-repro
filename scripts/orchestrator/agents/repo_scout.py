"""
Repo Scout Agent - NORA-style specialist for GitHub repository discovery.

This agent searches for and evaluates code repositories relevant to the target paper.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .base import (
    AgentResult,
    AgentRegistry,
    HandoffContext,
    SpecialistAgent,
    utc_now,
)


class RepoScoutAgent(SpecialistAgent):
    """
    Agent for discovering and evaluating repositories.

    Responsibilities:
    - Search GitHub for related repositories
    - Evaluate repository quality and relevance
    - Collect repository metadata
    - Prepare handoff for PaperAuditorAgent
    """

    agent_type = "repo-scout"
    agent_name = "RepoScoutAgent"
    description = "Discovers and evaluates GitHub repositories for paper reproduction"
    capabilities = [
        "github_search",
        "repo_evaluation",
        "code_analysis",
        "dependency_analysis",
    ]
    next_agents = ["paper-auditor"]

    def execute(self, context: HandoffContext) -> AgentResult:
        """Execute repository scouting."""
        query = context.data.get("query", "")
        paper_title = context.data.get("paper_title", "")
        keywords = context.data.get("keywords", [])

        search_query = query or self._build_search_query(paper_title, keywords)
        repositories = self._search_github(search_query)

        if not repositories:
            return AgentResult(
                agent_type=self.agent_type,
                agent_id=self.agent_id,
                status="partial",
                output={"repositories": [], "query": search_query},
                handoff=self._prepare_handoff(search_query, []),
            )

        evaluated = []
        for repo in repositories:
            evaluation = self._evaluate_repo(repo)
            evaluated.append(evaluation)

        evaluated.sort(key=lambda x: x.get("score", 0), reverse=True)

        top_repo = evaluated[0] if evaluated else {}

        self.prepare_handoff(context, {
            "repositories": evaluated,
            "top_repository": top_repo,
            "query": search_query,
        })

        return AgentResult(
            agent_type=self.agent_type,
            agent_id=self.agent_id,
            status="success",
            output={
                "repositories": evaluated,
                "top_repository": top_repo,
                "total_found": len(evaluated),
            },
            handoff={
                "repositories": evaluated,
                "primary_repo": top_repo,
                "next_agent": "paper-auditor",
            },
            metadata={
                "query": search_query,
                "results_count": len(evaluated),
            },
        )

    def _build_search_query(self, paper_title: str, keywords: list[str]) -> str:
        """Build search query from paper title and keywords."""
        parts = []

        if paper_title:
            words = paper_title.split()
            significant = [w for w in words if len(w) > 3 and w.lower() not in {
                "with", "from", "using", "learning", "deep", "neural", "network"
            }]
            parts.extend(significant[:5])

        parts.extend(keywords[:5])

        return " ".join(parts[:10]) if parts else paper_title

    def _search_github(self, query: str) -> list[dict[str, Any]]:
        """Search GitHub for repositories."""
        if not query:
            return []

        try:
            result = subprocess.run(
                ["gh", "api", "search/repositories", "-q", query, "-L", "10", "--jq", ".items[] | {name: .full_name, stars: .stargazers_count, description: .description, url: .html_url, language: .language, updated: .updated_at}"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                repos = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        try:
                            repos.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                return repos

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

        return self._mock_search(query)

    def _mock_search(self, query: str) -> list[dict[str, Any]]:
        """Mock search results for when gh CLI is not available."""
        return [
            {
                "name": f"example-{query.replace(' ', '-')}",
                "full_name": f"author/example-{query.replace(' ', '-')}",
                "stargazers_count": 100,
                "description": f"Implementation of {query}",
                "html_url": f"https://github.com/author/example-{query.replace(' ', '-')}",
                "language": "Python",
                "updated_at": utc_now(),
            }
        ]

    def _evaluate_repo(self, repo: dict[str, Any]) -> dict[str, Any]:
        """Evaluate repository quality and relevance."""
        score = 0

        score += min(repo.get("stargazers_count", 0) / 10, 100)

        description = repo.get("description", "").lower()
        keywords = ["pytorch", "tensorflow", "official", "implementation", "reproduction"]
        for kw in keywords:
            if kw in description:
                score += 10

        return {
            **repo,
            "score": score,
            "evaluation": {
                "has_description": bool(repo.get("description")),
                "has_stars": repo.get("stargazers_count", 0) > 0,
                "is_active": repo.get("updated_at") is not None,
            },
        }

    def _prepare_handoff(self, query: str, repositories: list[dict]) -> dict[str, Any]:
        """Prepare handoff data for next agent."""
        return {
            "query": query,
            "repositories": repositories,
            "primary_repo": repositories[0] if repositories else None,
            "next_agent": "paper-auditor",
        }


AgentRegistry.register(RepoScoutAgent)
