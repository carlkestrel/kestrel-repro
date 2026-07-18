"""R2 Plan schema: versioned, validated, canonical-hashed.

Schema version: "2.0"
Location: ``.repro/plan.yaml``

This module provides:
  * ``PlanSchema`` — a structured, typed representation of a plan.
  * ``load_plan()`` — parse + validate + hash a plan from YAML.
  * ``dump_plan()`` — serialize a plan to YAML with frontmatter.
  * ``canonical_hash()`` — deterministic hash of plan content (excludes
    source_sha256, plan_id, schema_version comments).
  * ``validate_plan()`` — structural + semantic validation returning a list
    of ``ValidationError`` objects.

Validation rules enforced here (R2 acceptance tests):
  1. Valid plan schema passes.
  2. Missing acceptance_tests rejected.
  3. Unknown dependencies rejected.
  4. Circular dependencies rejected.
  5. Unknown / illegal modes rejected.
  6. Mode migration: unambiguous modes auto-migrate, ambiguous → NEEDS_MODE_REVIEW.

The plan YAML uses YAML frontmatter format::

    ---          # frontmatter YAML
    schema_version: "2.0"
    plan_id: ...
    tasks:
      - id: T1
        acceptance_tests:
          - ...
    ---
    # body (free-form narrative)
"""
from __future__ import annotations

import hashlib
import json
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

# ─── Version ────────────────────────────────────────────────────────────
CURRENT_SCHEMA_VERSION = "2.0"

# ─── Validation errors ─────────────────────────────────────────────────


@dataclass
class ValidationError:
    field: str
    message: str
    task_id: str | None = None

    def __str__(self) -> str:
        loc = f"[task={self.task_id}] " if self.task_id else ""
        return f"{loc}{self.field}: {self.message}"


# ─── Mode model ────────────────────────────────────────────────────────

RESEARCH_PURPOSE_VALUES = frozenset({"audit", "reproduce", "extend", "takeover"})
EXECUTION_TRACK_VALUES = frozenset({"smoke", "fast", "strict", "statistical"})
AUTOMATION_LEVEL_VALUES = frozenset({"manual", "gated-autopilot"})

# Legacy modes → three-field canonical form.
# Ambiguous or unrecognised modes map to None (→ NEEDS_MODE_REVIEW).
LEGACY_MODE_MAP: dict[str, tuple[str, str, str] | None] = {
    "strict_repro":         ("reproduce", "strict", "gated-autopilot"),
    "optimized_repro_safe": ("reproduce", "fast",   "gated-autopilot"),
    "experimental_fast":    ("reproduce", "fast",   "gated-autopilot"),
    "strict":               ("reproduce", "strict", "manual"),
    "optimized":            ("reproduce", "fast",   "manual"),
    "reproduce":            ("reproduce", "strict", "gated-autopilot"),
    "diagnose":            ("audit",     "strict", "gated-autopilot"),
    "evolve":              ("extend",    "fast",   "gated-autopilot"),
    # fully-specified 3-D legacy keys
    "audit_smoke_manual":        ("audit",     "smoke",     "manual"),
    "audit_smoke_gated-autopilot": ("audit",  "smoke",     "gated-autopilot"),
    "reproduce_smoke_gated-autopilot": ("reproduce", "smoke", "gated-autopilot"),
}


def migrate_legacy_mode(mode_raw: str) -> dict[str, str] | None:
    """Map a legacy single-string mode to three fields.

    Returns None when the legacy mode is unrecognised or ambiguous,
    signalling that a human must review it.
    """
    mode = mode_raw.strip().lower()
    if mode in LEGACY_MODE_MAP:
        result = LEGACY_MODE_MAP[mode]
        if result is None:
            return None  # needs review
        purpose, track, automation = result
        return {
            "research_purpose": purpose,
            "execution_track": track,
            "automation_level": automation,
            "_migrated_from": mode_raw,
        }

    # Check if it looks like a partially-specified mode (e.g. "audit" alone)
    if mode in RESEARCH_PURPOSE_VALUES:
        # Ambiguous — missing execution_track and automation_level
        return None
    if mode in EXECUTION_TRACK_VALUES:
        return None
    if mode in AUTOMATION_LEVEL_VALUES:
        return None

    # Completely unknown
    return None


