"""R2 legacy state migration: JSON → SQLite.

Handles:
  * ``.repro/state.json`` (legacy)
  * ``execution_state.json`` (legacy)
  * ``.execution/*`` (legacy read-only)

Migration rules (R2 §9):
  1. Backup before migration (SHA-256 recorded).
  2. Do NOT delete original files.
  3. Do NOT modify user run artifacts.
  4. Output ``migration_report.json``.
  5. LEGACY_UNVERIFIED: unconfirmable PASS states → LEGACY_UNVERIFIED.
  6. BLOCKED_STATE_CONFLICT on SQLite ↔ legacy conflict.

The orchestrator's own ``state_store.py`` is not touched here; it may
continue to be used by the orchestrator subsystem. This module only
manages the startup-layer migration.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.core.state_store import StateStore
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

# R3-0: import canonical authorization-bound hash
from scripts.core.state_store import (
    CURRENT_CANONICALIZATION_VERSION,
    compute_authorization_bound_hash,
)

# ─── Migration report ─────────────────────────────────────────────────

@dataclass
class MigrationReport:
    migration_id: str
    started_at: str = ""
    finished_at: str = ""
    legacy_files: list[str] = field(default_factory=list)
    legacy_hashes: dict[str, str] = field(default_factory=dict)
    tasks_migrated: int = 0
    gates_migrated: int = 0
    tasks_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "in_progress"
    output_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "migration_id": self.migration_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "legacy_files": self.legacy_files,
            "legacy_hashes": self.legacy_hashes,
            "tasks_migrated": self.tasks_migrated,
            "gates_migrated": self.gates_migrated,
            "tasks_skipped": self.tasks_skipped,
            "errors": self.errors,
            "status": self.status,
            "output_path": self.output_path,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── SHA-256 helpers ─────────────────────────────────────────────────

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# ─── Legacy file discovery ──────────────────────────────────────────

LEGACY_FILES: list[str] = [
    ".repro/state.json",
    ".repro/execution/execution_state.json",
    ".execution/execution_state.json",
    ".execution/state.json",
    ".repro/execution/state.json",
]


def find_legacy_files(project_root: Path) -> list[Path]:
    found = []
    for rel in LEGACY_FILES:
        p = project_root / rel
        if p.exists() and p.is_file():
            try:
                with p.open("rb"):
                    pass
                found.append(p)
            except OSError:
                pass
    return found


def parse_legacy_file(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if yaml is not None:
        try:
            return yaml.safe_load(text) or {}
        except (yaml.YAMLError, TypeError):
            pass
    return None


# ─── Task migration ──────────────────────────────────────────────────

def _migrate_task_state(raw_state: str) -> tuple[str, str]:
    """Map legacy task state to R2 state.

    Rules:
    * PASS → LEGACY_UNVERIFIED (R2 §9: unconfirmable PASS not auto-PASSED)
    * FAIL → FAILED
    * READY/PENDING/BLOCKED → kept as-is
    * WAITING_APPROVAL → WAITING_APPROVAL (kept)
    * APPROVED → APPROVED
    """
    legacy = raw_state.upper()
    KNOWN = {
        "PASS", "FAIL", "READY", "PENDING", "BLOCKED",
        "WAITING_APPROVAL", "APPROVED", "REJECTED",
        "RUNNING", "VERIFYING",
    }
    if legacy == "PASS":
        return "LEGACY_UNVERIFIED", "evidence_unconfirmable"
    if legacy in KNOWN:
        return legacy, "migrated"
    return "LEGACY_UNVERIFIED", "unknown_state_migrated"


# ─── Gate migration ─────────────────────────────────────────────────

def _migrate_gate(legacy_gate: dict[str, Any]) -> dict[str, str]:
    """Map legacy gate to R2 gate."""
    legacy_state = str(legacy_gate.get("state", "LOCKED")).upper()
    if legacy_state in ("PASS", "COMPLETED"):
        return {"state": "UNLOCKED", "migrated_from": legacy_state}
    if legacy_state == "FAILED":
        return {"state": "LOCKED", "migrated_from": legacy_state}
    return {"state": "LOCKED", "migrated_from": legacy_state}


# ─── Migration executor ───────────────────────────────────────────────

def migrate_legacy_state(
    project_root: Path,
    output_dir: Path | None = None,
    store: StateStore | None = None,
) -> MigrationReport:
    """Migrate all legacy state files to the R2 SQLite store.

    Arguments:
      project_root: the reproduction project root.
      output_dir: directory for the migration report (default: .repro/reports/).
      store: an optional StateStore instance to write into. If None, only
        reports are produced and no state is written.

    Returns:
      MigrationReport with counts and SHA-256 of each backed-up file.
    """
    report_id = hashlib.sha256(
        f"{project_root}{utc_now()}".encode()
    ).hexdigest()[:16]

    report = MigrationReport(migration_id=report_id, started_at=utc_now())
    report.output_path = str(output_dir or (project_root / ".repro" / "reports"))

    legacy_files = find_legacy_files(project_root)
    report.legacy_files = [str(p) for p in legacy_files]

    # Step 1: Hash and backup (R2 §9)
    backup_dir = project_root / ".repro" / "migrations"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts_backup = backup_dir / f"legacy_{report_id}"
    ts_backup.mkdir(exist_ok=True)

    for p in legacy_files:
        h = sha256_of(p)
        report.legacy_hashes[str(p)] = h
        dest = ts_backup / p.name
        shutil.copy2(p, dest)

    # Step 2: Parse and merge legacy states
    merged_tasks: list[dict[str, Any]] = []
    merged_gates: dict[str, dict[str, str]] = {}
    project_state = "DETECTED"
    plan_hash = ""
    canonical_hash = ""

    for p in legacy_files:
        state = parse_legacy_file(p)
        if state is None:
            report.errors.append(f"could not parse {p}")
            continue

        project_state = state.get("project_state") or state.get("state") or project_state
        plan_hash = state.get("plan_hash") or plan_hash
        canonical_hash = state.get("canonical_plan_hash") or canonical_hash

        # Tasks
        legacy_tasks = state.get("tasks", [])
        if not isinstance(legacy_tasks, list):
            legacy_tasks = []
        for t in legacy_tasks:
            if not isinstance(t, dict):
                continue
            task_id = t.get("id") or t.get("task_id")
            if not task_id:
                continue
            migrated_state, reason = _migrate_task_state(t.get("status", "PENDING"))
            task = {
                "id": task_id,
                "name": t.get("name", task_id),
                "gate": t.get("gate", "default"),
                "deps": t.get("deps", []),
                "command": t.get("command", ""),
                "shell": bool(t.get("shell", False)),
                "timeout_min": float(t.get("timeout_min", 30.0)),
                "acceptance_tests": t.get("acceptance_tests", []),
                "retry_policy": t.get("retry_policy", {}),
                "resource_requirements": t.get("resource_requirements", {}),
                "writes": t.get("writes", []),
                "state": migrated_state,
                "result_source": reason,
                "attempts": int(t.get("attempts", 0)),
                "failure_reason": t.get("failure_reason"),
            }
            # Deduplicate by id (last wins)
            existing = {x["id"]: x for x in merged_tasks}
            existing[task_id] = task
            merged_tasks = list(existing.values())

        # Gates
        legacy_gates = state.get("gates", {})
        if isinstance(legacy_gates, dict):
            for g_name, g_data in legacy_gates.items():
                migrated = _migrate_gate(g_data if isinstance(g_data, dict) else {})
                merged_gates[g_name] = migrated

    report.tasks_migrated = len(merged_tasks)
    report.gates_migrated = len(merged_gates)

    # Step 3: Write into StateStore if provided
    if store is not None:
        # Check for conflicts
        from scripts.startup.state_store import StateConflict
        try:
            conflict = store.detect_conflict({
                "plan_hash": plan_hash,
                "canonical_plan_hash": canonical_hash,
                "project_state": project_state,
            })
            if conflict:
                # detect_conflict raises StateConflict
                pass
        except Exception as exc:
            if isinstance(exc, StateConflict):
                raise
            report.errors.append(f"conflict check failed: {exc}")

        # Record plan — use existing project_id if available, else create 'migrated'
        if plan_hash or canonical_hash:
            project_id_for_plan = "migrated"
            try:
                cur_proj = store._connect().execute(
                    "SELECT project_id FROM project LIMIT 1"
                ).fetchone()
                if cur_proj and cur_proj["project_id"]:
                    project_id_for_plan = cur_proj["project_id"]
            except sqlite3.OperationalError:
                pass
            # Ensure the project exists (FK reference)
            try:
                store.init_project(project_id_for_plan, str(project_root))
            except Exception:
                pass
            store.record_plan(
                plan_id="migrated",
                project_id=project_id_for_plan,
                canonical_hash=canonical_hash or plan_hash,
                source_hash=plan_hash,
                schema_version="2.0",
                authorization_bound_hash=compute_authorization_bound_hash(
                    canonical_hash or plan_hash, "2.0",
                    CURRENT_CANONICALIZATION_VERSION,
                ),
            )

        # Create tasks
        if merged_tasks:
            store.create_tasks(plan_id="migrated", task_defs=merged_tasks)

        # Upsert gates
        for g_name, g_data in merged_gates.items():
            store.upsert_gate(
                gate_name=g_name,
                plan_id="migrated",
                state=g_data.get("state", "LOCKED"),
            )

        # Record migration
        store.record_migration(
            legacy_path=",".join(report.legacy_files),
            sha256=",".join(report.legacy_hashes.values()),
            tasks=report.tasks_migrated,
            gates=report.gates_migrated,
            migration_id=report_id,
        )

    # Step 4: Write migration report
    report.finished_at = utc_now()
    report.status = "done"
    out_dir = Path(report.output_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"migration_{report_id}.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    report.output_path = str(report_path)

    return report


__all__ = [
    "MigrationReport",
    "find_legacy_files",
    "parse_legacy_file",
    "migrate_legacy_state",
    "sha256_of",
    "compute_authorization_bound_hash",
    "CURRENT_CANONICALIZATION_VERSION",
]
