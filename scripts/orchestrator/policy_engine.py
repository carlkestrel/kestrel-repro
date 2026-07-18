from __future__ import annotations

import os
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
    "nora": {
        "auto_proceed": False,
        "human_checkpoints": [],
        "review_loop": {
            "max_iterations": 3,
            "auto_stop_on_fail": True,
            "consecutive_fail_threshold": 2,
        },
    },
}
_SAFE_TOP_LEVEL = {".repro", ".execution", "output", "reports"}
_FORBIDDEN = {"src", "configs", "scripts", "README.md"}
_PAPER_ASSET = re.compile(r"(^|[/\\])(paper|papers|assets?)([/\\]|$)|\.pdf(?:\s|$)", re.I)

# AUTO_PROCEED environment variable
AUTO_PROCEED_ENV = "AUTO_PROCEED"


class PolicyEngine:
    """Reload-on-every-decision policy evaluator with NORA AUTO_PROCEED support."""

    def __init__(
        self,
        project_root: str | Path,
        policy_path: str | Path | None = None,
        automation: str = "safe-auto",
    ):
        self.project_root = Path(project_root).resolve()
        self.policy_path = (
            Path(policy_path).resolve()
            if policy_path
            else self.project_root / "automation_policy.yaml"
        )
        self.automation = automation
        self._nora_config: dict[str, Any] = {}

    def load(self) -> dict:
        if not self.policy_path.exists():
            return DEFAULT_POLICY
        if yaml is None:
            raise RuntimeError("PyYAML is required to read automation policy")
        loaded = yaml.safe_load(self.policy_path.read_text(encoding="utf-8")) or {}

        # Load NORA config
        self._nora_config = loaded.get("nora", DEFAULT_POLICY["nora"])

        merged = {
            "default": loaded.get("default", DEFAULT_POLICY["default"]),
            "gates": {**DEFAULT_POLICY["gates"], **loaded.get("gates", {})},
            "nora": {**DEFAULT_POLICY["nora"], **self._nora_config},
        }
        return merged

    def is_auto_proceed_enabled(self) -> bool:
        """Check if AUTO_PROCEED is enabled via env var or config."""
        env_value = os.environ.get(AUTO_PROCEED_ENV, "").lower()
        if env_value in ("true", "1", "yes"):
            return True
        if env_value in ("false", "0", "no"):
            return False

        # Check config
        policy = self.load()
        return policy.get("nora", {}).get("auto_proceed", False)

    def get_human_checkpoints(self) -> list[str]:
        """Get list of human checkpoint gates."""
        policy = self.load()
        return policy.get("nora", {}).get("human_checkpoints", [])

    def should_pause_at_checkpoint(self, gate: str) -> bool:
        """Check if we should pause at a checkpoint for human review."""
        checkpoints = self.get_human_checkpoints()
        if not checkpoints:
            return False

        # Check if this gate is in the checkpoint list
        if gate in checkpoints:
            # Don't pause if AUTO_PROCEED is enabled
            return not self.is_auto_proceed_enabled()

        return False

    def evaluate(self, task: dict) -> tuple[str, str]:
        policy = self.load()
        gate = str(task.get("gate", ""))
        decision = str(policy["gates"].get(gate, policy["default"])).upper()

        if decision not in DECISIONS:
            return REJECT, f"invalid policy decision {decision!r} for gate {gate}"

        if self.automation != "safe-auto":
            return decision, f"policy gate {gate}"

        # Check for AUTO_PROCEED
        if self.is_auto_proceed_enabled() and decision == REQUIRE_APPROVAL:
            # Auto-approve R0/R1 gates if AUTO_PROCEED is enabled
            risk_level = self._get_risk_level(gate)
            if risk_level in ("R0", "R1", "R2"):
                return AUTO_EXECUTE, f"{gate} auto-proceeded (AUTO_PROCEED=true)"

        boundary = self._safe_auto_boundary(task)
        if boundary is not None:
            return boundary
        return decision, f"policy gate {gate}"

    def _get_risk_level(self, gate: str) -> str:
        """Map gate to risk level."""
        risk_map = {
            "read_only": "R0",
            "safe": "R0",
            "compute_metrics": "R1",
            "generate_report": "R1",
            "mini_benchmark": "R2",
            "small_download": "R2",
            "gpu_training": "R3",
            "full_training": "R3",
            "modify_project_files": "R4",
            "destructive": "R4",
            "protocol_change": "R4",
            "external_publish": "R4",
            "credential_access": "R4",
        }
        return risk_map.get(gate, "R3")

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
