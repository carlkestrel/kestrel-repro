"""R2 Authorization Contract: data model, validator, and enforcement.

Schema: ``.repro/authorization_contract.yaml``

This module provides:
  * ``AuthorizationContract`` — structured representation of a contract.
  * ``load_contract()`` — parse + validate a contract YAML file.
  * ``validate_contract()`` — structural and semantic validation.
  * ``check_action()`` — is a given action permitted by this contract?
  * ``check_write_path()`` — is a write to this path within allowed roots?
  * ``is_active()`` — is the contract currently active (not expired/revoked)?
  * ``AuthorizationError`` — raised on policy violations.

Denial-by-default: any action not explicitly listed in ``granted_actions``
is denied. ``denied_actions`` is the explicit deny list (for auditing).

R2 acceptance:
  #11 — actions outside explicit grant are denied.
  #12 — actions within grant pass.
  #13 — out-of-scope write paths are denied.
  #14 — symlink traversal attempts are denied.
  #15 — expired/revoked contracts block.
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


# ─── Error type ─────────────────────────────────────────────────────────

class AuthorizationError(Exception):
    """Raised when an action violates the authorization contract."""
    def __init__(self, action: str, reason: str,
                 contract_id: str = "", contract_path: str = ""):
        self.action = action
        self.reason = reason
        self.contract_id = contract_id
        self.contract_path = contract_path
        super().__init__(
            f"[authorization] {action}: {reason}"
            + (f" (contract={contract_id})" if contract_id else "")
        )


# ─── Data model ────────────────────────────────────────────────────────

@dataclass
class AuthorizationContract:
    contract_id: str
    project_root: str
    project_id: str = ""
    # authorization_bound_hash (R3-0): stronger than canonical_plan_hash alone.
    # Includes schema_version and canonicalization_version, so schema upgrades
    # automatically invalidate old contracts and force NEEDS_RECONFIRMATION.
    authorization_bound_hash: str = ""
    canonical_plan_hash: str = ""
    git_commit: str = ""
    created_at: str = ""
    expires_at: str = ""
    granted_actions: list[str] = field(default_factory=list)
    denied_actions: list[str] = field(default_factory=list)
    allowed_write_roots: list[str] = field(default_factory=list)
    network_policy: str = "deny"          # "allow" | "deny" | "read-only"
    clone_policy: str = "deny"            # "allow" | "deny"
    download_policy: str = "deny"         # "allow" | "deny"
    dependency_install_policy: str = "deny"  # "allow" | "deny"
    source_modification_policy: str = "deny"  # "allow" | "deny"
    gpu_execution_policy: str = "deny"   # "allow" | "deny"
    training_stages: list[str] = field(default_factory=list)
    time_budget_minutes: int = 0
    disk_budget_gb: int = 0
    vram_budget_gb: int = 0
    temperature_limit_c: int = 0
    retry_limit: int = 3
    safe_repair_whitelist: list[str] = field(default_factory=list)
    local_commit_permission: bool = False
    push_pr_permission: bool = False
    release_permission: bool = False
    revocation_state: str = "active"      # "active" | "revoked" | "expired"
    _loaded_from: Path | None = None

    def is_active(self) -> bool:
        """Return True if the contract is currently active.

        Returns False if:
        1. revocation_state != "active" (revoked or expired)
        2. expires_at is set and the current time is past it
        """
        if self.revocation_state != "active":
            return False
        if self.expires_at:
            try:
                exp = datetime.fromisoformat(self.expires_at)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp:
                    return False
            except (ValueError, TypeError):
                pass
        return True

    def check_action(self, action: str) -> None:
        """Raise AuthorizationError if action is not permitted."""
        if not self.is_active():
            raise AuthorizationError(
                action, f"contract {self.contract_id} is {self.revocation_state}",
                contract_id=self.contract_id,
            )

        # Deny list always wins
        if action in self.denied_actions:
            raise AuthorizationError(
                action, "explicitly denied by contract",
                contract_id=self.contract_id,
            )

        # Granted actions
        if action in self.granted_actions:
            return

        # Wildcard grant
        if "*" in self.granted_actions:
            return

        raise AuthorizationError(
            action, "not in granted_actions (deny-by-default)",
            contract_id=self.contract_id,
        )

    def check_write_path(self, path: str, project_root: str) -> None:
        """Raise AuthorizationError if path is not within allowed_write_roots.

        Performs:
          * Real-path resolution (resolves symlinks).
          * `..` traversal normalisation.
          * Absolute-path bypass prevention.
          * Symlink-exit detection.
        """
        if not self.is_active():
            raise AuthorizationError(
                "<write>", f"contract {self.contract_id} is {self.revocation_state}",
                contract_id=self.contract_id,
            )

        if not self.allowed_write_roots:
            raise AuthorizationError(
                "<write>", "no allowed_write_roots defined (deny-by-default)",
                contract_id=self.contract_id,
            )

        try:
            abs_path = Path(path).resolve()
        except Exception as e:
            raise AuthorizationError(
                "<write>", f"cannot resolve path {path!r}: {e}",
                contract_id=self.contract_id,
            ) from e

        # Detect absolute-path bypass (path already absolute but outside project)
        if Path(path).is_absolute():
            # Check if it's within any allowed root
            allowed = [Path(project_root) / r for r in self.allowed_write_roots]
            if not any(_is_within(abs_path, r) for r in allowed):
                raise AuthorizationError(
                    "<write>", f"absolute path {path!r} outside allowed_write_roots",
                    contract_id=self.contract_id,
                )

        # Check each allowed root
        allowed_roots = [Path(project_root) / r for r in self.allowed_write_roots]
        for root in allowed_roots:
            try:
                root_resolved = root.resolve()
            except Exception:
                continue
            if not _is_within(abs_path, root_resolved):
                continue
            # Additional symlink-exit check: the real path must stay within root
            # (already guaranteed by _is_within on resolved paths)
            return

        raise AuthorizationError(
            "<write>",
            f"path {path!r} resolves to {abs_path} which is not within "
            f"allowed_write_roots {self.allowed_write_roots}",
            contract_id=self.contract_id,
        )

    def revoke(self, reason: str = "manual") -> None:
        self.revocation_state = "revoked"

    def mark_expired(self) -> None:
        self.revocation_state = "expired"


def _is_within(child: Path, parent: Path) -> bool:
    """Return True if child is at or under parent (both must be resolved)."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# ─── Validation ────────────────────────────────────────────────────────

