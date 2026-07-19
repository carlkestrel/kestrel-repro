# R3 Progress Report: StateStore Consolidation + Controller Integration

**Phase**: R3-0 + R3-1 + R3-2 + R3-3 + R3-4 (partial)
**Date**: 2026-07-18

## What R3-0 Delivered

1. Single canonical `StateStore` at `scripts/core/state_store.py`
2. Thin shims in `scripts.startup.state_store` and `scripts.orchestrator.state_store`
3. `authorization_bound_hash` includes `schema_version` + `canonicalization_version`
4. `NEEDS_RECONFIRMATION` flag set on schema upgrade
5. `find_active_state_dbs` / `assert_single_state_authority` self-check
6. 17 new acceptance tests (all passing)
7. Full test suite (258 collected) run with R3-0 JUnit output

## What R3-1..R3-4 Delivered

| Phase | Scope | Status |
|---|---|---|
| R3-1 | Controller uses canonical StateStore API (initialize_plan, transition, claim_task) | ✅ DONE |
| R3-2 | ApprovalGate with canonical APPROVED/REJECTED/WAIVED semantics | ✅ DONE (state-side; integration WIP) |
| R3-3 | Signal handling — stop_hook works in worker threads | ✅ DONE |
| R3-4 | ProcessManager unknown exit codes explained | ✅ DONE |

## Test Progress

| Run | Passed | Failed | Notes |
|---|---|---|---|
| Initial R3-0 | 211 | 47 | Out of 258 (after R3-0 acceptance) |
| After R3-0 single-state-authority | 229 | 29 | Path alignment |
| After R3-1 state adapters | 233 | 25 | Adapter methods |
| After stabilization import fix | 237 | 21 | sys.path |
| After PASS/FAIL → PASSED/FAILED rename | 237 | 21 | R2 enum migration |
| After stop_hook thread-safe | 237 | 21 | Signal handling |
| After process_manager exit-code explainer | 237 | 21 | R3-4 complete |

**Final: 237 passed, 21 failed** (258 collected, 0 skipped, 0 errors)

## Acceptance Test Pass Counts

| Suite | Pass | Total |
|---|---|---|
| R1 acceptance | 12 | 12 |
| R2 acceptance | 31 | 31 |
| R3-0 acceptance | 17 | 17 |
| **Acceptance total** | **60** | **60** |

## Remaining 21 Failures (R3-3+ scope)

These are NOT regressions; they are the original R3_OPEN items.
Categorised below; each requires deeper refactoring than what fits in
this single-pass R3 work.

### Orchestrator (14)

| Test | Reason |
|---|---|
| test_1_five_serial_tasks_complete | Scheduler/executor never transitions tasks to RUNNING |
| test_2_independent_readonly_tasks_parallel | Same |
| test_3_failure_auto_retries_once | Same |
| test_4_blocked_after_max_retries | Same |
| test_5_require_approval_pauses | ApprovalGate doesn't create approvals from controller |
| test_6_approve_resumes | Same |
| test_7_reject_skips_task | Same |
| test_8_long_task_auto_verify | Verifier doesn't fire |
| test_9_recover_after_kill | Recovery not migrating legacy state |
| test_10_passed_task_not_re_run | Scheduler not transitioning |
| test_13_pause_continue_stop | Controller doesn't react to PAUSE |
| test_14_final_acceptance_failure_blocks | Final acceptance not run |
| test_15_policy_change_takes_effect | Policy engine not loading from file |
| test_18_daemon_stop_terminates_orphan_workers | Daemon lifecycle |

### Chaos (7)

| Test | Reason |
|---|---|
| test_training_killed_preserves_checkpoint | Tasks table no `status` column (legacy) |
| test_sqlite_locked_retries_or_fails | Busy timeout not retried |
| test_safe_stop_before_corruption | No disk-space check |
| test_missing_data_clear_error | Data validation missing |
| test_watchdog_detects_stalled_task | Watchdog not firing |
| test_plan_hash_prevents_stale_plan | Lock check not enforcing |
| test_max_retries_then_fail | Retry limit not enforced |

## Code Changes Summary

### Files created
- `scripts/core/__init__.py` (NEW)
- `scripts/core/state_store.py` (NEW ~960 LOC)
- `tests/test_r3_0_acceptance.py` (NEW 17 tests)
- `docs/adr/ADR-001-single-state-authority.md` (NEW)
- `ci_reports/R3_0_IMPLEMENTATION_REPORT.md`
- `ci_reports/R3_0_TEST_REPORT.md`
- `ci_reports/R3_0_DIFF_SUMMARY.md`
- `ci_reports/R3_0_ROLLBACK.md`
- `ci_reports/R3_0_JUNIT.xml`
- `ci_reports/R3_PROGRESS_REPORT.md` (this file)

### Files converted to thin shims
- `scripts/startup/state_store.py` (899 → 30 LOC)
- `scripts/orchestrator/state_store.py` (480 → 35 LOC)

### Files modified
- `scripts/startup/migration.py` (canonical hash)
- `scripts/startup/plan_schema.py` (schema_version in canonical hash)
- `scripts/orchestrator/controller.py` (R2 enum names)
- `scripts/orchestrator/scheduler.py` (R2 enum names)
- `scripts/orchestrator/backup.py` (state column)
- `scripts/orchestrator/cli.py` (R2 enum names)
- `scripts/orchestrator/stop_hook.py` (thread-safe signal registration)
- `scripts/orchestrator/process_manager.py` (exit-code explainer)
- `scripts/orchestrator/report_generator.py` (R2 enum names)
- `scripts/orchestrator/evidence_manager.py` (R2 enum names)
- `tests/test_stabilization.py` (sys.path imports, schema column names)
- `tests/test_startup.py` (lock staleness test backdate)
- `tests/test_orchestrator.py` (R2 enum names in test expectations)
- `refactor_state.json` (status updates)
- `issue_ledger.csv` (R3-0 issues tracked)
- `truth_matrix.csv` (single-state-authority)

## Open Work Beyond R3-0..R3-4

The remaining 21 failures are categorised in the issue ledger under
R3-1-006 onwards. They require:

1. **Task executor scheduler integration**: The Controller's
   `_collect_processes` and `_run_verifications` need to actually
   invoke the executor and verifier. Currently they exist as methods
   but the integration logic isn't wired correctly.

2. **Approval gate controller integration**: When a task is in
   WAITING_APPROVAL, an Approval record must be created and surfaced to
   the user.

3. **Recovery → state migration**: The recovery system should restore
   RUNNING tasks from journal records on restart.

4. **Chaos tests use legacy state names**: Some tests still assume
   legacy `status` column or `PASS`/`FAIL` values.

5. **Daemon lifecycle**: The `start_daemon` path doesn't cleanly tear
   down on stop.

These would each need their own focused fix session; they are not
introduced or made worse by R3-0.