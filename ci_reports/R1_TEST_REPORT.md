# R1 TEST REPORT

## Summary

| Metric | Value |
|---|---|
| Total tests | 210 |
| Passed | 197 |
| Failed | 13 |
| Errors | 0 |
| Skipped | 0 |
| Wall time | 318.26 s |
| pytest exit code | 1 (non-zero on failure) ✅ |
| JUnit XML | `ci_reports/R1_JUNIT.xml` |

## R0 → R1 deltas

| | R0 | R1 |
|---|---|---|
| Total tests | 198 | 210 |
| Passed | 174 | 197 |
| Failed | 24 | 13 |
| R1 acceptance tests | — | +12 (all green) |
| R1 residual failures | 24 | 13 (all R3 territory) |

## Required R1 acceptance subtests (must all pass)

| Suite | Required | Actual | Status |
|---|---|---|---|
| `test_plugin_discovery` | 4/4 | 4/4 | ✅ |
| `test_repro_perf` | 15/15 | 15/15 | ✅ |
| `test_l0_l3` | 4/4 (STUB ok) | 4/4 (STUB ok) | ✅ |
| `test_r1_acceptance` (new) | — | 12/12 | ✅ |

## Test inventory

```
test_chaos.py               28 tests   (21 pass / 7 fail) — R3 territory
test_checkpoint_recovery.py ? tests    (all pass)
test_handoff.py             ? tests    (all pass)
test_human_checkpoint.py    ? tests    (all pass)
test_l0_l3.py               4 tests    (4 pass, STUB state) ✅
test_metrics_recompute.py   ? tests    (all pass)
test_minimal_e2e.py         ? tests    (all pass)
test_mode_switch.py         ? tests    (all pass)
test_orchestrator.py        ? tests    (? pass / 6 fail) — R3 territory
test_ostar.py               ? tests    (all pass)
test_parity.py              ? tests    (all pass)
test_plugin_discovery.py    4 tests    (4 pass) ✅
test_r1_acceptance.py       12 tests   (12 pass) ✅ — NEW
test_regression.py          9 tests    (9 pass)
test_repro_perf.py          15 tests   (15 pass) ✅
test_stabilization.py       14 tests   (14 pass)
test_startup.py             ? tests    (all pass)
test_state_machine.py       3 tests    (3 pass)
```

## 13 residual failures (all R3 territory)

### test_chaos.py (7)

1. `TestTrainingSubprocessKilled::test_training_killed_preserves_checkpoint` —
   expected T1 == `PASS`, got `WAITING_APPROVAL` (controller-state drift)
2. `TestSqliteLocked::test_sqlite_locked_retries_or_fails` — exit code `-15`
   instead of recoverable error string
3. `TestDiskSpaceExhausted::test_safe_stop_before_corruption` —
   `watchdog` subcommand unknown (CLI surface drift)
4. `TestDataFileMissing::test_missing_data_clear_error` —
   `IsADirectoryError: 'golden' is a directory`, expected file
5. `TestLogfileStalls::test_watchdog_detects_stalled_task` —
   same `watchdog` CLI issue as #3
6. `TestPlanChangesDuringRecovery::test_plan_hash_prevents_stale_plan` —
   exit code 8 instead of recoverable
7. `TestAutoRetryHitsLimit::test_max_retries_then_fail` — retry policy
   not producing the expected final state

### test_orchestrator.py (6)

1. `test_5_require_approval_pauses`
2. `test_6_approve_resumes`
3. `test_7_reject_skips_task`
4. `test_9_recover_after_kill`
5. `test_13_pause_continue_stop`
6. `test_15_policy_change_takes_effect`

These are all `assertion` failures on Controller state transitions and
CLI surface mismatches — explicitly out of R1 scope (R3 will address
orchestrator state machines and watchdog command).

## L0–L3 status

```
$ python -m pytest tests/test_l0_l3.py -v
tests/test_l0_l3.py::test_l0_smoke             PASSED   [STUB_TEST_PASSED state]
tests/test_l0_l3.py::test_l1_overfit           PASSED   [STUB_TEST_PASSED state]
tests/test_l0_l3.py::test_l2_mini_loop         PASSED   [STUB_TEST_PASSED state]
tests/test_l0_l3.py::test_l3_checkpoint_resume PASSED   [STUB_TEST_PASSED state]
```

Per R1 invariant, L0–L3 success state is `STUB_TEST_PASSED`, NOT
`REAL_REPRO_SMOKE_PASSED`. The tests verify the scripts can be invoked
and exit cleanly under torch-less conditions; they do not certify a
real paper reproduction.

## Pytest vs `python -m pytest` parity

```
$ python -m pytest tests --collect-only -q | tail -2
210 tests collected

$ pytest tests --collect-only -q | tail -2
210 tests collected
```

Both invocations collect the same 210 tests in the editable install
environment. No drift.

## Exit-code invariant

```
$ python -m pytest tests/test_chaos.py -q  # has failures
7 failed, 21 passed
$ echo $?
1                              # non-zero, as required
```

R1 invariant `pytest has failures → exit code != 0` is preserved.

## Coverage of R1 invariants

| Invariant | How verified |
|---|---|
| `pip install -e .` succeeds in fresh venv | `test_editable_install_marker_exists`, `test_scripts_package_imports` |
| `reproctl` console script works | `test_reproctl_console_script_present`, `test_reproctl_help_runs` |
| `python -m scripts.reproctl` works | `test_reproctl_version_subcommand_runs` |
| Version three sources in sync | `test_version_three_sources_in_sync` |
| Fixtures from any cwd | `test_fixture_locator_works_from_random_cwd` |
| Commands/agents/skills/rules/templates visible | `test_other_data_roots_resolve`, `test_regression` (sub-tests 02/03/04) |
| conftest.py has no sys.path hacks | `test_no_absolute_paths_in_conftest` |
| pytest exit code non-zero on failure | shell-level check |
| No new mock-based shortcuts | grep + manual review |

## Forbidden-pattern check (final)

```
$ grep -rn "/home/\|/tmp/" tests/test_r1_acceptance.py \
                              scripts/fixture_locator.py \
                              scripts/_version.py \
                              scripts/reproctl/__main__.py \
                              tests/conftest.py
(no matches in executable code)
```

Only `[tool.setuptools.package-data]` paths and `Path(__file__).parents`
chains within `conftest._discover_plugin_root` exist, and both are
documented as the discovery-only fallback.