@dataclass
class ContractValidationError:
    field: str
    message: str


def validate_contract(contract: AuthorizationContract) -> list[ContractValidationError]:
    errors: list[ContractValidationError] = []
    if not contract.contract_id:
        errors.append(ContractValidationError("contract_id", "required"))
    if not contract.project_root:
        errors.append(ContractValidationError("project_root", "required"))
    if not contract.project_id:
        errors.append(ContractValidationError("project_id", "required"))
    # Policy values
    for field_name in ("network_policy", "clone_policy", "download_policy",
                       "dependency_install_policy", "source_modification_policy",
                       "gpu_execution_policy"):
        val = getattr(contract, field_name, None)
        if val not in ("allow", "deny", "read-only", ""):
            errors.append(ContractValidationError(
                field_name, f"invalid value {val!r}; must be allow/deny/read-only"
            ))
    return errors


# ─── Loaders ──────────────────────────────────────────────────────────

def load_contract(path: str | Path) -> AuthorizationContract:
    """Parse and validate an authorization contract YAML file.

    Exits with code 10 on validation failure (CI compatibility).
    """
    p = Path(path)
    if not p.exists():
        print(f"[authorization] contract file not found: {p}", file=sys.stderr)
        sys.exit(10)

    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[authorization] cannot read contract {p}: {e}", file=sys.stderr)
        sys.exit(10)

    if yaml is not None:
        try:
            raw = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            print(f"[authorization] YAML error in {p}: {e}", file=sys.stderr)
            sys.exit(10)
    else:
        raw = _mini_yaml(text)

    contract = _dict_to_contract(raw)
    errors = validate_contract(contract)
    if errors:
        for e in errors:
            print(f"[authorization] {e.field}: {e.message}", file=sys.stderr)
        sys.exit(10)

    contract._loaded_from = p
    return contract


def _dict_to_contract(d: dict[str, Any]) -> AuthorizationContract:
    return AuthorizationContract(
        contract_id=str(d.get("contract_id", "")),
        project_root=str(d.get("project_root", "")),
        project_id=str(d.get("project_id", "")),
        authorization_bound_hash=str(d.get("authorization_bound_hash", "")),
        canonical_plan_hash=str(d.get("canonical_plan_hash", "")),
        git_commit=str(d.get("git_commit", "")),
        created_at=str(d.get("created_at", "")),
        expires_at=str(d.get("expires_at", "")),
        granted_actions=list(d.get("granted_actions") or []),
        denied_actions=list(d.get("denied_actions") or []),
        allowed_write_roots=list(d.get("allowed_write_roots") or []),
        network_policy=str(d.get("network_policy", "deny")),
        clone_policy=str(d.get("clone_policy", "deny")),
        download_policy=str(d.get("download_policy", "deny")),
        dependency_install_policy=str(d.get("dependency_install_policy", "deny")),
        source_modification_policy=str(d.get("source_modification_policy", "deny")),
        gpu_execution_policy=str(d.get("gpu_execution_policy", "deny")),
        training_stages=list(d.get("training_stages") or []),
        time_budget_minutes=int(d.get("time_budget_minutes", 0)) or 0,
        disk_budget_gb=int(d.get("disk_budget_gb", 0)) or 0,
        vram_budget_gb=int(d.get("vram_budget_gb", 0)) or 0,
        temperature_limit_c=int(d.get("temperature_limit_c", 0)) or 0,
        retry_limit=int(d.get("retry_limit", 3)) or 3,
        safe_repair_whitelist=list(d.get("safe_repair_whitelist") or []),
        local_commit_permission=bool(d.get("local_commit_permission", False)),
        push_pr_permission=bool(d.get("push_pr_permission", False)),
        release_permission=bool(d.get("release_permission", False)),
        revocation_state=str(d.get("revocation_state", "active")),
    )


def _mini_yaml(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.lower() in ("true", "false"):
            out[k] = v.lower() == "true"
        elif v.lower() in ("null", "~", ""):
            out[k] = None
        else:
            try:
                out[k] = int(v)
            except ValueError:
                try:
                    out[k] = float(v)
                except ValueError:
                    out[k] = v
    return out


__all__ = [
    "AuthorizationContract", "AuthorizationError",
    "ContractValidationError",
    "validate_contract", "load_contract",
]
