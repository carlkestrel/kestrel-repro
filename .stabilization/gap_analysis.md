# Stabilization Gap Analysis

## Gap G-01: State Versioning Infrastructure Absent

**Status:** PARTIAL → MISSING (core fields)

**Evidence:**
- `scripts/orchestrator/state_store.py` line 83–116: `metadata` table is created with only `(key TEXT PRIMARY KEY, value TEXT NOT NULL)` — no fixed columns for `schema_version`, `plugin_version`, `created_at`, `updated_at`, `project_id`, `plan_hash`.
- `scripts/orchestrator/state_store.py` line 139–156: `set_metadata()` / `get_metadata()` operate as a generic key-value store; no enforced schema fields.
- `scripts/orchestrator/state_store.py` line 158–221: `initialize_plan()` writes `plan_id`, `plan_path`, `mode`, `automation`, `mandatory_task_ids`, `budgets` as metadata keys, but `schema_version` and `plugin_version` are never written.
- `.stabilization/stabilization_state.json` exists at plugin root (schema_version "1.0.0", plugin_version "0.2.0"), proving intent but the project-level `state.sqlite3` has no equivalent.
- `scripts/startup/recovery.py` line 24 comment: "verify plan_hash matches plan file" — comment-only; no hash computation or comparison implemented.

**Gap:** The `metadata` table lacks required versioned fields (`schema_version`, `plugin_version`, `created_at`, `updated_at`, `plan_hash`). The store is fully generic (key-value JSON blobs) with no enforced schema. No migration system exists to add these fields to existing databases. `plan_hash` (SHA-256 of plan file content) is referenced in a comment but never computed.

**Impact:** Without schema versioning, there is no way to detect schema drift, validate compatibility, or perform safe in-place upgrades. A future schema change (e.g., adding new tables, changing column types) would corrupt existing state files with no recovery path. The lack of `plan_hash` means plan file modifications after initialization go undetected.

---

## Gap G-02: Migration CLI Completely Absent

**Status:** MISSING

**Evidence:**
- `scripts/reproctl.py` lines 1–170: Dispatcher routes to `startup/cli.py` (commands: start, doctor, status, resume, stop, verify, version) and `orchestrator/cli.py` (commands: run, pause, continue, stop, status, events, next, approve, reject, daemon). No `migrate`, `backup`, `restore`, `integrity-check`, or `storage` subcommands.
- `scripts/reproctl.py` lines 1580–1609: `main()` command map has no migration-related handlers.
- `scripts/startup/cli.py`: 620-line CLI, no migrate/backup/restore/integrity-check commands.
- `scripts/orchestrator/cli.py` lines 344–414: argparse parser has no migration subparsers.
- `scripts/orchestrator/state_store.py` lines 55–62: `_connect()` sets `PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL` (infrastructure exists) but no migration code calls it.

**Gap:** All 8 migration/backup/restore/integrity commands are absent. No `reproctl migrate`, `reproctl backup`, `reproctl restore`, `reproctl integrity-check`, `reproctl storage status`, `reproctl storage cleanup` commands. The entire storage governance CLI surface is missing.

**Impact:** Users cannot migrate state across plugin versions, cannot create or restore named backups, cannot run integrity checks on demand, and cannot manage disk space. A corrupted state file has no repair path except manual intervention. Storage growth is unconstrained.

---

## Gap G-03: Schema Validation Filesystem Missing

**Status:** MISSING

**Evidence:**
- `Glob schemas/**` in plugin root: **0 files found**. No `schemas/` directory exists.
- `scripts/orchestrator/state_store.py` line 224–231: `_validate_task()` validates required keys (`id`, `name`, `gate`, `deps`, `command`, `timeout_min`, `acceptance_tests`, `retry_policy`) via Python code — no JSON Schema.
- `scripts/startup/config.py` lines 43–90: Config loading uses custom `_mini_yaml()` parser — no JSON Schema validation.
- `scripts/orchestrator/controller.py` line 34–45: `load_plan()` parses YAML/JSON but performs no schema validation.
- `scripts/startup/recovery.py` lines 38–53: `run()` reads `execution_state.json` with bare `json.loads()` — no schema validation.
- `scripts/startup/secrets_redactor.py`: Full secrets redaction implementation exists, but no schema for what constitutes a "secret field."

**Gap:** The `schemas/` directory with 7 schema files (`config.schema.json`, `plan.schema.json`, `task.schema.json`, `state.schema.json`, `adapter.schema.json`, `run_manifest.schema.json`, `evidence.schema.json`) does not exist. No schema validation occurs anywhere in the codebase. No `reproctl validate-config` or `reproctl validate-state` commands.

**Impact:** A malformed plan YAML, config, or state file silently produces incorrect behavior. There is no early-warning system for schema drift. The absence of schemas also means the migration system has no target schema to migrate toward.

---

## Gap G-04: Storage Governance CLI and Policy Absent

**Status:** MISSING

**Evidence:**
- `scripts/orchestrator/watchdog.py` lines 1–46: `Watchdog` class checks heartbeat staleness and task timeout only — no disk space monitoring.
- `scripts/orchestrator/process_manager.py` lines 1–128: `ProcessManager` creates and manages subprocesses — no disk I/O monitoring.
- `scripts/orchestrator/controller.py` line 76: `Watchdog` instantiated with no disk-related arguments.
- `scripts/orchestrator/state_store.py` lines 450–471: `export_snapshots()` creates snapshot files in `.repro/execution/` — no size management.
- `scripts/reproctl.py`: No `storage` subcommand, no retention configuration parsing, no disk policy enforcement.
- `scripts/startup/config.py` lines 27–33: `DEFAULTS` dict has no retention/disk policy fields.

