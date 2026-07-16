from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

AUTO_EXECUTE = "AUTO_EXECUTE"
REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
REJECT = "REJECT"
DECISIONS = {AUTO_EXECUTE, REQUIRE_APPROVAL, REJECT}

DEFAULT_POLICY = {
    "default": "REQUIRE_APPROVAL",
    "gates": {
        "read_only": "AUTO_EXECUTE",
        "safe": "AUTO_EXECUTE",
        "modify_project_files": "REQUIRE_APPROVAL",
        "gpu_training": "REQUIRE_APPROVAL",
        "destructive": "REJECT",
    },
}
_SAFE_TOP_LEVEL = {".repro", ".execution", "output", "reports"}
_FORBIDDEN = {"src", "configs", "scripts", "README.md"}
_PAPER_ASSET = re.compile(r"(^|[/\\])(paper|papers|assets?)([/\\]|$)|\.pdf(?:\s|$)", re.I)


class PolicyEngine:
    """Reload-on-every-decision policy evaluator with safe-auto boundaries."""

    def __init__(self, project_root: str | Path,
                 policy_path: str | Path | None = None,
                 automation: str = "safe-auto"):
        self.project_root = Path(project_root).resolve()
        self.policy_path = (Path(policy_path).resolve() if policy_path else
                            self.project_root / "automation_policy.yaml")
        self.automation = automation

    def load(self) -> dict:
        if not self.policy_path.exists():
            return DEFAULT_POLICY
        if yaml is None:
            raise RuntimeError("PyYAML is required to read automation policy")
        loaded = yaml.safe_load(self.policy_path.read_text(encoding="utf-8")) or {}
        merged = {"default": loaded.get("default", DEFAULT_POLICY["default"]),
                  "gates": {**DEFAULT_POLICY["gates"], **loaded.get("gates", {})}}
        return merged

    def evaluate(self, task: dict) -> tuple[str, str]:
        policy = self.load()
        gate = str(task.get("gate", ""))
        decision = str(policy["gates"].get(gate, policy["default"])).upper()
        if decision not in DECISIONS:
            return REJECT, f"invalid policy decision {decision!r} for gate {gate}"
        if self.automation != "safe-auto":
            return decision, f"policy gate {gate}"
        boundary = self._safe_auto_boundary(task)
        if boundary is not None:
            return boundary
        return decision, f"policy gate {gate}"

    def _safe_auto_boundary(self, task: dict) -> tuple[str, str] | None:
        gate = str(task.get("gate", ""))
        command = str(task.get("command", ""))
        if gate != "modify_project_files":
            return None
        writes = task.get("writes")
        if not writes:
            return REQUIRE_APPROVAL, "modify_project_files requires declared writes"
        for raw in writes:
            path = Path(str(raw))
            if path.is_absolute():
                try:
                    rel = path.resolve().relative_to(self.project_root)
                except ValueError:
                    return REJECT, f"write escapes project root: {raw}"
            else:
                rel = path
            parts = rel.parts
            if not parts or parts[0] not in _SAFE_TOP_LEVEL:
                return REJECT, f"safe-auto write outside allowed roots: {raw}"
            if any(part in _FORBIDDEN for part in parts) or _PAPER_ASSET.search(str(rel)):
                return REJECT, f"safe-auto forbidden asset: {raw}"
        command_tokens = set(re.findall(r"(?:^|\s)([\w.-]+)(?:/|\s|$)", command))
        if command_tokens & _FORBIDDEN or _PAPER_ASSET.search(command):
            return REJECT, "command references protected project content"
        return None