# ─── Plan dataclass ───────────────────────────────────────────────────

@dataclass
class ResourceRequirements:
    resource_class: str | None = None
    gpu_ids: list[int] = field(default_factory=list)
    gpu_exclusive: bool = False
    cpu_limit: str | None = None          # e.g. "4"
    memory_limit: str | None = None         # e.g. "16Gi"
    disk_budget: str | None = None          # e.g. "50Gi"


@dataclass
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: int = 60
    retry_on_exit_codes: list[int] = field(default_factory=lambda: [-1])


@dataclass
class TaskDef:
    id: str
    name: str
    gate: str
    deps: list[str] = field(default_factory=list)
    command: str | list[str] = field(default_factory=list)
    timeout_min: float = 30.0
    acceptance_tests: list[str] = field(default_factory=list)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    resource_requirements: ResourceRequirements = field(default_factory=ResourceRequirements)
    shell: bool = False
    writes: list[str] = field(default_factory=list)          # allowed write globs
    decision_point: str | None = None


@dataclass
class BudgetDef:
    time_minutes: int | None = None
    disk_gb: int | None = None
    vram_gb: int | None = None
    temperature_c: int | None = None
    max_retries: int = 3


@dataclass
class AuthorizationContractRef:
    contract_id: str
    path: str  # relative to project_root


@dataclass
class PlanSchema:
    schema_version: str = CURRENT_SCHEMA_VERSION
    plan_id: str = ""
    project_id: str = ""
    project_root: str = ""
    paper_identity: str = ""
    target_claims: list[str] = field(default_factory=list)
    research_intent: str = ""
    execution_track: str = "strict"
    automation_level: str = "gated-autopilot"
    research_purpose: str = "reproduce"
    repositories: list[dict[str, str]] = field(default_factory=list)
    dataset_contract: dict[str, Any] = field(default_factory=dict)
    metric_protocol: dict[str, Any] = field(default_factory=dict)
    authorization_contract_ref: AuthorizationContractRef | None = None
    budgets: BudgetDef = field(default_factory=BudgetDef)
    tasks: list[TaskDef] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    rollback_strategy: str = "safe-restart"
    mandatory_artifacts: list[str] = field(default_factory=list)
    decision_points: list[str] = field(default_factory=list)
    # Legacy tracking
    legacy_mode: str | None = None
    _needs_mode_review: bool = False
    _source_sha256: str = ""
    _canonical_sha256: str = ""
    _loaded_from: Path | None = None

    @property
    def canonical_plan_hash(self) -> str:
        return self._canonical_sha256

    @property
    def source_sha256(self) -> str:
        return self._source_sha256

    @property
    def needs_mode_review(self) -> bool:
        return self._needs_mode_review


# ─── Frontmatter parsing ──────────────────────────────────────────────

_FM_RE = re.compile(r"\A---\s*\n(?P<fm>.*?)\n---\s*(?:\n|$)", re.DOTALL)


def _load_yaml(text: str) -> dict[str, Any]:
    if yaml is not None:
        try:
            return yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error: {e}") from e
    return _mini_yaml(text)


