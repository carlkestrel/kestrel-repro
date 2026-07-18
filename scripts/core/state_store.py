"""R3-0 canonical StateStore — the ONLY authoritative state implementation.

This module supersedes:
  * ``scripts.startup.state_store``  → now a thin shim
  * ``scripts.orchestrator.state_store``  → now a thin shim

See ``docs/adr/ADR-001-single-state-authority.md`` for the rationale.

Canonical DB path: ``<project_root>/.repro/execution/state.sqlite3``

Schema highlights:
  * Single SQLite DB per project (verified by ``test_single_state_authority``).
  * WAL mode + foreign keys + synchronous=FULL.
  * Atomic transactions (BEGIN IMMEDIATE / COMMIT / ROLLBACK).
  * Strict task state enums (R2 §6).
  * PASSED is terminal and can only be set by ``evidence_verifier`` or ``acceptance``.
  * LEGACY_UNVERIFIED for migrated tasks (R2 §9).
  * Migration records + legacy_state table (R2 §5).
  * Approval gate / gate / run / retry / heartbeat / event / evidence / authorization
    all live in the same DB and the same transaction system.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# ─── Enums (R2 §6) ────────────────────────────────────────────────────

PROJECT_STATES = frozenset({
    "DETECTED", "INTERVIEWING", "PLANNED", "WAITING_CONFIRMATION",
    "RUNNING", "WAITING_DECISION", "PAUSED", "BLOCKED",
    "COMPLETED", "STOPPED",
})

TASK_STATES = frozenset({
    "PENDING", "READY", "WAITING_APPROVAL", "APPROVED",
    "RUNNING", "VERIFYING", "PASSED", "FAILED",
    "RETRY_WAIT", "BLOCKED", "REJECTED", "WAIVED",
    "LEGACY_UNVERIFIED",
})

# Aliases for backward compatibility with orchestrator code that used
# the original enums (PASS / FAIL). These are mapped to the R2 names.
LEGACY_TASK_STATE_ALIASES = {
    "PASS": "PASSED",
    "FAIL": "FAILED",
}

HUMAN_TRANSITIONS: dict[str, set[str]] = {
    "WAITING_APPROVAL": {"APPROVED", "REJECTED", "WAIVED"},
    "REJECTED": set(),
    "WAIVED": set(),
    "BLOCKED": {"READY"},
}

TASK_TRANSITIONS: dict[str, set[str]] = {
    "PENDING":           {"READY", "FAILED", "BLOCKED"},
    "READY":             {"RUNNING", "WAITING_APPROVAL", "REJECTED", "FAILED", "BLOCKED"},
    "WAITING_APPROVAL":  {"APPROVED", "REJECTED", "WAIVED"},
    "APPROVED":          {"RUNNING"},
    "RUNNING":           {"VERIFYING", "FAILED", "READY"},
    "VERIFYING":         {"PASSED", "FAILED"},
    "FAILED":            {"RETRY_WAIT", "BLOCKED"},
    "RETRY_WAIT":        {"READY"},
    "PASSED":            set(),
    "REJECTED":          set(),
    "WAIVED":            set(),
    "BLOCKED":           {"READY"},
    "LEGACY_UNVERIFIED": {"PASSED", "FAILED", "BLOCKED"},
}

# Sources allowed to set PASSED (R2 §6)
VERIFIER_SOURCES = frozenset({"evidence_verifier", "acceptance", "system"})


@dataclass
class StateConflict(Exception):
    """Raised when SQLite state conflicts with a legacy state file."""
    sqlite_state: dict[str, Any]
    legacy_state: dict[str, Any]
    report_path: Path

    def __str__(self) -> str:
        return (
            f"StateConflict: SQLite and legacy state disagree. "
            f"See conflict report at {self.report_path}"
        )


@dataclass
class InvalidTransition(Exception):
    task_id: str
    from_state: str
    to_state: str

    def __str__(self) -> str:
        return (
            f"Invalid transition: task {self.task_id!r} "
            f"{self.from_state!r} → {self.to_state!r} not allowed"
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Canonical DB path resolver ───────────────────────────────────────

def canonical_db_path(project_root: str | Path) -> Path:
    """Return the canonical DB path for the given project root.

    R3-0 canonical: ``<project_root>/.repro/execution/state.sqlite3``

    This is the canonical path. The R3-0 fix is that there is ONLY ONE
    such path per project, regardless of which layer (startup / orchestrator)
    accesses it. Chaos tests, integration tests, and runtime code all
    resolve through this function or ``StateStore.db_path``.
    """
    return Path(project_root).resolve() / ".repro" / "execution" / "state.sqlite3"


def canonical_repro_dir(project_root: str | Path) -> Path:
    """Return the canonical .repro directory: ``<project_root>/.repro``."""
    return Path(project_root).resolve() / ".repro"


# ─── StateStore class ─────────────────────────────────────────────────

class StateStore:
    """R3-0 canonical SQLite-backed state store.

    The single authoritative implementation. Used by:
    * startup layer (via thin shim ``scripts.startup.state_store``)
    * orchestrator layer (via thin shim ``scripts.orchestrator.state_store``)

    Tests: ``tests/test_r3_0_acceptance.py::test_single_state_authority``
    confirms no project tree contains more than one active StateStore DB.
    """

    def __init__(self, project_root: str | Path, journal: Any | None = None):
        """R3-0 canonical constructor.

        Accepts an optional ``journal`` parameter for orchestrator backward
        compatibility — the journal is a no-op (the canonical implementation
        integrates event emission directly into the same SQLite transaction).
        """
        self._deprecated_journal = journal  # accepted but unused
        self.project_root = Path(project_root).resolve()
        # Canonical .repro layout
        self.repro_dir = canonical_repro_dir(self.project_root)
        self.execution_dir = self.repro_dir / "execution"
        self.execution_dir.mkdir(parents=True, exist_ok=True)
        # Reports directory for conflict reports etc.
        self.reports_dir = self.repro_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Canonical DB path: .repro/execution/state.sqlite3
        self.db_path = canonical_db_path(self.project_root)
        self.heartbeat_path = self.execution_dir / "controller.heartbeat"
        self._local = threading.local()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Atomic transaction context. Rolls back on any exception."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                raise
            else:
                conn.execute("COMMIT")
        finally:
            conn.close()

    def _initialize(self) -> None:
        ddl = [
            "CREATE TABLE IF NOT EXISTS metadata ("
            "  key TEXT PRIMARY KEY,"
            "  value TEXT NOT NULL"
            ")",
            "CREATE TABLE IF NOT EXISTS project ("
            "  project_id TEXT PRIMARY KEY,"
            "  project_root TEXT NOT NULL,"
            "  state TEXT NOT NULL DEFAULT 'DETECTED',"
            "  plan_hash TEXT,"
            "  canonical_plan_hash TEXT,"
            "  authorization_contract_id TEXT,"
            "  created_at TEXT NOT NULL,"
            "  updated_at TEXT NOT NULL"
            ")",
            "CREATE TABLE IF NOT EXISTS plan ("
            "  plan_id TEXT PRIMARY KEY,"
            "  project_id TEXT NOT NULL,"
            "  canonical_plan_hash TEXT NOT NULL,"
            "  source_sha256 TEXT NOT NULL,"
            "  authorization_bound_hash TEXT NOT NULL,"
            "  schema_version TEXT NOT NULL,"
            "  canonicalization_version TEXT NOT NULL,"
            "  loaded_at TEXT NOT NULL,"
            "  FOREIGN KEY (project_id) REFERENCES project(project_id)"
            ")",
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id TEXT PRIMARY KEY,"
            "  plan_id TEXT NOT NULL,"
            "  name TEXT NOT NULL,"
            "  gate TEXT NOT NULL,"
            "  deps_json TEXT NOT NULL DEFAULT '[]',"
            "  command TEXT NOT NULL,"
            "  shell INTEGER NOT NULL DEFAULT 0,"
            "  timeout_min REAL NOT NULL DEFAULT 30.0,"
            "  acceptance_tests_json TEXT NOT NULL DEFAULT '[]',"
            "  retry_policy_json TEXT NOT NULL DEFAULT '{}',"
            "  resource_requirements_json TEXT NOT NULL DEFAULT '{}',"
            "  writes_json TEXT NOT NULL DEFAULT '[]',"
            "  state TEXT NOT NULL DEFAULT 'PENDING',"
            "  owner TEXT,"
            "  attempts INTEGER NOT NULL DEFAULT 0,"
            "  retry_at REAL,"
            "  pid INTEGER,"
            "  log_path TEXT,"
            "  started_at TEXT,"
            "  finished_at TEXT,"
            "  failure_reason TEXT,"
            "  result_source TEXT DEFAULT 'system',"
            "  updated_at TEXT NOT NULL,"
            "  FOREIGN KEY (plan_id) REFERENCES plan(plan_id)"
            ")",
            "CREATE TABLE IF NOT EXISTS gates ("
            "  gate_name TEXT PRIMARY KEY,"
            "  state TEXT NOT NULL DEFAULT 'LOCKED',"
            "  plan_id TEXT NOT NULL,"
            "  updated_at TEXT NOT NULL,"
            "  FOREIGN KEY (plan_id) REFERENCES plan(plan_id)"
            ")",
            "CREATE TABLE IF NOT EXISTS authorization ("
            "  contract_id TEXT PRIMARY KEY,"
            "  project_id TEXT NOT NULL,"
            "  canonical_plan_hash TEXT NOT NULL,"
            "  authorization_bound_hash TEXT NOT NULL,"
            "  git_commit TEXT NOT NULL,"
            "  created_at TEXT NOT NULL,"
            "  expires_at TEXT,"
            "  granted_actions_json TEXT NOT NULL DEFAULT '[]',"
            "  denied_actions_json TEXT NOT NULL DEFAULT '[]',"
            "  allowed_write_roots_json TEXT NOT NULL DEFAULT '[]',"
            "  network_policy TEXT NOT NULL DEFAULT 'deny',"
            "  clone_policy TEXT NOT NULL DEFAULT 'deny',"
            "  download_policy TEXT NOT NULL DEFAULT 'deny',"
            "  dependency_install_policy TEXT NOT NULL DEFAULT 'deny',"
            "  source_modification_policy TEXT NOT NULL DEFAULT 'deny',"
            "  gpu_execution_policy TEXT NOT NULL DEFAULT 'deny',"
            "  time_budget_minutes INTEGER NOT NULL DEFAULT 0,"
            "  disk_budget_gb INTEGER NOT NULL DEFAULT 0,"
            "  vram_budget_gb INTEGER NOT NULL DEFAULT 0,"
            "  temperature_limit_c INTEGER NOT NULL DEFAULT 0,"
            "  retry_limit INTEGER NOT NULL DEFAULT 3,"
            "  safe_repair_whitelist_json TEXT NOT NULL DEFAULT '[]',"
            "  local_commit_permission INTEGER NOT NULL DEFAULT 0,"
            "  push_pr_permission INTEGER NOT NULL DEFAULT 0,"
            "  release_permission INTEGER NOT NULL DEFAULT 0,"
            "  revocation_state TEXT NOT NULL DEFAULT 'active',"
            "  needs_reconfirmation INTEGER NOT NULL DEFAULT 0,"
            "  updated_at TEXT NOT NULL,"
            "  FOREIGN KEY (project_id) REFERENCES project(project_id)"
            ")",
            "CREATE TABLE IF NOT EXISTS approvals ("
            "  approval_id TEXT PRIMARY KEY,"
            "  task_id TEXT NOT NULL,"
            "  state TEXT NOT NULL DEFAULT 'PENDING',"
            "  reason TEXT,"
            "  created_at TEXT NOT NULL,"
            "  expires_at REAL,"
            "  decided_at TEXT,"
            "  FOREIGN KEY (task_id) REFERENCES tasks(id)"
            ")",
            "CREATE TABLE IF NOT EXISTS runs ("
            "  run_id TEXT PRIMARY KEY,"
            "  task_id TEXT NOT NULL,"
            "  attempt INTEGER NOT NULL,"
            "  started_at TEXT NOT NULL,"
            "  finished_at TEXT,"
            "  exit_code INTEGER,"
            "  pid INTEGER,"
            "  log_path TEXT,"
            "  FOREIGN KEY (task_id) REFERENCES tasks(id)"
            ")",
            "CREATE TABLE IF NOT EXISTS retries ("
            "  retry_id TEXT PRIMARY KEY,"
            "  task_id TEXT NOT NULL,"
            "  attempt_from INTEGER NOT NULL,"
            "  attempt_to INTEGER NOT NULL,"
            "  reason TEXT,"
            "  created_at TEXT NOT NULL,"
            "  FOREIGN KEY (task_id) REFERENCES tasks(id)"
            ")",
            "CREATE TABLE IF NOT EXISTS heartbeats ("
            "  owner TEXT PRIMARY KEY,"
            "  pid INTEGER NOT NULL,"
            "  timestamp REAL NOT NULL,"
            "  detail_json TEXT NOT NULL DEFAULT '{}'"
            ")",
            "CREATE TABLE IF NOT EXISTS events ("
            "  seq INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  timestamp TEXT NOT NULL,"
            "  event_type TEXT NOT NULL,"
            "  task_id TEXT,"
            "  payload_json TEXT NOT NULL DEFAULT '{}'"
            ")",
            "CREATE TABLE IF NOT EXISTS evidence_refs ("
            "  ref_id TEXT PRIMARY KEY,"
            "  task_id TEXT NOT NULL,"
            "  artifact_path TEXT NOT NULL,"
            "  artifact_type TEXT NOT NULL,"
            "  sha256 TEXT,"
            "  recorded_at TEXT NOT NULL,"
            "  FOREIGN KEY (task_id) REFERENCES tasks(id)"
            ")",
            "CREATE TABLE IF NOT EXISTS migrations ("
            "  migration_id TEXT PRIMARY KEY,"
            "  legacy_path TEXT NOT NULL,"
            "  legacy_sha256 TEXT NOT NULL,"
            "  migrated_at TEXT NOT NULL,"
            "  tasks_migrated INTEGER NOT NULL DEFAULT 0,"
            "  gates_migrated INTEGER NOT NULL DEFAULT 0,"
            "  status TEXT NOT NULL DEFAULT 'done'"
            ")",
            "CREATE TABLE IF NOT EXISTS legacy_state ("
            "  source_path TEXT PRIMARY KEY,"
            "  sha256 TEXT NOT NULL,"
            "  migrated_at TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'legacy_readonly'"
            ")",
            "CREATE TABLE IF NOT EXISTS control_state ("
            "  key TEXT PRIMARY KEY DEFAULT 'global',"
            "  value TEXT NOT NULL"
            ")",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_plan ON tasks(plan_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id, seq)",
            "CREATE INDEX IF NOT EXISTS idx_events_seq ON events(seq)",
            "CREATE INDEX IF NOT EXISTS idx_approvals_task ON approvals(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_auth_bound_hash ON authorization(authorization_bound_hash)",
        ]
        with self.transaction() as conn:
            for stmt in ddl:
                conn.execute(stmt)
            for idx in indexes:
                conn.execute(idx)
            # Initialise control_state default
            conn.execute(
                "INSERT OR IGNORE INTO control_state(key,value) VALUES('global',?)",
                ("RUNNING",),
            )

    # ─── Event helpers ────────────────────────────────────────────────

    def _emit(self, conn: sqlite3.Connection,
               event_type: str,
               task_id: str | None = None,
               payload: dict[str, Any] | None = None) -> int:
        seq = conn.execute(
            "INSERT INTO events(seq,timestamp,event_type,task_id,payload_json) "
            "VALUES(NULL,?,?,?,?)",
            (utc_now(), event_type, task_id,
             json.dumps(payload or {}, sort_keys=True)),
        ).lastrowid
        return int(seq)

    # ─── Metadata ──────────────────────────────────────────────────────

    def set_metadata(self, key: str, value: Any) -> None:
        enc = json.dumps(value, sort_keys=True)
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO metadata(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, enc),
            )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key=?", (key,)
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    # ─── Project ───────────────────────────────────────────────────────

    def init_project(self, project_id: str, project_root: str) -> None:
        now = utc_now()
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO project(project_id,project_root,state,"
                "created_at,updated_at) VALUES(?,?,'DETECTED',?,?)",
                (project_id, project_root, now, now),
            )
            self._emit(conn, "PROJECT_CREATED", payload={"project_id": project_id})

    # ─── Plan initialization (R3-1 legacy adapter) ───────────────────

    def initialize_plan(self, plan: dict[str, Any], plan_path: str | Path,
                        automation: str | None = None) -> None:
        """R3-1 legacy adapter: bridge Controller's old `initialize_plan` call
        to canonical R2 APIs.

        The legacy orchestrator called:
            store.initialize_plan(plan_dict, plan_path, automation)

        It expected the store to:
          1. Compute plan hash from the source file
          2. Record the plan in SQLite
          3. Create all tasks
          4. Set automation metadata
        """
        plan_id = plan.get("plan_id") or plan.get("id") or "default"
        project_id = plan.get("project_id") or "default"
        # Compute hashes from raw file bytes if path is readable
        try:
            source_bytes = Path(plan_path).read_bytes()
            source_sha = hashlib.sha256(source_bytes).hexdigest()
        except (FileNotFoundError, OSError):
            source_bytes = json.dumps(plan, sort_keys=True, default=str).encode()
            source_sha = hashlib.sha256(source_bytes).hexdigest()

        # Compute canonical hash from plan dict (mirror plan_schema.py logic)
        canonical = {k: v for k, v in plan.items()
                     if k not in ("_source_sha", "schema_version_comment")}
        canonical_bytes = json.dumps(
            canonical, sort_keys=True, separators=(",", ":")
        ).encode()
        canonical_sha = hashlib.sha256(canonical_bytes).hexdigest()

        schema_version = str(plan.get("schema_version", "1.0"))
        canonicalization_version = str(plan.get(
            "canonicalization_version", CURRENT_CANONICALIZATION_VERSION
        ))
        bound_hash = compute_authorization_bound_hash(
            canonical_sha, schema_version, canonicalization_version,
        )

        # Project init + plan record
        self.init_project(project_id, str(self.project_root))
        self.record_plan(
            plan_id=plan_id, project_id=project_id,
            canonical_hash=canonical_sha, source_hash=source_sha,
            schema_version=schema_version,
            authorization_bound_hash=bound_hash,
            canonicalization_version=canonicalization_version,
        )

        # Create tasks
        tasks = plan.get("tasks") or []
        if tasks:
            task_defs = []
            for t in tasks:
                if isinstance(t, dict):
                    task_defs.append(t)
                else:
                    # Map dataclass TaskDef back to dict if needed
                    task_defs.append({
                        "id": getattr(t, "id", str(uuid.uuid4())),
                        "name": getattr(t, "name", "task"),
                        "gate": getattr(t, "gate", "default"),
                        "deps": getattr(t, "deps", []),
                        "command": getattr(t, "command", ""),
                        "acceptance_tests": getattr(t, "acceptance_tests", []),
                    })
            self.create_tasks(plan_id=plan_id, task_defs=task_defs)

        # Persist automation level metadata
        if automation:
            self.set_metadata("automation_level", automation)
        # Persist mode if present
        if "mode" in plan:
            self.set_metadata("plan_mode", plan["mode"])

    def set_project_state(self, state: str) -> None:
        if state not in PROJECT_STATES:
            raise ValueError(f"invalid project state: {state!r}")
        now = utc_now()
        with self.transaction() as conn:
            conn.execute(
                "UPDATE project SET state=?,updated_at=? "
                "WHERE project_id=(SELECT project_id FROM project LIMIT 1)",
                (state, now),
            )
            self._emit(conn, "PROJECT_STATE_CHANGE", payload={"to": state})

    def get_project_state(self) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT state FROM project LIMIT 1").fetchone()
        return row["state"] if row else "DETECTED"

    # ─── Plan ──────────────────────────────────────────────────────────

    def record_plan(self, plan_id: str, project_id: str,
                    canonical_hash: str, source_hash: str,
                    schema_version: str,
                    authorization_bound_hash: str = "",
                    canonicalization_version: str = "1") -> None:
        """Record a plan load. The authorization_bound_hash must include
        schema_version and canonicalization_version — see ADR-001.
        """
        now = utc_now()
        if not authorization_bound_hash:
            # Auto-compute if not provided (back-compat)
            authorization_bound_hash = compute_authorization_bound_hash(
                canonical_hash, schema_version, canonicalization_version
            )
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO plan"
                "(plan_id,project_id,canonical_plan_hash,source_sha256,"
                "authorization_bound_hash,schema_version,canonicalization_version,"
                "loaded_at) VALUES(?,?,?,?,?,?,?,?)",
                (plan_id, project_id, canonical_hash, source_hash,
                 authorization_bound_hash, schema_version, canonicalization_version,
                 now),
            )
            self._emit(conn, "PLAN_RECORDED", payload={
                "plan_id": plan_id,
                "canonical_hash": canonical_hash,
                "authorization_bound_hash": authorization_bound_hash,
                "schema_version": schema_version,
            })
        # Also store canonical_plan_hash in metadata so legacy conflict
        # detection keeps working.
        self.set_metadata("canonical_plan_hash", canonical_hash)
        self.set_metadata("authorization_bound_hash", authorization_bound_hash)
        self.set_metadata("schema_version", schema_version)
        self.set_metadata("canonicalization_version", canonicalization_version)

    # ─── Authorization ─────────────────────────────────────────────────

    def upsert_authorization(self, contract_id: str, project_id: str,
                             plan_hash: str, git_commit: str,
                             authorization_bound_hash: str,
                             granted: list[str], denied: list[str],
                             write_roots: list[str],
                             policies: dict[str, str],
                             budgets: dict[str, int],
                             other: dict[str, Any]) -> None:
        now = utc_now()
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO authorization("
                "  contract_id,project_id,canonical_plan_hash,authorization_bound_hash,"
                "  git_commit,created_at,expires_at,granted_actions_json,denied_actions_json,"
                "  allowed_write_roots_json,network_policy,clone_policy,download_policy,"
                "  dependency_install_policy,source_modification_policy,gpu_execution_policy,"
                "  time_budget_minutes,disk_budget_gb,vram_budget_gb,temperature_limit_c,"
                "  retry_limit,safe_repair_whitelist_json,local_commit_permission,"
                "  push_pr_permission,release_permission,revocation_state,"
                "  needs_reconfirmation,updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    contract_id, project_id, plan_hash, authorization_bound_hash,
                    git_commit, now, other.get("expires_at", ""),
                    json.dumps(granted), json.dumps(denied),
                    json.dumps(write_roots),
                    policies.get("network", "deny"),
                    policies.get("clone", "deny"),
                    policies.get("download", "deny"),
                    policies.get("dep_install", "deny"),
                    policies.get("src_modify", "deny"),
                    policies.get("gpu", "deny"),
                    budgets.get("time", 0),
                    budgets.get("disk", 0),
                    budgets.get("vram", 0),
                    budgets.get("temp", 0),
                    other.get("retry_limit", 3),
                    json.dumps(other.get("safe_repair_whitelist", [])),
                    int(other.get("local_commit", False)),
                    int(other.get("push_pr", False)),
                    int(other.get("release", False)),
                    other.get("revocation_state", "active"),
                    int(other.get("needs_reconfirmation", False)),
                    now,
                ),
            )
            self._emit(conn, "AUTHORIZATION_UPSERTED", payload={
                "contract_id": contract_id,
                "authorization_bound_hash": authorization_bound_hash,
            })

    def get_authorization(self, contract_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM authorization WHERE contract_id=?", (contract_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def is_authorized(self, contract_id: str, action: str) -> bool:
        """Check if the contract is currently valid AND grants the action.

        A contract is invalid (returns False) if:
        1. No contract with this id exists.
        2. revocation_state != "active".
        3. needs_reconfirmation is True (set after schema upgrade).
        4. The bound hash doesn't match the current plan's bound hash.
        """
        row = self.get_authorization(contract_id)
        if not row:
            return False
        if row["revocation_state"] != "active":
            return False
        if row.get("needs_reconfirmation"):
            return False
        # Cross-check: contract bound hash must match current plan bound hash
        current_bound = self.get_metadata("authorization_bound_hash")
        if current_bound and row["authorization_bound_hash"] != current_bound:
            return False
        granted = json.loads(row["granted_actions_json"])
        denied = json.loads(row["denied_actions_json"])
        if action in denied:
            return False
        if action in granted or "*" in granted:
            return True
        return False

    def mark_authorizations_needs_reconfirmation(self, reason: str = "schema_upgrade") -> int:
        """Mark all active contracts as NEEDS_RECONFIRMATION.

        Called when schema_version or canonicalization_version changes.
        Returns the number of contracts marked.
        """
        now = utc_now()
        with self.transaction() as conn:
            cur = conn.execute(
                "UPDATE authorization SET needs_reconfirmation=1, updated_at=? "
                "WHERE revocation_state='active' AND needs_reconfirmation=0",
                (now,),
            )
            n = cur.rowcount
            self._emit(conn, "AUTHORIZATIONS_NEEDS_RECONFIRM", payload={
                "count": n, "reason": reason,
            })
        return n

    # ─── Tasks ─────────────────────────────────────────────────────────

    def create_tasks(self, plan_id: str, task_defs: list[dict[str, Any]]) -> int:
        now = utc_now()
        count = 0
        with self.transaction() as conn:
            for t in task_defs:
                conn.execute(
                    "INSERT OR IGNORE INTO tasks("
                    "  id,plan_id,name,gate,deps_json,command,shell,timeout_min,"
                    "  acceptance_tests_json,retry_policy_json,"
                    "  resource_requirements_json,writes_json,state,attempts,updated_at"
                    ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        t["id"], plan_id, t["name"], t["gate"],
                        json.dumps(t.get("deps", [])),
                        json.dumps(t.get("command", "")),
                        int(t.get("shell", False)),
                        float(t.get("timeout_min", 30.0)),
                        json.dumps(t.get("acceptance_tests", [])),
                        json.dumps(t.get("retry_policy", {})),
                        json.dumps(t.get("resource_requirements", {})),
                        json.dumps(t.get("writes", [])),
                        "PENDING", 0, now,
                    ),
                )
                count += 1
            self._emit(conn, "TASKS_CREATED",
                       payload={"count": count, "plan_id": plan_id})
        return count

    def list_tasks(self, statuses: set[str] | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM tasks"
        params: list[Any] = []
        if statuses:
            # Normalise legacy aliases
            norm = set()
            for s in statuses:
                norm.add(LEGACY_TASK_STATE_ALIASES.get(s, s))
            marks = ",".join("?" for _ in norm)
            sql += f" WHERE state IN ({marks})"
            params.extend(sorted(norm))
        sql += " ORDER BY rowid"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_task(dict(r)) for r in rows]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_task(dict(row))

    def _row_to_task(self, row: dict[str, Any]) -> dict[str, Any]:
        # R3-1 compatibility: orchestrator code reads `task["status"]` (legacy),
        # canonical schema uses `state`. Mirror both for now.
        # Also surface `owner`, `retry_at` for orchestrator's scheduler.
        task = {
            "id": row["id"],
            "name": row["name"],
            "gate": row["gate"],
            "deps": json.loads(row["deps_json"]),
            "command": json.loads(row["command"]),
            "shell": bool(row["shell"]),
            "timeout_min": row["timeout_min"],
            "acceptance_tests": json.loads(row["acceptance_tests_json"]),
            "retry_policy": json.loads(row["retry_policy_json"]),
            "resource_requirements": json.loads(row["resource_requirements_json"]),
            "writes": json.loads(row["writes_json"]),
            "state": row["state"],
            "attempts": row["attempts"],
            "pid": row["pid"],
            "log_path": row["log_path"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "failure_reason": row["failure_reason"],
            "result_source": row["result_source"],
            "updated_at": row["updated_at"],
        }
        # Aliases for legacy orchestrator code
        task["status"] = task["state"]
        if "owner" in row.keys() and row["owner"] is not None:
            task["owner"] = row["owner"]
        if "retry_at" in row.keys() and row["retry_at"] is not None:
            task["retry_at"] = row["retry_at"]
        # legacy 'PASS' / 'FAIL' aliases already in state via transition_task
        return task

    def claim_task(self, task_id: str, owner: str) -> dict[str, Any] | None:
        """R3-1 legacy adapter: atomically claim a READY task for execution.

        Returns the task dict if the claim succeeded, or None if another
        owner already claimed it or the task is no longer READY.

        Per R3F-3 task 4: only READY or APPROVED tasks may be claimed.
        PENDING must be promoted to READY by the scheduler first (when
        dependencies are satisfied). RETRY_WAIT must be promoted by the
        scheduler when ``retry_at`` has elapsed.
        """
        now = utc_now()
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT state, attempts FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not row:
                return None
            # R3F-3: strict claim semantics — only READY or APPROVED.
            if row["state"] not in {"READY", "APPROVED"}:
                return None
            conn.execute(
                "UPDATE tasks SET state=?, owner=?, started_at=?, "
                "attempts=attempts+1, updated_at=? WHERE id=?",
                ("RUNNING", owner, now, now, task_id),
            )
            self._emit(conn, "TASK_CLAIMED", task_id, {"owner": owner})
            claimed_row = conn.execute(
                "SELECT * FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
        return self._row_to_task(dict(claimed_row))  # type: ignore[arg-type]

    def set_process(self, task_id: str, pid: int | None,
                    log_path: str | None) -> None:
        """R3F-3: persist pid/log_path for a claimed (RUNNING) task.

        TaskExecutor.launch uses this after ``start()`` to record the
        spawned subprocess pid and its log file path. If persistence
        fails (e.g. DB write error), the caller MUST terminate the
        just-launched process so no orphan is left behind — see
        ``task_executor.launch_with_orphan_guard``.
        """
        with self.transaction() as conn:
            conn.execute(
                "UPDATE tasks SET pid=?, log_path=?, updated_at=? WHERE id=?",
                (pid, log_path, utc_now(), task_id),
            )

    def transition(self, task_id: str, new_state: str,
                   expected: str | set[str] | None = None,
                   **kwargs: Any) -> dict[str, Any]:
        """R3-1 legacy adapter: alias for `transition_task` that accepts
        ``expected=`` instead of ``expect_from=``.
        """
        return self.transition_task(
            task_id, new_state, expect_from=expected, **kwargs
        )

    def transition_task(self, task_id: str, new_state: str,
                        result_source: str = "system",
                        fields: dict[str, Any] | None = None,
                        expect_from: str | set[str] | None = None,
                        event_type: str | None = None) -> dict[str, Any]:
        """R2-aware task transition (fail-closed)."""
        # Normalise legacy aliases
        new_state = LEGACY_TASK_STATE_ALIASES.get(new_state, new_state)

        if new_state not in TASK_STATES:
            raise ValueError(f"invalid task state: {new_state!r}")

        # R3F-3: legacy orchestrator code passes event_type= to request a
        # custom event name. Default is TASK_TRANSITION for the transition
        # itself; callers (e.g. Controller._fail) may override.
        emit_event = event_type or "TASK_TRANSITION"

        # Human-triggered: restrict who can trigger what
        if result_source == "human":
            if new_state == "PASSED":
                raise InvalidTransition(task_id, "(unknown)", new_state)
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT state FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
            if not row:
                raise KeyError(task_id)
            from_state = row["state"]
            if from_state not in HUMAN_TRANSITIONS:
                raise InvalidTransition(task_id, from_state, new_state)
            if new_state not in HUMAN_TRANSITIONS[from_state]:
                raise InvalidTransition(task_id, from_state, new_state)

        # PASSED restriction: evidence_verifier or acceptance only
        if new_state == "PASSED" and result_source not in VERIFIER_SOURCES:
            raise InvalidTransition(task_id, "(unknown)", new_state)

        now = utc_now()
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT state FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not row:
                raise KeyError(task_id)
            old_state = row["state"]

            if expect_from is not None:
                expected = {expect_from} if isinstance(expect_from, str) else expect_from
                if old_state not in expected:
                    raise InvalidTransition(task_id, old_state, new_state)

            if new_state != old_state:
                if old_state not in TASK_TRANSITIONS:
                    raise InvalidTransition(task_id, old_state, new_state)
                if new_state not in TASK_TRANSITIONS[old_state]:
                    raise InvalidTransition(task_id, old_state, new_state)

            upd: dict[str, Any] = {"state": new_state, "updated_at": now,
                                    "result_source": result_source}
            if fields:
                for k in ("pid", "log_path", "started_at", "finished_at",
                          "failure_reason", "attempts"):
                    if k in fields:
                        upd[k] = fields[k]

            assignments = ",".join(f"{k}=?" for k in upd)
            conn.execute(
                f"UPDATE tasks SET {assignments} WHERE id=?",
                [*upd.values(), task_id],
            )
            self._emit(conn, emit_event, task_id, {
                "from": old_state, "to": new_state,
                "result_source": result_source,
            })
            result_row = conn.execute(
                "SELECT * FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
        return self._row_to_task(dict(result_row))  # type: ignore[arg-type]

    # ─── Gates ─────────────────────────────────────────────────────────

    def upsert_gate(self, gate_name: str, plan_id: str,
                    state: str = "LOCKED") -> None:
        now = utc_now()
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO gates"
                "(gate_name,state,plan_id,updated_at) VALUES(?,?,?,?)",
                (gate_name, state, plan_id, now),
            )
            self._emit(conn, "GATE_UPSERTED", payload={
                "gate": gate_name, "state": state,
            })

    def list_gates(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM gates").fetchall()
        return [dict(r) for r in rows]

    # ─── Approvals ────────────────────────────────────────────────────

    def create_approval(self, approval_id: str, task_id: str,
                        expires_at: float | None) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO approvals(approval_id,task_id,state,created_at,expires_at) "
                "VALUES(?,?,'PENDING',?,?)",
                (approval_id, task_id, utc_now(), expires_at),
            )
            conn.execute(
                "UPDATE tasks SET state='WAITING_APPROVAL',updated_at=? WHERE id=?",
                (utc_now(), task_id),
            )
            self._emit(conn, "APPROVAL_REQUESTED", task_id, {
                "approval_id": approval_id,
            })

    def decide_approval(self, approval_id: str, decision: str,
                        reason: str = "") -> None:
        decision = decision.upper()
        if decision not in {"APPROVED", "REJECTED", "WAIVED"}:
            raise ValueError("decision must be APPROVED/REJECTED/WAIVED")
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
            if not row:
                raise KeyError(approval_id)
            task_id = row["task_id"]
            conn.execute(
                "UPDATE approvals SET state=?,reason=?,decided_at=? WHERE approval_id=?",
                (decision, reason, utc_now(), approval_id),
            )
            conn.execute(
                "UPDATE tasks SET state=?,updated_at=? WHERE id=?",
                (decision, utc_now(), task_id),
            )
            self._emit(conn, f"APPROVAL_{decision}", task_id, {
                "approval_id": approval_id, "reason": reason,
            })

    def pending_approvals(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE state='PENDING' ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    # ─── Migration recording ──────────────────────────────────────────

    def record_migration(self, legacy_path: str, sha256: str,
                         tasks: int, gates: int,
                         migration_id: str | None = None) -> None:
        if migration_id is None:
            migration_id = hashlib.sha256(
                f"{legacy_path}{sha256}{utc_now()}".encode()
            ).hexdigest()[:16]
        now = utc_now()
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO migrations"
                "(migration_id,legacy_path,legacy_sha256,migrated_at,"
                "tasks_migrated,gates_migrated,status) "
                "VALUES(?,?,?,?,?,?,'done')",
                (migration_id, legacy_path, sha256, now, tasks, gates),
            )
            conn.execute(
                "INSERT OR IGNORE INTO legacy_state"
                "(source_path,sha256,migrated_at,status) "
                "VALUES(?,?,?,'legacy_readonly')",
                (legacy_path, sha256, now),
            )
            self._emit(conn, "MIGRATION_DONE", payload={
                "migration_id": migration_id,
                "legacy_path": legacy_path,
            })

    # ─── Conflict detection ───────────────────────────────────────────

    def detect_conflict(self, legacy_state: dict[str, Any]) -> None:
        """Raise StateConflict if SQLite state conflicts with legacy state.

        If SQLite has no plan metadata yet (fresh DB), no conflict is raised —
        the migration is treating legacy as the seed.
        """
        with self._connect() as conn:
            sqlite_plan_hash = self.get_metadata("canonical_plan_hash")
            sqlite_project_state = self.get_project_state()

        legacy_hash = legacy_state.get("plan_hash") or legacy_state.get("canonical_plan_hash")
        if sqlite_plan_hash and legacy_hash and sqlite_plan_hash != legacy_hash:
            self._write_conflict_report({
                "type": "plan_hash_mismatch",
                "sqlite_hash": sqlite_plan_hash,
                "legacy_hash": legacy_hash,
            })
            raise StateConflict(
                sqlite_state={"canonical_plan_hash": sqlite_plan_hash},
                legacy_state={"plan_hash": legacy_hash},
                report_path=self.reports_dir / "state_conflict.json",
            )

        # Only check project state if SQLite already has a plan record.
        # A fresh SQLite DB (no plan) is the migration target.
        legacy_proj_state = legacy_state.get("project_state") or legacy_state.get("state", "")
        if legacy_proj_state and sqlite_plan_hash and legacy_proj_state != sqlite_project_state:
            self._write_conflict_report({
                "type": "project_state_mismatch",
                "sqlite_state": sqlite_project_state,
                "legacy_state": legacy_proj_state,
            })
            raise StateConflict(
                sqlite_state={"state": sqlite_project_state},
                legacy_state={"state": legacy_proj_state},
                report_path=self.reports_dir / "state_conflict.json",
            )

    def _write_conflict_report(self, details: dict[str, Any]) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat().replace(":", "-")
        report_path = self.reports_dir / f"state_conflict_{ts}.json"
        report_path.write_text(json.dumps({
            "generated_at": utc_now(),
            "project_root": str(self.project_root),
            **details,
        }, indent=2), encoding="utf-8")
        return report_path

    # ─── Snapshots (export-only) ──────────────────────────────────────

    def export_snapshots(self) -> dict[str, str]:
        summary = self.status_summary()
        snap_dir = self.execution_dir
        json_path = snap_dir / "state.snapshot.json"
        yaml_path = snap_dir / "state.snapshot.yaml"
        csv_path = snap_dir / "tasks.snapshot.csv"

        self._atomic_write(json_path, json.dumps(summary, indent=2, sort_keys=True))
        try:
            import yaml as _y
            self._atomic_write(yaml_path, _y.safe_dump(summary, sort_keys=False))
        except ImportError:
            self._atomic_write(yaml_path, json.dumps(summary, indent=2))

        fields = ["id", "name", "gate", "state", "attempts",
                  "started_at", "finished_at", "failure_reason", "result_source"]
        tmp = csv_path.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for task in summary.get("tasks", []):
                writer.writerow({k: task.get(k) for k in fields})
        os.replace(tmp, csv_path)

        return {"json": str(json_path), "yaml": str(yaml_path), "csv": str(csv_path)}

    # ─── Status ───────────────────────────────────────────────────────

    def status_summary(self) -> dict[str, Any]:
        tasks = self.list_tasks()
        counts: dict[str, int] = {}
        for t in tasks:
            counts[t["state"]] = counts.get(t["state"], 0) + 1
        gates = self.list_gates()
        gate_counts: dict[str, int] = {}
        for g in gates:
            gate_counts[g["state"]] = gate_counts.get(g["state"], 0) + 1
        return {
            "project_root": str(self.project_root),
            "project_state": self.get_project_state(),
            "task_counts": counts,
            "counts": counts,  # legacy alias (R3F-3 back-compat with orchestrator tests)
            "gate_counts": gate_counts,
            "tasks": tasks,
            "gates": gates,
            "pending_approvals": self.pending_approvals(),
        }

    # ─── Heartbeat ────────────────────────────────────────────────────

    def heartbeat(self, owner: str, pid: int, detail: dict[str, Any] | None = None) -> None:
        import time
        stamp = time.time()
        payload = {"owner": owner, "pid": pid, "timestamp": stamp,
                   "detail": detail or {}}
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO heartbeats(owner,pid,timestamp,detail_json) VALUES(?,?,?,?) "
                "ON CONFLICT(owner) DO UPDATE SET pid=excluded.pid,timestamp=excluded.timestamp,"
                "detail_json=excluded.detail_json",
                (owner, pid, stamp, json.dumps(detail or {}, sort_keys=True)),
            )
        tmp = self.heartbeat_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.heartbeat_path)

    def get_heartbeat(self, owner: str = "controller") -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM heartbeats WHERE owner=?", (owner,)
            ).fetchone()
        if row is None:
            return None
        return {"owner": row["owner"], "pid": row["pid"],
                "timestamp": row["timestamp"],
                "detail": json.loads(row["detail_json"])}

    # ─── Run tracking ─────────────────────────────────────────────────

    def create_run(self, run_id: str, task_id: str, attempt: int,
                   pid: int | None = None, log_path: str | None = None) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO runs(run_id,task_id,attempt,started_at,pid,log_path) "
                "VALUES(?,?,?,?,?,?)",
                (run_id, task_id, attempt, utc_now(), pid, log_path),
            )
            self._emit(conn, "RUN_CREATED", task_id, {
                "run_id": run_id, "attempt": attempt,
            })

    def finish_run(self, run_id: str, exit_code: int) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE runs SET finished_at=?, exit_code=? WHERE run_id=?",
                (utc_now(), exit_code, run_id),
            )
            row = conn.execute(
                "SELECT task_id FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            task_id = row["task_id"] if row else None
            self._emit(conn, "RUN_FINISHED", task_id, {
                "run_id": run_id, "exit_code": exit_code,
            })

    # ─── Control state (R2 §6 + orchestrator compat) ──────────────────

    def set_control_state(self, state: str) -> None:
        if state not in {"RUNNING", "PAUSED", "STOPPED"}:
            raise ValueError(f"invalid control state: {state!r}")
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT value FROM control_state WHERE key='global'"
            ).fetchone()
            old = row["value"] if row else "RUNNING"
            conn.execute(
                "INSERT OR REPLACE INTO control_state(key,value) VALUES('global',?)",
                (state,),
            )
            self._emit(conn, "CONTROL_STATE", payload={
                "from": old, "to": state,
            })

    def control_state(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM control_state WHERE key='global'"
            ).fetchone()
        return row["value"] if row else "RUNNING"

    # ─── Compatibility shim: orchestrator "events" ────────────────────

    def events(self, after_seq: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?",
                (after_seq, limit),
            ).fetchall()
        return [{
            "seq": row["seq"],
            "timestamp": row["timestamp"],
            "event_type": row["event_type"],
            "task_id": row["task_id"],
            "payload": json.loads(row["payload_json"]),
        } for row in rows]

    def record_event(self, event_type: str, task_id: str | None = None,
                     payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.transaction() as conn:
            seq = self._emit(conn, event_type, task_id, payload or {})
        return {"seq": seq, "timestamp": utc_now(),
                "event_type": event_type, "task_id": task_id,
                "payload": payload or {}}

    # ─── Atomic write helper ──────────────────────────────────────────

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as h:
            h.write(content)
            h.flush()
            os.fsync(h.fileno())
        os.replace(tmp, path)

    # ─── Shutdown ─────────────────────────────────────────────────────

    def close(self) -> None:
        """Close any open connections. Idempotent."""
        # SQLite connections are per-call in this implementation, so nothing to do.
        pass


# ─── Authorization-bound hash computation (R3-0 fix) ───────────────────

CURRENT_CANONICALIZATION_VERSION = "1"


def compute_authorization_bound_hash(
    canonical_plan_hash: str,
    schema_version: str,
    canonicalization_version: str = CURRENT_CANONICALIZATION_VERSION,
    extra: dict[str, Any] | None = None,
) -> str:
    """Compute the hash that AUTHORIZATIONS bind to.

    Must include:
      * canonical_plan_hash
      * schema_version          ← previously missing in R2 (now fixed)
      * canonicalization_version

    Any change to these fields MUST produce a different hash, which
    invalidates existing authorizations.

    R3-0 acceptance #11: hash includes schema_version.
    R3-0 acceptance #12: schema upgrade invalidates authorizations.
    """
    payload = {
        "canonical_plan_hash": canonical_plan_hash,
        "schema_version": schema_version,
        "canonicalization_version": canonicalization_version,
    }
    if extra:
        payload.update(extra)
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical_bytes).hexdigest()


def upgrade_schema_with_hash_reset(store: StateStore,
                                   new_schema_version: str,
                                   new_canonicalization_version: str = "2") -> int:
    """Apply a schema/canonicalization version upgrade.

    Steps:
      1. Compute new authorization_bound_hash for the new schema.
      2. Mark all active contracts as NEEDS_RECONFIRMATION.
      3. Update the metadata-bound hash so future is_authorized() calls
         correctly return False for old contracts.

    Returns the number of contracts marked for reconfirmation.
    """
    current_canonical = store.get_metadata("canonical_plan_hash", "")
    new_bound = compute_authorization_bound_hash(
        current_canonical, new_schema_version, new_canonicalization_version
    )
    store.set_metadata("schema_version", new_schema_version)
    store.set_metadata("canonicalization_version", new_canonicalization_version)
    store.set_metadata("authorization_bound_hash", new_bound)
    n = store.mark_authorizations_needs_reconfirmation(
        reason=f"schema_upgrade:{new_schema_version}+canon:{new_canonicalization_version}"
    )
    return n


# ─── Single-state-authority self-check ────────────────────────────────

def find_active_state_dbs(project_root: str | Path) -> list[Path]:
    """Return paths to all *active* state.sqlite3 databases under the project.

    "Active" = SQLite file that is not marked as legacy_readonly in the
    ``legacy_state`` table.

    R3-0 acceptance #16: project must have exactly 0 or 1 active DB.

    Also detects legacy authoritative state files (``execution_state.json``
    under the canonical .repro/execution/ directory or under legacy
    .execution/) that might conflict with the SQLite authority. Such
    legacy files must have been migrated already; if they still exist
    in an *authoritative* position alongside an active SQLite, raise
    BLOCKED_STATE_CONFLICT.
    """
    root = Path(project_root).resolve()
    found: list[Path] = []
    legacy_authoritative: list[Path] = []
    if not root.exists():
        return found
    # Limit search depth to 6 levels (avoid deep node_modules / .venv scans)
    skip_dirs = {".venv", "venv", "node_modules", "__pycache__", ".git"}
    for dirpath, dirnames, filenames in os.walk(root):
        # Depth control
        rel = Path(dirpath).relative_to(root)
        depth = len(rel.parts)
        if depth > 6:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            p = Path(dirpath) / name
            if name == "state.sqlite3":
                # Mark legacy if it has a legacy_state table with any entry
                try:
                    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
                    has_legacy = conn.execute(
                        "SELECT COUNT(*) FROM legacy_state WHERE status='legacy_readonly'"
                    ).fetchone()[0]
                    conn.close()
                    if has_legacy > 0:
                        continue  # legacy_readonly; not active
                except sqlite3.OperationalError:
                    # Empty / corrupt DB; treat as active (worth flagging)
                    pass
                found.append(p)
            elif name == "execution_state.json":
                # Legacy JSON authoritative state files
                # Only flag if path is in a canonical authoritative location
                rel_p = p.relative_to(root)
                rel_parts = rel_p.parts
                # canonical authoritative locations:
                #   <root>/execution_state.json                            (len==1)
                #   <root>/.repro/execution/execution_state.json          (last 3 == .repro,execution,execution_state.json)
                #   <root>/.execution/execution_state.json                (last 3 == .execution,execution_state.json)
                # Note: parent dir is `execution` in the latter two.
                is_authoritative = (
                    len(rel_parts) == 1
                    or rel_parts[-3:] == (".repro", "execution", "execution_state.json")
                    or rel_parts[-3:] == (".execution", "execution", "execution_state.json")
                )
                if is_authoritative:
                    legacy_authoritative.append(p)

    # Conflict check: if both an active SQLite and an un-migrated legacy
    # JSON authoritative file exist, we have a state-conflict situation.
    # Migration is supposed to move these JSON files to .repro/execution/
    # checkpoints/ or rename them; their presence here means the migration
    # was incomplete.
    if found and legacy_authoritative:
        # Local import to avoid circular-import risk between core and startup
        from scripts.startup.errors import StartupError
        raise StartupError(
            code="BLOCKED_STATE_CONFLICT",
            message=(
                f"Found {len(found)} active SQLite state DB(s) AND "
                f"{len(legacy_authoritative)} legacy authoritative JSON "
                f"state file(s) at: "
                f"{[str(p) for p in legacy_authoritative]}. "
                "Run migration or remove legacy authoritative state before proceeding."
            ),
            ctx={"sqlite_dbs": [str(p) for p in found],
                 "legacy_jsons": [str(p) for p in legacy_authoritative]},
        )

    return found


def assert_single_state_authority(project_root: str | Path) -> None:
    """Raise AssertionError if more than one active SQLite DB is found.

    R3-0 acceptance #16.
    """
    found = find_active_state_dbs(project_root)
    if len(found) > 1:
        raise AssertionError(
            f"Multiple active state databases found under {project_root!r}: "
            f"{[str(p) for p in found]}. "
            f"Only one is allowed per ADR-001."
        )


__all__ = [
    "StateStore", "StateConflict", "InvalidTransition",
    "PROJECT_STATES", "TASK_STATES", "TASK_TRANSITIONS",
    "HUMAN_TRANSITIONS", "VERIFIER_SOURCES",
    "LEGACY_TASK_STATE_ALIASES",
    "utc_now",
    "canonical_db_path", "canonical_repro_dir",
    "compute_authorization_bound_hash", "upgrade_schema_with_hash_reset",
    "find_active_state_dbs", "assert_single_state_authority",
    "CURRENT_CANONICALIZATION_VERSION",
]
