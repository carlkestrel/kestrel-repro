# R3F-0 Baseline Report

**Date**: 2026-07-18
**Phase**: R3F-0 (Establish trusted baseline)
**Branch**: `review/r3-20260718-a828023`
**Start SHA**: `851f3516702511e68985f54a5f3eca46d3a70c7a` (verified ✅)

---

## 1. Input state (verified at start)

| Field | Value |
|---|---|
| HEAD SHA | `851f3516702511e68985f54a5f3eca46d3a70c7a` ✅ matches expected |
| Branch | `review/r3-20260718-a828023` ✅ |
| Working tree | clean (0 dirty files) |
| Python | 3.13.13 |
| pytest | 9.1.1 |
| modules | sqlite3 ✅, yaml ✅, tomllib ✅, json ✅, pathlib ✅, subprocess ✅, signal ✅, threading ✅ |

## 2. Independent re-runs (single fresh process)

| Suite | Collected | Passed | Failed | Exit | JUnit |
|---|---|---|---|---|---|
| `tests/test_r1_acceptance.py` | 12 | 12 | 0 | 0 | `raw_logs/R1_run.xml` |
| `tests/test_r2_acceptance.py` | 31 | 31 | 0 | 0 | `raw_logs/R2_run.xml` |
| `tests/test_r3_0_acceptance.py` | 17 | 17 | 0 | 0 | `raw_logs/R3_0_run.xml` |
| `tests/test_r1_acceptance.py` + `tests/test_r2_acceptance.py` + `tests/test_r3_0_acceptance.py` (combined) | 60 | 60 | 0 | 0 | `R3F_0_JUNIT.xml` |

**Verdict**: All R1 / R2 / R3-0 acceptance suites pass. R3-0 single-state authority is locally green.

## 3. Orchestrator stability — 3 runs

Each run: `pytest tests/test_orchestrator.py --timeout=600 -p no:cacheprovider`

| Run | Wall time | Collected | Passed | Failed | Exit | JUnit |
|---|---|---|---|---|---|---|
| #1 | 60.98 s | 18 | 4 | 14 | 1 | `raw_logs/orchestrator_run_1.xml` |
| #2 | 60.97 s | 18 | 4 | 14 | 1 | `raw_logs/orchestrator_run_2.xml` |
| #3 | 60.97 s | 18 | 4 | 14 | 1 | `raw_logs/orchestrator_run_3.xml` |

**Stability verdict: DETERMINISTIC**, not nondeterministic.

Cross-run comparison: the same 14 node_ids fail in all three runs. No flake observed.
Wall-time variance < 0.5 %.

Pass-set (stable, all 3 runs): `test_11_cycle_dependency_blocked`, `test_12_no_ready_exits_blocked`, `test_16_daemon_start_on_fresh_project`, `test_17_daemon_child_arg_recognized`.

Fail-set (stable, all 3 runs, 14 of 18): see `failure_lineage.csv` rows with `classification=REGRESSION` and `root_cause starting with orchestrator_wiring`.

## 4. Chaos suite

`pytest tests/test_chaos.py --timeout=600 -p no:cacheprovider`
Wall time: 259.30 s
Result: 28 collected / 21 passed / 7 failed.
JUnit: `raw_logs/chaos_run.xml`

| Class-based test (canonical) | Status | Root cause bucket |
|---|---|---|
| `TestAutoRetryHitsLimit::test_max_retries_then_fail` | FAILED | `legacy_status_column` (chaos hits old `status` column on migrated SQLite) |
| `TestDataFileMissing::test_missing_data_clear_error` | FAILED | `is_a_directory` (test prepares a `golden` directory; copy logic crashes) |
| `TestDiskSpaceExhausted::test_safe_stop_before_corruption` | FAILED | `watchdog_command` (probes CLI sub-command that does not exist) |
| `TestLogfileStalls::test_watchdog_detects_stalled_task` | FAILED | `watchdog_command` |
| `TestPlanChangesDuringRecovery::test_plan_hash_prevents_stale_plan` | FAILED | `plan_hash_stale` (resume CLI exits 8 not 0/1) |
| `TestSqliteLocked::test_sqlite_locked_retries_or_fails` | FAILED | `sqlite_locked` (probed exit/stdout signature mismatch) |
| `TestTrainingSubprocessKilled::test_training_killed_preserves_checkpoint` | FAILED | `legacy_status_column` |

