"""Thin shim — re-exports the R3-0 canonical StateStore.

The CANONICAL implementation is at ``scripts.core.state_store``.
This file is kept ONLY for backward compatibility with existing
orchestrator imports. It MUST NOT define its own table schema or
transaction logic — see ADR-001.

If you need to modify the canonical StateStore, edit
``scripts/core/state_store.py`` instead.

Note: legacy callers that used `PASS` / `FAIL` enums should be updated to
`PASSED` / `FAILED` (R2 names). For temporary compatibility, the canonical
StateStore automatically aliases `PASS` → `PASSED` and `FAIL` → `FAILED`
in `transition_task` and `list_tasks`.
"""

from scripts.core.state_store import (
    CURRENT_CANONICALIZATION_VERSION,
    HUMAN_TRANSITIONS,
    LEGACY_TASK_STATE_ALIASES,
    PROJECT_STATES,
    TASK_STATES,
    TASK_TRANSITIONS,
    VERIFIER_SOURCES,
    InvalidTransition,
    StateConflict,
    StateStore,
    assert_single_state_authority,
    canonical_db_path,
    canonical_repro_dir,
    compute_authorization_bound_hash,
    find_active_state_dbs,
    upgrade_schema_with_hash_reset,
    utc_now,
)

# Backward-compat alias names
TRANSITIONS = TASK_TRANSITIONS
CONTROL_STATES = {"RUNNING", "PAUSED", "STOPPED"}

__all__ = [
    "StateStore",
    "StateConflict",
    "InvalidTransition",
    "PROJECT_STATES",
    "TASK_STATES",
    "TASK_TRANSITIONS",
    "TRANSITIONS",
    "CONTROL_STATES",
    "HUMAN_TRANSITIONS",
    "VERIFIER_SOURCES",
    "LEGACY_TASK_STATE_ALIASES",
    "utc_now",
    "canonical_db_path",
    "canonical_repro_dir",
    "compute_authorization_bound_hash",
    "upgrade_schema_with_hash_reset",
    "find_active_state_dbs",
    "assert_single_state_authority",
    "CURRENT_CANONICALIZATION_VERSION",
]
