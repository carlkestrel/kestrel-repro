"""Thin shim — re-exports the R3-0 canonical StateStore.

The CANONICAL implementation is at ``scripts.core.state_store``.
This file is kept ONLY for backward compatibility with existing imports
in startup-layer code. It MUST NOT define its own table schema or
transaction logic — see ADR-001.

If you need to modify the canonical StateStore, edit
``scripts/core/state_store.py`` instead.
"""
from scripts.core.state_store import (
    StateStore,
    StateConflict,
    InvalidTransition,
    PROJECT_STATES,
    TASK_STATES,
    TASK_TRANSITIONS,
    HUMAN_TRANSITIONS,
    VERIFIER_SOURCES,
    LEGACY_TASK_STATE_ALIASES,
    utc_now,
    canonical_db_path,
    canonical_repro_dir,
    compute_authorization_bound_hash,
    upgrade_schema_with_hash_reset,
    find_active_state_dbs,
    assert_single_state_authority,
    CURRENT_CANONICALIZATION_VERSION,
)

# Deprecated aliases retained so old startup code keeps working.
# These names refer to the SAME object — they are not separate implementations.
__all__ = [
    "StateStore",
    "StateConflict",
    "InvalidTransition",
    "PROJECT_STATES",
    "TASK_STATES",
    "TASK_TRANSITIONS",
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
