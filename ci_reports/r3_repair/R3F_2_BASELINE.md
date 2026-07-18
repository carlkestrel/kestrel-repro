# R3F-2 Report — Single SQLite Authority End-to-End

**Date**: 2026-07-18
**Phase**: R3F-2
**Branch**: `review/r3-20260718-a828023`
**Start SHA**: `453a58b83294011ba47a0402f09bf5db2f3deaeb`

---

## 1. Verification of R3-0 acceptance (no regressions)

| Suite | Collected | Passed | Failed |
|---|---|---|---|
| `tests/test_r1_acceptance.py` | 12 | 12 | 0 ✅ |
| `tests/test_r2_acceptance.py` | 31 | 31 | 0 ✅ |
| `tests/test_r3_0_acceptance.py` | 17 | 17 | 0 ✅ |
| `tests/test_r3f2_single_authority.py` | 7 | 7 | 0 ✅ |
| **total** | **67** | **67** | **0** |

## 2. Issues addressed

### 2.1 Canonical StateStore doc path mismatch (task #9)

- **Before**: docstring said `<project_root>/.repro/state/state.sqlite3` (line 9)
- **After**: docstring says `<project_root>/.repro/execution/state.sqlite3`
- Verified: `StateStore._db_path` (line 129) returns the path with `.repro/execution/state.sqlite3`.
- Test: `test_canonical_doc_path_matches_actual` asserts the docstring contains the canonical path.

### 2.2 find_active_state_dbs detects legacy JSON authoritative conflict (task #10)

- **Before**: only counted SQLite DBs; ignored legacy JSON.
- **After**: scans for `execution_state.json` at canonical authoritative locations:
  - `<root>/execution_state.json`
  - `<root>/.repro/execution/execution_state.json`
  - `<root>/.execution/execution_state.json`
- When an active SQLite AND a legacy authoritative JSON coexist, raises `StartupError(code="BLOCKED_STATE_CONFLICT")` with structured `ctx` listing both.

### 2.3 New module: `scripts/startup/errors.py`

- Single source of truth for `StartupError` class and error codes (`BLOCKED_STATE_CONFLICT`, etc.).
- Avoids circular import via deferred import inside `find_active_state_dbs`.

## 3. Acceptance coverage

The R3F-2 test suite (`tests/test_r3f2_single_authority.py`) exercises:

1. `test_canonical_doc_path_matches_actual` — doc/impl consistency.
2. `test_no_active_db_returns_empty` — clean project.
3. `test_single_active_sqlite_is_found` — exactly one active SQLite.
4. `test_legacy_authoritative_json_conflict_raises` — JSON + SQLite → BLOCKED_STATE_CONFLICT.
5. `test_legacy_authoritative_json_no_sqlite_does_not_conflict` — JSON alone is not a conflict (no SQLite to conflict with).
6. `test_legacy_authoritative_json_in_subdir_raises` — JSON in `.repro/execution/` also triggers BLOCKED_STATE_CONFLICT.
7. `test_migrated_legacy_does_not_conflict` — fully-migrated project (DB marked legacy_readonly) is clean.

## 4. Single-state-authority end-to-end (per task list)

| Task | Status |
|---|---|
| `scripts/core/state_store.py` is the only state implementation | ✅ R3-0 acceptance test 1 |
| startup/orchestrator/resume/stop/approval/recovery via this store | ✅ R3-0 acceptance tests 3, 4, 15 |
| execution_state.json is export-only / migration input | ✅ R3-0 acceptance test 9 (one-way migration) |
| Snapshot cannot reverse-write to SQLite | ✅ R3-0 acceptance test 10 |
| startup/state_machine.py does not use JSON as authoritative | ✅ (only reads JSON for migration input) |
| Legacy JSON / old SQLite one-shot rollback migration | ✅ R3-0 acceptance tests 7, 8 |
| LEGACY_UNVERIFIED marking after migration | ✅ R2 acceptance test 24 |
| Multi-state conflict → BLOCKED_STATE_CONFLICT | ✅ **NEW in R3F-2**: `find_active_state_dbs` raises |
| Canonical StateStore doc path vs actual | ✅ **FIXED in R3F-2** |
| find_active_state_dbs detects JSON authoritative conflict | ✅ **NEW in R3F-2** |

## 5. Acceptance verdict

- [x] All R3-0 acceptance tests still pass (17/17)
- [x] New R3F-2 verification suite passes (7/7)
- [x] No regressions in R1/R2 acceptance (43/43)
- [x] Single SQLite authority end-to-end demonstrated

**R3F-2 status: PASS. Ready to commit and push.**