**Gap:** No retention configuration (how many raw data/checkpoint/intermediate files to keep), no disk policy (free GB thresholds: warning/stop/emergency), no log rotation, no checkpoint cleanup with pre-deletion manifests, no disk-full safety stop, no cache management, and no check against uncontrolled wildcard deletes.

**Impact:** Over time, `.repro/` grows unbounded. A full disk causes opaque training failures. Checkpoints accumulate without cleanup. There is no way to recover disk space without manual intervention. No protection against `rm -rf .repro/*` mistakes.

---

## Gap G-05: Chaos Test Suite Absent

**Status:** MISSING

**Evidence:**
- `Glob chaos*` in plugin root: **0 files found**.
- `Glob tests/*.py` in plugin root: 13 test files (`test_orchestrator.py`, `test_state_machine.py`, `test_regression.py`, etc.) — all unit/integration tests, none are chaos tests.
- `scripts/orchestrator/recovery.py` lines 1–41: `RecoveryManager.recover()` handles only normal restart recovery — process alive checks, checkpoint existence, state transitions. No chaos simulation.
- `scripts/orchestrator/watchdog.py` lines 21–36: `inspect()` handles timeout detection and graceful termination — no memory, disk, or signal-based chaos.
- `scripts/orchestrator/event_journal.py` lines 36–38: Handles partial JSON in last line (torn write) but no corruption injection.

**Gap:** 6 chaos test scenarios are entirely absent: (1) `kill -9` recovery (hard-kill controller, verify state survives), (2) OOM detection (inject memory pressure, verify graceful stop), (3) checkpoint corruption detection (zero out checkpoint bytes, verify hash mismatch detected), (4) log truncation detection (truncate log file mid-write, verify truncation flagged), (5) disk full safety stop (fill disk, verify training stops gracefully), (6) false completion rejection (mark task PASS without running acceptance tests, verify rejection).

**Impact:** The recovery system is tested only against planned restarts (controller stop/restart). Crash scenarios, corruption, and resource exhaustion are unverified. Users deploying the plugin may encounter silent failures in these scenarios.

---

## Gap G-06: Golden Test Projects Absent

**Status:** MISSING

**Evidence:**
- `Glob goldens/**` in plugin root: **0 files found**.
- `Glob */goldens/**` in plugin root: **0 files found**.
- `scripts/orchestrator/state_store.py` lines 158–221: `initialize_plan()` validates plans but no golden project fixture system.
- `scripts/orchestrator/controller.py` lines 91–126: `run()` executes tasks — no golden project mode.
- `scripts/reproctl.py`: No `reproctl golden` or `reproctl test-fixture` command.

**Gap:** Three golden projects are missing: (A) minimal PyTorch fixture (MNIST-like, <1MB) for fast smoke tests, (B) point cloud fixture (PointNet minimal) for domain-specific testing, (C) real paper reproduction fixture for end-to-end validation. Associated expected state sequences and expected event sequences are also absent.

**Impact:** New users and CI cannot run a fully-defined test project that exercises the entire pipeline. Without golden projects, there is no automated way to verify that the orchestrator, state machine, recovery, and verification pipeline work end-to-end. Integration testing relies on ad-hoc manual test projects.

---

## Gap G-07: Event Schema Incomplete

**Status:** PARTIAL

**Evidence:**
- `scripts/orchestrator/state_store.py` lines 100–103: `events` table schema: `(seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, event_type TEXT NOT NULL, task_id TEXT, payload_json TEXT NOT NULL)`.
- `scripts/orchestrator/state_store.py` lines 118–132: `_event_tx()` creates event dict with `timestamp`, `event_type`, `task_id`, `payload`. `seq` assigned by SQLite autoincrement.
- Missing from event schema: `event_id` (UUID), `project_id`, `run_id`, `severity` (DEBUG/INFO/WARN/ERROR/CRITICAL), `evidence_path`.

**Gap:** Events have only 4 fields (seq, timestamp, event_type, task_id) plus a raw JSON payload. No standardized `event_id` (UUID), no `project_id` (enables cross-project event aggregation), no `run_id` (links events to specific runs), no `severity` level, and no `evidence_path`. The `payload_json` blob is unstructured, making event querying and aggregation unreliable across the system.

**Impact:** Event correlation across systems is difficult (no `event_id`). Event filtering by severity is impossible. Evidence paths for failed tasks are not systematically recorded. Cross-project monitoring and aggregation are not possible without `project_id`.

---

## Gap G-08: Secrets Integration Gaps

**Status:** PARTIAL

**Evidence:**
- `scripts/startup/secrets_redactor.py` lines 1–88: Full implementation exists with `_PATTERNS` regex (Authorization, Cookie, Bearer, api_key, password, secret_key, token), `redact()`, `scrub_env()`, `scrub_dict()`.
- `scripts/startup/cli.py` line 43: `secrets_redactor` imported.
- `scripts/orchestrator/verifier.py` lines 1–37: `Verifier` runs acceptance test commands — no secret redaction on command output or log paths.
- `scripts/orchestrator/task_executor.py`: Not read, but task commands execute raw shell commands that may emit secrets.
- `scripts/orchestrator/controller.py` line 76: `Watchdog` instantiated — no secret scanning of task log files.
- No mechanism to scan plan YAML for secret-like values before persisting.

**Gap:** `secrets_redactor.py` is implemented but integration is incomplete: (1) No automatic redaction of task log files (acceptance test logs may contain stdout/stderr with secrets), (2) no pre-persistence scan of plan/task-graph YAML files to prevent secrets from being written to durable state, (3) no redaction in error reports and error messages, (4) no minimum-privilege enforcement (filesystem permissions, capability checks).

**Impact:** If a secret (API key, token, password) appears in a training script's stdout, it can leak into log files, state records, or error reports. The redaction library exists but is not systematically applied to all output paths.
