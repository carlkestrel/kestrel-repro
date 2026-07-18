# R3-0 Code Diff Summary

## New files

| File | Lines | Purpose |
|---|---|---|
| `scripts/core/__init__.py` | 7 | Core package marker |
| `scripts/core/state_store.py` | ~960 | Canonical StateStore (R2+orchestrator features merged) |
| `tests/test_r3_0_acceptance.py` | ~470 | 17 R3-0 acceptance tests |
| `docs/adr/ADR-001-single-state-authority.md` | ~120 | ADR for canonical store |
| `ci_reports/R3_0_IMPLEMENTATION_REPORT.md` | ~150 | R3-0 implementation report |
| `ci_reports/R3_0_TEST_REPORT.md` | ~110 | Test results |
| `ci_reports/R3_0_JUNIT.xml` | full | JUnit XML from full suite |
| `ci_reports/R3_0_ROLLBACK.md` | ~70 | Rollback procedure |

## Files Modified

| File | Lines Before | Lines After | Change |
|---|---|---|---|
| `scripts/startup/state_store.py` | 899 | 30 | Converted to thin shim |
| `scripts/orchestrator/state_store.py` | 480 | 35 | Converted to thin shim |
| `scripts/startup/migration.py` | 331 | 343 | Use canonical authorization_bound_hash |
| `scripts/startup/plan_schema.py` | 623 | 625 | schema_version included in canonical hash |

## Key Semantic Changes

1. **Single class**: `StateStore` from `scripts.core.state_store` is now
   the only implementation. Both `scripts.startup.state_store` and
   `scripts.orchestrator.state_store` re-export it.

2. **Schema_version in canonical hash**: Plan content hash now includes
   schema_version. Changing schema invalidates plans by hash.

3. **Authorization bound hash**: New helper `compute_authorization_bound_hash`
   produces a hash that includes:
   - canonical_plan_hash
   - schema_version
   - canonicalization_version

4. **NEEDS_RECONFIRMATION**: Contracts have a `needs_reconfirmation` flag
   set when schema upgrades.

5. **Single-state-authority self-check**: `find_active_state_dbs()` and
   `assert_single_state_authority()` enforce one DB per project.

## Compatibility Notes

- Orchestrator StateStore usage `journal=...` is accepted (no-op).
- Tasks with state `PASS` / `FAIL` (legacy names) are auto-aliased to
  `PASSED` / `FAILED` in `transition_task` and `list_tasks`.
- Existing `.repro/execution/state.sqlite3` paths remain canonical
  (no path change required).

## Migration

- No DB schema migration needed for existing R2 databases — the new
  fields (`authorization_bound_hash`, `canonicalization_version`,
  `needs_reconfirmation`) are added by `CREATE TABLE IF NOT EXISTS`.
- For projects with existing pre-R2 data, `migrate_legacy_state` is
  idempotent and records SHA-256 of each legacy file.

## Test Impact

- 17 new R3-0 tests added
- 0 R2 tests broken
- 0 R1 tests broken
- 29 pre-existing R3 failures remain (out of scope for R3-0)
