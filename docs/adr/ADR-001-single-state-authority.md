# ADR-001: Single State Authority for kestrel-repro

**Status**: PROPOSED (R3-0)
**Date**: 2026-07-18
**Deciders**: Refactor Agent, user review

## Context

After R2, two parallel StateStore implementations existed:

| Module | DB Path | Status |
|---|---|---|
| `scripts/startup/state_store.py` (899 LOC) | `<project_root>/.repro/execution/state.sqlite3` | R2 implementation, includes project/plan/authorization/gate/run/retry/heartbeat/evidence/migration tables, R2 state enums, fail-closed transitions |
| `scripts/orchestrator/state_store.py` (480 LOC) | `<project_root>/.repro/execution/state.sqlite3` (same path!) | Older implementation, narrower schema (tasks/approvals/events/heartbeats/metadata), used by Controller, approval_gate, stop_hook, review_loop, ostar, cvo |

Both wrote to the SAME `<project_root>/.repro/execution/state.sqlite3` path but maintained different table schemas and state semantics (e.g., orchestrator uses `PASS`/`FAIL`, startup uses R2 `PASSED`/`FAILED`/`LEGACY_UNVERIFIED`). This constitutes two state authorities reading/writing the same file, which can corrupt each other.

This violates R2 §5 ("SQLite is the only writable authoritative state") and §11 ("passing the same plan hash and authorization contract requires consistency").

## Decision

**Adopt the R2 implementation as canonical, located at `scripts/core/state_store.py`.**

### Rationale

1. **R2 schema is a strict superset**: it contains all the orchestrator's tables (tasks, approvals, events, heartbeats) plus R2 additions (project, plan, gates, authorization, runs, retries, evidence_refs, migrations, legacy_state).

2. **R2 semantics are stricter**: PASSED only by verifier, fail-closed transitions, WAIVED semantics, LEGACY_UNVERIFIED state — these need to apply to orchestrator code too.

3. **Lower migration cost**: orchestrator code calling `record_event`, `list_tasks`, `control_state`, `export_snapshots` works against R2's StateStore (which has all the same methods).

4. **DB path collision**: Both files already wrote to `<project_root>/.repro/execution/state.sqlite3`. Consolidation is a logical continuation, not a path split.

### Target Structure

```
scripts/
  core/
    state_store.py         # CANONICAL implementation (~900 LOC, R2 schema)
  startup/
    state_store.py         # THIN SHIM: from scripts.core.state_store import *
  orchestrator/
    state_store.py         # THIN SHIM: from scripts.core.state_store import *
```

### Canonical Database Path

```
<repo_root>/.repro/execution/state.sqlite3
```

This is the **same path** the legacy `scripts.orchestrator.state_store`
used, so existing chaos tests, integration tests, and runtime code do
NOT need to change. The R3-0 fix is that there is only ONE such path
per project — startup, orchestrator, and recovery all resolve through
the same `canonical_db_path()` function.

## Alternatives Considered

### A. Keep startup's StateStore as canonical, leave orchestrator unchanged

Rejected — two StateStores, two potential DRY violations, schema drift.

### B. Make orchestrator's StateStore canonical, extend it

Rejected — orchestrator's StateStore lacks R2 features (project state, gates, authorization, evidence_refs, fail-closed transitions). Extending it to match R2 is equivalent to migration but in the wrong direction (older semantics → newer).

### C. Create a third location with a unified schema

Rejected — three locations. ADR recommendation is to consolidate to ONE canonical module.

### D. Side-by-side, dual-write via synchronization

Explicitly rejected by user. Forbidden: "禁止通过'双写同步'维持两个 Store".

## Consequences

### Positive

- One StateStore implementation.
- One DB file.
- One schema.
- One transaction system.
- One migration entrypoint.
- Orchestrator benefits from R2 features (R3+ work easier).

### Negative

- Need migration from `<root>/.repro/execution/state.sqlite3` to `<root>/.repro/state/state.sqlite3`.
- Orchestrator code using R2 schema may need minor adjustments (e.g., `PASS` → `PASSED`).
- Existing tests using `tasks[].status == "PASS"` may need updating (R3-1 work).

## Implementation Plan (R3-0)

1. Create `scripts/core/__init__.py` and `scripts/core/state_store.py`.
2. Copy startup's R2 implementation into `scripts/core/state_store.py`.
3. Change DB path to `<root>/.repro/state/state.sqlite3`.
4. Make `scripts/startup/state_store.py` and `scripts/orchestrator/state_store.py` re-export from core.
5. Add canonicalization_version field to plan_schema for hash stability.
6. Update authorization_bound_hash to include schema_version + canonicalization_version.
7. Add `test_single_state_authority` to detect >1 active SQLite in project tree.
8. Run full 241-test suite and document failures.
