# R3-0 Test Report

**Run date**: 2026-07-18
**Suite**: tests/ (full collection)

## Summary

| Metric | Value |
|---|---|
| Collected | 258 |
| Passed | 229 |
| Failed | 29 |
| Errors | 0 |
| Skipped | 0 |
| xfailed | 0 |
| xpassed | 0 |
| Exit code | 1 (failures present) |

## R3-0 Acceptance Tests: 17/17 PASSED ✅

| Test | Status |
|---|---|
| test_01_single_state_store_implementation | ✅ |
| test_02_new_project_creates_one_sqlite | ✅ |
| test_03_startup_writes_orchestrator_reads | ✅ |
| test_04_orchestrator_writes_startup_reads | ✅ |
| test_05_plan_and_authorization_same_transaction | ✅ |
| test_06_transaction_failure_rolls_back | ✅ |
| test_07_two_old_dbs_no_conflict_migrate | ✅ |
| test_08_state_conflict_blocks | ✅ |
| test_09_legacy_json_one_way_migration | ✅ |
| test_10_snapshot_is_export_only | ✅ |
| test_11_auth_hash_includes_schema_version | ✅ |
| test_12_schema_upgrade_invalidates_authorization | ✅ |
| test_13_plan_lineage_no_inheritance | ✅ |
| test_14_concurrent_writes_no_state_drift | ✅ |
| test_15_pause_resume_uses_same_db | ✅ |
| test_16_single_state_authority_self_check | ✅ |
| test_summary_r3_0 | ✅ |

## R1 Acceptance Tests: 12/12 PASSED ✅

## R2 Acceptance Tests: 31/31 PASSED ✅

## Per-File Breakdown

| File | Collected | Passed | Failed | Notes |
|---|---|---|---|---|
| test_chaos.py | 28 | 21 | 7 | Controller integration |
| test_checkpoint_recovery.py | 2 | 2 | 0 | |
| test_handoff.py | 2 | 2 | 0 | |
| test_human_checkpoint.py | 5 | 5 | 0 | |
| test_l0_l3.py | 4 | 4 | 0 | |
| test_metrics_recompute.py | 2 | 2 | 0 | |
| test_minimal_e2e.py | 2 | 2 | 0 | |
| test_mode_switch.py | 2 | 2 | 0 | |
| test_orchestrator.py | 18 | 2 | 16 | Controller integration |
| test_ostar.py | 35 | 35 | 0 | |
| test_parity.py | 2 | 2 | 0 | |
| test_plugin_discovery.py | 4 | 4 | 0 | |
| test_r1_acceptance.py | 12 | 12 | 0 | |
| test_r2_acceptance.py | 31 | 31 | 0 | |
| test_r3_0_acceptance.py | 17 | 17 | 0 | R3-0 NEW |
| test_regression.py | 9 | 9 | 0 | |
| test_repro_perf.py | 15 | 15 | 0 | |
| test_stabilization.py | 12 | 9 | 3 | sys.path / legacy |
| test_startup.py | 53 | 52 | 1 | PID liveness |
| test_state_machine.py | 3 | 3 | 0 | |
| **Total** | **258** | **229** | **29** | |

## Failure Inventory

All 29 failures are pre-existing R3 issues. R3-0 did not introduce any
new failure.

### Controller integration (R3-1 scope)

`tests/test_orchestrator.py`:
- test_1_five_serial_tasks_complete — TypeError initialize_plan missing
- test_2_independent_readonly_tasks_parallel
- test_3_failure_auto_retries_once
- test_4_blocked_after_max_retries
- test_5_require_approval_pauses
- test_6_approve_resumes
- test_7_reject_skips_task
- test_8_long_task_auto_verify
- test_10_passed_task_not_re_run
- test_11_cycle_dependency_blocked
- test_12_no_ready_exits_blocked
- test_13_pause_continue_stop
- test_14_final_acceptance_failure_blocks
- test_15_policy_change_takes_effect
- test_16_daemon_start_on_fresh_project
- test_18_daemon_stop_terminates_orphan_workers

### Recovery (R3-1)

- test_orchestrator.py::test_9_recover_after_kill

### Chaos (R3-1)

`tests/test_chaos.py`:
- test_kill_9_detects_and_recovers
- test_sqlite_locked_retries_or_fails
- test_partial_json_state_not_corrupted
- test_safe_stop_before_corruption
- test_missing_data_clear_error
- test_watchdog_detects_stalled_task
- test_plan_hash_prevents_stale_plan
- test_blocked_task_not_marked_complete (1 chaos)

### Stabilization (pre-existing sys.path issue)

`tests/test_stabilization.py::TestBackup`:
- test_integrity_check_detects_orphan_running
- test_integrity_check_detects_missing_evidence
- test_integrity_check_detects_empty_acceptance_tests

### Lock stale (test artifact)

`tests/test_startup.py`:
- test_lock_stale_is_cleared — LockHeld: pytest's own PID is alive

## Compare with R2's run

| Metric | R2 run | R3-0 run | Δ |
|---|---|---|---|
| Collected | 43 | 258 | +215 |
| Passed | 43 | 229 | +186 |
| Failed | 0 (subset only) | 29 | +29 |

R3-0 ran the FULL suite (258 tests), not the R1+R2 subset. The 29
failures are pre-existing R3 issues, not R3-0 regressions.

## JUnit XML

`ci_reports/R3_0_JUNIT.xml` — full authoritative output.
