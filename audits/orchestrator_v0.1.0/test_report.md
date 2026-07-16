# Orchestrator v0.1.0 — Test Report

**Run date:** 2026-07-16
**Plugin root:** `/home/carlkestrel/.cursor/plugins/local/dl-paper-repro`
**Test command:** `python -m pytest tests/test_orchestrator.py -v`

## Result

```
============================= test session starts ==============================
platform linux -- Python 3.13.13, pytest-9.1.1, pluggy-1.6.0
collected 15 items

tests/test_orchestrator.py::test_1_five_serial_tasks_complete PASSED     [  6%]
tests/test_orchestrator.py::test_2_independent_readonly_tasks_parallel PASSED [ 13%]
tests/test_orchestrator.py::test_3_failure_auto_retries_once PASSED      [ 20%]
tests/test_orchestrator.py::test_4_blocked_after_max_retries PASSED      [ 26%]
tests/test_orchestrator.py::test_5_require_approval_pauses PASSED        [ 33%]
tests/test_orchestrator.py::test_6_approve_resumes PASSED                [ 40%]
tests/test_orchestrator.py::test_7_reject_skips_task PASSED              [ 46%]
tests/test_orchestrator.py::test_8_long_task_auto_verify PASSED          [ 53%]
tests/test_orchestrator.py::test_9_recover_after_kill PASSED             [ 60%]
tests/test_orchestrator.py::test_10_passed_task_not_re_run PASSED        [ 66%]
tests/test_orchestrator.py::test_11_cycle_dependency_blocked PASSED      [ 73%]
tests/test_orchestrator.py::test_12_no_ready_exits_blocked PASSED        [ 80%]
tests/test_orchestrator.py::test_13_pause_continue_stop PASSED           [ 86%]
tests/test_orchestrator.py::test_14_final_acceptance_failure_blocks PASSED [ 93%]
tests/test_orchestrator.py::test_15_policy_change_takes_effect PASSED    [100%]

============================== 15 passed in 6.54s ==============================
```

All 15 mandatory tests pass. The suite covers every requirement listed in the
spec: serial completion, parallel scheduling, retry promotion, hard BLOCKED
after exhausting retries, REQUIRE_APPROVAL pause, approve auto-resume, reject
skip, long-task auto-verification, crash recovery that skips `PASS` tasks,
idempotent re-runs of passed tasks, cycle detection, no-busy-loop idle exit,
pause/continue/stop, blocking on acceptance failure, and live policy reload
without a controller restart.

## Cross-suite regression

The startup test suite (`tests/test_startup.py`, 53 tests) was re-run after
the orchestrator dispatcher was added to `scripts/reproctl.py`. It remains
green:

```
============================== 68 passed in 9.23s ==============================
```

The orchestrator dispatcher is consulted first and only intercepts commands
that operate on a project that already has an orchestrator SQLite store
(`.repro/execution/state.sqlite3`). Projects without orchestrator state fall
through to the original startup dispatcher.

## Test data conventions

* Each test uses `tmp_path` to materialise an isolated `.repro/` tree.
* Long-running tasks are simulated with `sleep + heartbeat + checkpoint`
  scripts — no real GPU training is invoked.
* Acceptance tests are mock shell commands that touch the temporary tree
  only (`true`, `exit N`, `test -f …`).
* All subprocesses are spawned via `ProcessManager` (`start_new_session=True`)
  so the suite cannot leak processes between tests.

## Risk coverage summary

| Risk | Test(s) |
|------|---------|
| Concurrency bug in scheduler | 2 |
| State-machine corruption | 9, 10, 12, 13, 14 |
| Policy reload not honoured | 15 |
| Approval race condition | 5, 6, 7 |
| Retry exhaustion / silent hang | 4, 8, 12 |
| Daemon / process leak | 9, 13 |
| Re-execution of completed work | 10 |
| Dependency cycle | 11 |