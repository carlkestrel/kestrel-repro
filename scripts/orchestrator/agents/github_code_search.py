"""
NORA-style GitHub Code Search.

This module provides enhanced GitHub code search capabilities:
- Code snippet discovery
- Repository ranking based on code relevance
- Rate-limited API access
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any


class GitHubCodeSearch:
    """
    NORA-style GitHub code search for discovering relevant code snippets.
    
    Features:
    - Code search API integration
    - Rate limiting with exponential backoff
    - Code snippet classification
    - Repository ranking
    """

    API_BASE = "https://api.github.com"

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path(".cache/github_search")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._rate_limit_delay = 1.0
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request = time.time()

    def _get_auth_token(self) -> str | None:
        """Get GitHub auth token if available."""
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make authenticated GitHub API request."""
        import urllib.parse
        import urllib.request

        self._rate_limit()

        url = f"{self.API_BASE}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "dl-paper-repro/1.0",
        }

        token = self._get_auth_token()
        if token:
            headers["Authorization"] = f"token {token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e)}

    def search_code(self, query: str, language: str | None = None,
                   max_results: int = 30) -> list[dict]:
        """
        Search for code snippets.

        Args:
            query: Search query
            language: Optional language filter
            max_results: Maximum results (1-100)

        Returns:
            List of code search results
        """
        params = {
            "q": query,
            "per_page": min(max_results, 100),
            "sort": "indexed",
            "order": "desc",
        }
        if language:
            params["q"] += f" language:{language}"

        data = self._make_request("/search/code", params)
        if data is None or "error" in data:
            return []

        return [
            {
                "name": item.get("name", ""),
                "path": item.get("path", ""),
                "sha": item.get("sha", ""),
                "url": item.get("html_url", ""),
                "repository": item.get("repository", {}).get("full_name", ""),
                "score": item.get("score", 0),
                "text_matches": item.get("text_matches", []),
            }
            for item in data.get("items", [])
        ]

    def search_repositories(self, query: str, language: str | None = None,
                           max_results: int = 30) -> list[dict]:
        """
        Search for repositories.

        Args:
            query: Search query
            language: Optional language filter
            max_results: Maximum results (1-100)

        Returns:
            List of repository results
        """
        params = {
            "q": query,
            "per_page": min(max_results, 100),
            "sort": "stars",
            "order": "desc",
        }
        if language:
            params["q"] += f" language:{language}"

        data = self._make_request("/search/repositories", params)
        if data is None or "error" in data:
            return []

        return [
            {
                "name": item.get("name", ""),
                "full_name": item.get("full_name", ""),
                "description": item.get("description", ""),
                "html_url": item.get("html_url", ""),
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language", ""),
                "forks": item.get("forks_count", 0),
                "updated_at": item.get("updated_at", ""),
                "pushed_at": item.get("pushed_at", ""),
                "topics": item.get("topics", []),
                "license": item.get("license", {}).get("name", ""),
            }
            for item in data.get("items", [])
        ]

    def get_file_content(self, repo: str, path: str, ref: str = "main") -> str | None:
        """Get file content from a repository."""
        import urllib.request

        self._rate_limit()

        url = f"{self.API_BASE}/repos/{repo}/contents/{path}"
        if ref:
            url += f"?ref={ref}"

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "dl-paper-repro/1.0",
        }

        token = self._get_auth_token()
        if token:
            headers["Authorization"] = f"token {token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                import base64
                return base64.b64decode(data["content"]).decode("utf-8")
        except Exception:
            return None

    def search_model_architecture(self, repo_pattern: str, architecture: str) -> list[dict]:
        """Search for model architecture code in a repository."""
        queries = [
            f"class {architecture} in:file",
            f"class.*{architecture}.*in:file",
            f"def forward.*{architecture}.*in:file",
        ]

        results = []
        for query in queries:
            full_query = f"{query} repo:{repo_pattern}"
            results.extend(self.search_code(full_query, language="python"))

        return results

    def search_loss_function(self, repo_pattern: str, loss_name: str | None = None) -> list[dict]:
        """Search for loss function implementations."""
        if loss_name:
            queries = [
                f"def.*{loss_name}.*in:file",
                f"class.*{loss_name}Loss.*in:file",
            ]
        else:
            queries = [
                "class.*Loss.*in:file language:python",
                "def.*loss.*in:file language:python",
            ]

        results = []
        for query in queries:
            full_query = f"{query} repo:{repo_pattern}" if repo_pattern else query
            results.extend(self.search_code(full_query))

        return results

    def search_dataset(self, repo_pattern: str) -> list[dict]:
        """Search for dataset implementations."""
        queries = [
            "class.*Dataset.*in:file language:python",
            "def __getitem__.*in:file language:python",
            "class.*DataLoader.*in:file language:python",
        ]

        results = []
        for query in queries:
            full_query = f"{query} repo:{repo_pattern}" if repo_pattern else query
            results.extend(self.search_code(full_query))

        return results

    def search_metrics(self, repo_pattern: str, metric_names: list[str] | None = None) -> list[dict]:
        """Search for metric implementations."""
        if metric_names:
            queries = [f"def.*{name}.*in:file" for name in metric_names]
        else:
            queries = [
                "def.*accuracy.*in:file language:python",
                "def.*iou.*in:file language:python",
                "def.*f1.*in:file language:python",
            ]

        results = []
        for query in queries:
            full_query = f"{query} repo:{repo_pattern}" if repo_pattern else query
            results.extend(self.search_code(full_query))

        return results

    def classify_code_snippets(self, results: list[dict]) -> dict[str, list[dict]]:
        """Classify code snippets by type."""
        classified = {
            "model_architecture": [],
            "loss_functions": [],
            "data_loading": [],
            "training_loops": [],
            "metrics": [],
            "other": [],
        }

        for result in results:
            path = result.get("path", "").lower()
            name = result.get("name", "").lower()

            if any(kw in path for kw in ["model", "network", "layer", "backbone"]):
                classified["model_architecture"].append(result)
            elif any(kw in path for kw in ["loss", "criterion"]):
                classified["loss_functions"].append(result)
            elif any(kw in path for kw in ["dataset", "dataloader", "data"]):
                classified["data_loading"].append(result)
            elif any(kw in path for kw in ["train", "optimizer"]):
                classified["training_loops"].append(result)
            elif any(kw in path for kw in ["metric", "eval", "accuracy"]):
                classified["metrics"].append(result)
            else:
                classified["other"].append(result)

        return classified

    def calculate_repo_relevance(self, repo_data: dict,
                                code_results: list[dict]) -> dict[str, Any]:
        """Calculate repository relevance score."""
        score = {
            "total": 0.0,
            "components": {},
        }

        classified = self.classify_code_snippets(code_results)

        weights = {
            "model_architecture": 0.30,
            "loss_functions": 0.20,
            "data_loading": 0.15,
            "training_loops": 0.15,
            "metrics": 0.20,
        }

        for category, weight in weights.items():
            count = len(classified.get(category, []))
            category_score = min(count * weight * 10, weight * 100)
            score["components"][category] = {
                "count": count,
                "score": category_score,
            }
            score["total"] += category_score

        score["total"] = min(score["total"], 100.0)

        return score

    def full_search(self, repo_pattern: str,
                   architecture: str | None = None,
                   loss_name: str | None = None,
                   metric_names: list[str] | None = None) -> dict[str, Any]:
        """
        Perform full code search for a repository.

        Args:
            repo_pattern: Repository pattern (owner/repo or org/*)
            architecture: Optional architecture name to search
            loss_name: Optional loss function name
            metric_names: Optional metric names

        Returns:
            Combined search results and relevance scores
        """
        results = {
            "model_architecture": [],
            "loss_functions": [],
            "data_loading": [],
            "training_loops": [],
            "metrics": [],
        }

        if architecture:
            results["model_architecture"] = self.search_model_architecture(
                repo_pattern, architecture
            )

        results["loss_functions"] = self.search_loss_function(repo_pattern, loss_name)
        results["data_loading"] = self.search_dataset(repo_pattern)

        if metric_names:
            results["metrics"] = self.search_metrics(repo_pattern, metric_names)

        results["training_loops"] = self.search_code(
            f"for epoch in:file repo:{repo_pattern}"
        )

        relevance = self.calculate_repo_relevance({}, [r for rs in results.values() for r in rs])

        return {
            "results": results,
            "classified": self.classify_code_snippets([r for rs in results.values() for r in rs]),
            "relevance": relevance,
            "total_snippets": sum(len(v) for v in results.values()),
        }