Top-level free functions `test_*` (10 of them) all PASS. The 7 failures are exclusively in the class-based reorganized tests (`tests/test_chaos.py` line 60–500). They share a common root cause pattern: tests were rewritten against the new canonical state schema / CLI surface, but the underlying code still mixes old (`status` column) and new (`state` column) access. This is a R3F-3 wiring defect, not an environment or data issue.

## 5. CI YAML inventory

| File | Lines | `jobs:` blocks | Known failure mode |
|---|---|---|---|
| `.github/workflows/ci-l1.yml` | 216 | 1 | multi-line Python `python3 -c "..."` at line ~54 is a heredoc-style block; YAML parser sees indent mismatch and fails before any Job is created |
| `.github/workflows/ci-l2.yml` | 207 | 1 | same pattern at line ~156 |
| `.github/workflows/ci-l3.yml` | 283 | 1 | same pattern at line ~184 |

All three GitHub Actions workflows fail at YAML parse time → **0 Jobs created**.
Therefore the historical statement "CI truthfully reports test failures" cannot be made: there were no Jobs to report.

## 6. Failure lineage

`failure_lineage.csv` — 106 rows.
Columns: `test_node_id, R1_status, R3_status, current_status, first_known_bad_phase, classification, root_cause, evidence`.

Counts:

| classification | count |
|---|---|
| PASSED | 85 |
| REGRESSION | 21 |

**Pre-existing claims (refused).** No `first_known_bad_phase` is marked `PRE_EXISTING` — we do not have git bisect evidence, original JUnit, or historical log that proves a specific failure existed before this branch was cut. `refactor_state.json` reports 21 failures but conflates genuine regressions with possibly older issues; without bisect we cannot attribute.

**Deterministic evidence.**

- Orchestrator 14 failures are reproducible across 3 fresh runs with identical node_ids and identical exit codes. → REGRESSION.
- Chaos 7 failures are reproducible across the same single run. Failure messages reference specific column / CLI / IO bugs that match the file system state at this SHA. → REGRESSION.

**Environment / data / nondeterministic.** None observed. The `legacy_status_column` errors would be classed `ENVIRONMENT` only if the schema was genuinely unrelated to the code; in this case the schema *is* defined by the code at this SHA, so the bug is in the code.

## 7. Process / state pollution check

- `git status --short` returned empty before R3F-0 started.
- After R3F-0, only `ci_reports/r3_repair/` (untracked) is added.
- No `.repro/` was created yet (the canonical state db is only touched when the orchestrator test scaffolds one inside a `tmp_path`).
- `tmp/pytest-of-carlkestrel/pytest-43` was created by `pytest` as part of test fixtures; this is normal.

## 8. Per-phase accounting for R3F-0

| Metric | Value |
|---|---|
| Total wall time | ~7 minutes |
| Test invocations | 6 (R1, R2, R3-0, orchestrator ×3) + 1 (chaos) |
| exit codes observed | 0, 1 |
| JUnit files produced | 7 (R1, R2, R3-0, combined, orch×3, chaos) |
| Stale lock files | 0 |
| Orphan processes | 0 |

## 9. Acceptance verdict

- [x] HEAD verified
- [x] Original commands and exit codes saved
- [x] JUnit saved
- [x] `failure_lineage.csv` generated, no false PRE_EXISTING
- [x] 3 orchestrator stability runs saved
- [x] Working tree contains only the R3F-0 report directory

**R3F-0 status: PASS. Ready to commit and push to `review/r3-20260718-a828023`.**