def _mini_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML subset parser for environments without PyYAML."""
    out: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"unparsable line: {line!r}")
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


def _dict_to_task(d: dict[str, Any]) -> TaskDef:
    rp_d = d.get("retry_policy") or {}
    if isinstance(rp_d, dict):
        rp = RetryPolicy(
            max_attempts=int(rp_d.get("max_attempts", 1)),
            backoff_seconds=int(rp_d.get("backoff_seconds", 60)),
            retry_on_exit_codes=list(rp_d.get("retry_on_exit_codes", [-1])),
        )
    else:
        rp = RetryPolicy()

    rr_d = d.get("resource_requirements") or {}
    rr = ResourceRequirements(
        resource_class=rr_d.get("resource_class"),
        gpu_ids=list(rr_d.get("gpu_ids") or []),
        gpu_exclusive=bool(rr_d.get("gpu_exclusive", False)),
        cpu_limit=rr_d.get("cpu_limit"),
        memory_limit=rr_d.get("memory_limit"),
        disk_budget=rr_d.get("disk_budget"),
    )

    acc = d.get("acceptance_tests")
    if acc is None:
        acc = []
    elif isinstance(acc, str):
        acc = [acc] if acc.strip() else []

    cmd = d.get("command")
    shell = bool(d.get("shell", False))

    return TaskDef(
        id=str(d["id"]),
        name=str(d.get("name", d["id"])),
        gate=str(d.get("gate", "default")),
        deps=list(d.get("deps") or d.get("depends_on") or []),
        command=cmd if isinstance(cmd, list) else (cmd or ""),
        timeout_min=float(d.get("timeout_min", 30.0)),
        acceptance_tests=acc,
        retry_policy=rp,
        resource_requirements=rr,
        shell=shell,
        writes=list(d.get("writes") or []),
        decision_point=d.get("decision_point"),
    )


def _dict_to_plan(d: dict[str, Any], source_bytes: bytes,
                  loaded_from: Path | None = None) -> PlanSchema:
    # Source hash (over raw bytes, not parsed YAML)
    source_sha = hashlib.sha256(source_bytes).hexdigest()

    # Legacy mode detection and migration
    raw_mode = d.get("mode")
    needs_review = False
    migrated = False
    research_purpose = d.get("research_purpose", "reproduce")
    execution_track = d.get("execution_track", "strict")
    automation_level = d.get("automation_level", "gated-autopilot")

    if raw_mode is not None:
        migrated_dict = migrate_legacy_mode(str(raw_mode))
        if migrated_dict is None:
            needs_review = True
        else:
            research_purpose = migrated_dict.get("research_purpose", research_purpose)
            execution_track = migrated_dict.get("execution_track", execution_track)
            automation_level = migrated_dict.get("automation_level", automation_level)
            migrated = True

    # Canonical hash of normalised content
    # R3-0 fix: schema_version MUST be included in the canonical hash so
    # that schema upgrades change the hash and invalidate authorizations.
    # Excludes only: _source_sha (raw bytes), _loaded_from, volatile metadata.
    # Note: plan_id IS part of content — changing it changes the plan identity.
    canonical = {k: v for k, v in d.items()
                 if k not in ("_source_sha", "schema_version_comment")}
    canonical_bytes = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    canonical_sha = hashlib.sha256(canonical_bytes).hexdigest()

    # Build task list
    tasks_raw = d.get("tasks") or []
    if not isinstance(tasks_raw, list):
        tasks_raw = []

    # Budget
    b_d = d.get("budgets") or {}
    budgets = BudgetDef(
        time_minutes=b_d.get("time_minutes"),
        disk_gb=b_d.get("disk_gb"),
        vram_gb=b_d.get("vram_gb"),
        temperature_c=b_d.get("temperature_c"),
        max_retries=int(b_d.get("max_retries", 3)),
    )

    # Authorization contract ref
    auth_ref = None
    a_d = d.get("authorization_contract_ref")
    if isinstance(a_d, dict) and a_d.get("contract_id"):
        auth_ref = AuthorizationContractRef(
            contract_id=str(a_d["contract_id"]),
            path=str(a_d.get("path", ".repro/authorization_contract.yaml")),
        )

    return PlanSchema(
        schema_version=str(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        plan_id=str(d.get("plan_id", "")),
        project_id=str(d.get("project_id", "")),
        project_root=str(d.get("project_root", "")),
        paper_identity=str(d.get("paper_identity", "")),
        target_claims=list(d.get("target_claims") or []),
        research_intent=str(d.get("research_intent", "")),
        research_purpose=research_purpose,
        execution_track=execution_track,
        automation_level=automation_level,
        repositories=list(d.get("repositories") or []),
        dataset_contract=dict(d.get("dataset_contract") or {}),
        metric_protocol=dict(d.get("metric_protocol") or {}),
        authorization_contract_ref=auth_ref,
        budgets=budgets,
        tasks=[_dict_to_task(t) for t in tasks_raw],
        writes=list(d.get("writes") or []),
        rollback_strategy=str(d.get("rollback_strategy", "safe-restart")),
        mandatory_artifacts=list(d.get("mandatory_artifacts") or []),
        decision_points=list(d.get("decision_points") or []),
        legacy_mode=str(raw_mode) if raw_mode else None,
        _needs_mode_review=needs_review,
        _source_sha256=source_sha,
        _canonical_sha256=canonical_sha,
        _loaded_from=loaded_from,
    )


# ─── Validation ────────────────────────────────────────────────────────


def validate_plan(plan: PlanSchema) -> list[ValidationError]:
    errors: list[ValidationError] = []

    # Schema version
    if plan.schema_version != CURRENT_SCHEMA_VERSION:
        errors.append(ValidationError(
            "schema_version",
            f"expected {CURRENT_SCHEMA_VERSION!r}, got {plan.schema_version!r}"
        ))

    # Mode review flag
    if plan._needs_mode_review:
        errors.append(ValidationError(
            "mode",
            "ambiguous/unrecognised legacy mode requires human review"
        ))

    # Mode value checks
    if plan.execution_track not in EXECUTION_TRACK_VALUES:
        errors.append(ValidationError(
            "execution_track",
            f"invalid value {plan.execution_track!r}; must be one of {sorted(EXECUTION_TRACK_VALUES)}"
        ))
    if plan.research_purpose not in RESEARCH_PURPOSE_VALUES:
        errors.append(ValidationError(
            "research_purpose",
            f"invalid value {plan.research_purpose!r}; must be one of {sorted(RESEARCH_PURPOSE_VALUES)}"
        ))
    if plan.automation_level not in AUTOMATION_LEVEL_VALUES:
        errors.append(ValidationError(
            "automation_level",
            f"invalid value {plan.automation_level!r}; must be one of {sorted(AUTOMATION_LEVEL_VALUES)}"
        ))

    task_ids = set()
    for t in plan.tasks:
        # Duplicate task id
        if t.id in task_ids:
            errors.append(ValidationError("tasks", f"duplicate task id: {t.id!r}", task_id=t.id))
        task_ids.add(t.id)

        # Empty acceptance_tests (R2 acceptance test #2)
        if not t.acceptance_tests:
            errors.append(ValidationError(
                "acceptance_tests",
                f"task {t.id!r} has no acceptance_tests",
                task_id=t.id,
            ))

        # Unknown deps
        for dep in t.deps:
            if dep not in task_ids:
                errors.append(ValidationError(
                    "deps", f"task {t.id!r} depends on unknown task {dep!r}", task_id=t.id,
                ))

        # Cycle detection
    if _has_cycle(plan.tasks):
        errors.append(ValidationError("tasks", "circular dependency detected in task graph"))

    return errors


def _has_cycle(tasks: list[TaskDef]) -> bool:
    """Return True if the task dependency graph has a cycle."""
    by_id = {t.id: t for t in tasks}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in by_id}

    def visit(tid: str) -> bool:
        color[tid] = GRAY
        for dep in by_id[tid].deps:
            if dep not in color:
                color[dep] = GRAY  # unknown dep — will be caught elsewhere
                continue
            if color[dep] == GRAY:
                return True
            if color[dep] == WHITE and visit(dep):
                return True
        color[tid] = BLACK
        return False

    for tid in by_id:
        if color[tid] == WHITE and visit(tid):
            return True
    return False


# ─── Public loaders ───────────────────────────────────────────────────


def load_plan(path: str | Path) -> PlanSchema:
    """Parse and validate a plan YAML file.

    Raises ``SystemExit(5)`` on validation failure (for CLI compatibility).
    """
    p = Path(path)
    if not p.exists():
        print(f"[plan] file not found: {p}", file=sys.stderr)
        sys.exit(5)

    text = p.read_text(encoding="utf-8")
    source_bytes = text.encode("utf-8")

    # Strip frontmatter delimiters for the YAML parse
    m = _FM_RE.match(text)
    if not m:
        print("[plan] plan must use YAML frontmatter format (--- ... ---)",
              file=sys.stderr)
        sys.exit(5)

    fm_text = m.group("fm")
    try:
        fm = _load_yaml(fm_text)
    except ValueError as e:
        print(f"[plan] YAML parse error: {e}", file=sys.stderr)
        sys.exit(5)

    if not isinstance(fm, dict):
        print("[plan] plan frontmatter must be a YAML mapping", file=sys.stderr)
        sys.exit(5)

    plan = _dict_to_plan(fm, source_bytes, loaded_from=p)
    errors = validate_plan(plan)
    if errors:
        for err in errors:
            print(f"[plan] {err}", file=sys.stderr)
        sys.exit(5)

    return plan


def dump_plan(plan: PlanSchema, include_body: str = "") -> str:
    """Serialize a plan back to YAML frontmatter format."""
    d = {
        "schema_version": plan.schema_version,
        "plan_id": plan.plan_id,
        "project_id": plan.project_id,
        "project_root": plan.project_root,
        "paper_identity": plan.paper_identity,
        "target_claims": plan.target_claims,
        "research_intent": plan.research_intent,
        "research_purpose": plan.research_purpose,
        "execution_track": plan.execution_track,
        "automation_level": plan.automation_level,
        "repositories": plan.repositories,
        "dataset_contract": plan.dataset_contract,
        "metric_protocol": plan.metric_protocol,
        "budgets": {
            "time_minutes": plan.budgets.time_minutes,
            "disk_gb": plan.budgets.disk_gb,
            "vram_gb": plan.budgets.vram_gb,
            "temperature_c": plan.budgets.temperature_c,
            "max_retries": plan.budgets.max_retries,
        },
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "gate": t.gate,
                "deps": t.deps,
                "command": t.command,
                "shell": t.shell,
                "timeout_min": t.timeout_min,
                "acceptance_tests": t.acceptance_tests,
                "writes": t.writes,
                "retry_policy": {
                    "max_attempts": t.retry_policy.max_attempts,
                    "backoff_seconds": t.retry_policy.backoff_seconds,
                    "retry_on_exit_codes": t.retry_policy.retry_on_exit_codes,
                },
                "resource_requirements": {
                    k: v for k, v in {
                        "resource_class": t.resource_requirements.resource_class,
                        "gpu_ids": t.resource_requirements.gpu_ids,
                        "gpu_exclusive": t.resource_requirements.gpu_exclusive,
                        "cpu_limit": t.resource_requirements.cpu_limit,
                        "memory_limit": t.resource_requirements.memory_limit,
                        "disk_budget": t.resource_requirements.disk_budget,
                    }.items() if v is not None and v != [] and v != ""
                } or None,
            }
            for t in plan.tasks
        ],
        "writes": plan.writes,
        "rollback_strategy": plan.rollback_strategy,
        "mandatory_artifacts": plan.mandatory_artifacts,
        "decision_points": plan.decision_points,
    }
    if plan.legacy_mode:
        d["legacy_mode"] = plan.legacy_mode

    fm = yaml.safe_dump(d, sort_keys=False) if yaml else _dump_mini(d)
    return f"---\n{fm}---\n{include_body}"


def _dump_mini(d: dict[str, Any], indent: int = 0) -> str:
    """Minimal YAML serializer (list/dict/str/int/float/bool/None only)."""
    lines: list[str] = []
    prefix = "  " * indent
    for k, v in d.items():
        if v is None:
            lines.append(f"{prefix}{k}: null")
        elif isinstance(v, bool):
            lines.append(f"{prefix}{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{prefix}{k}: {v}")
        elif isinstance(v, str):
            lines.append(f"{prefix}{k}: {v}")
        elif isinstance(v, list):
            lines.append(f"{prefix}{k}:")
            for item in v:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    for ik, iv in item.items():
                        lines.append(f"{prefix}    {ik}: {iv}")
                else:
                    lines.append(f"{prefix}  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            lines.append(_dump_mini(v, indent + 1))
    return "\n".join(lines)


__all__ = [
    "PlanSchema", "TaskDef", "ResourceRequirements", "RetryPolicy",
    "BudgetDef", "AuthorizationContractRef", "ValidationError",
    "CURRENT_SCHEMA_VERSION",
    "RESEARCH_PURPOSE_VALUES", "EXECUTION_TRACK_VALUES", "AUTOMATION_LEVEL_VALUES",
    "LEGACY_MODE_MAP", "migrate_legacy_mode",
    "load_plan", "dump_plan", "validate_plan",
]
