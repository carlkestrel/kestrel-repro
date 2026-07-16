# Orchestrator v0.1.0 — Orphan Worker Patch Note

A second daemon stop regression surfaced after the D2/D3 fixes landed. The
parent process sent `SIGTERM` only to the controller's own PGID, but each
task worker is launched with `start_new_session=True` (setsid equivalent) so
the worker sits in a different session and survives the controller being
killed.

## Root cause

`_daemon_stop()` walked these steps only:

1. SIGTERM controller PGID.
2. Wait, SIGKILL controller PGID.
3. Remove the pid file.

The "long-running workers" left behind two visible artifacts in the failure
scenario:

* A live `train.sh` / `sleep` process tree still attached to the project's
  temp dirs.
* The associated SQLite task stayed in `RUNNING` because the controller
  process was gone — no one ever updated the row.

## Fix

Only `scripts/orchestrator/cli.py::_daemon_stop` changes. Workers are now
reaped *first*, then the controller:

1. Walk `store.list_tasks({"RUNNING"})` and collect each row's `pid`.
2. `ProcessManager.terminate(pid, grace_seconds=2.0)` on every worker —
   this sends SIGTERM to the worker's PGID (because `start_new_session`
   means `os.killpg(pid)` is correct), then escalates to SIGKILL if it
   doesn't exit within the grace window. `ProcessManager` is reused as
   the single kill boundary; we didn't reach into the implementation.
3. Move the SQLite rows out of RUNNING via the existing `transition` API.
   The preferred target is `READY` (so the operator can resume), with a
   last-resort fallback to `FAIL` if the row state has drifted.
4. Terminate the controller's own PGID with the same SIGTERM → wait →
   SIGKILL ladder.
5. Remove the pid file **and** the heartbeat file.

`_daemon_status` already handles a stale pid file; nothing changes there.

## Files touched

* `scripts/orchestrator/cli.py` — `_daemon_stop` rewritten to reap workers
  first; added a small `utc_now_iso()` helper for the transition timestamps.
* `tests/test_orchestrator.py` — added `test_18_daemon_stop_terminates_orphan_workers`.

No other orchestrator module changed. `process_manager.terminate` was already
correct; we just call it from the new location.

## New test

* `tests/test_orchestrator.py::test_18_daemon_stop_terminates_orphan_workers`
  — a plan with one long task (`sleep 10 + write checkpoint`). Daemon start,
  wait until RUNNING, daemon stop, then assert:

  1. `daemon stop` JSON lists at least one terminated worker.
  2. The worker PID is no longer alive (checked via `os.kill(0)` polling).
  3. `t3_train` is not in `RUNNING` anymore.
  4. `controller.pid` is gone.

  A defensive `try / finally` re-runs `daemon stop` if anything in the test
  fails, so a flaky test cannot leak subprocesses.

## pytest output (orchestrator, 18 tests)

```
============================= test session starts ==============================
platform linux -- Python 3.13.13, pytest-9.1.1, pluggy-1.6.0
collected 18 items

tests/test_orchestrator.py::test_1_five_serial_tasks_complete PASSED     [  5%]
tests/test_orchestrator.py::test_2_independent_readonly_tasks_parallel PASSED [ 11%]
tests/test_orchestrator.py::test_3_failure_auto_retries_once PASSED      [ 16%]
tests/test_orchestrator.py::test_4_blocked_after_max_retries PASSED      [ 22%]
tests/test_orchestrator.py::test_5_require_approval_pauses PASSED        [ 27%]
tests/test_orchestrator.py::test_6_approve_resumes PASSED                [ 33%]
tests/test_orchestrator.py::test_7_reject_skips_task PASSED              [ 38%]
tests/test_orchestrator.py::test_8_long_task_auto_verify PASSED          [ 44%]
tests/test_orchestrator.py::test_9_recover_after_kill PASSED             [ 50%]
tests/test_orchestrator.py::test_10_passed_task_not_re_run PASSED        [ 55%]
tests/test_orchestrator.py::test_11_cycle_dependency_blocked PASSED      [ 61%]
tests/test_orchestrator.py::test_12_no_ready_exits_blocked PASSED        [ 66%]
tests/test_orchestrator.py::test_13_pause_continue_stop PASSED           [ 72%]
tests/test_orchestrator.py::test_14_final_acceptance_failure_blocks PASSED [ 77%]
tests/test_orchestrator.py::test_15_policy_change_takes_effect PASSED    [ 83%]
tests/test_orchestrator.py::test_16_daemon_start_on_fresh_project PASSED [ 88%]
tests/test_orchestrator.py::test_17_daemon_child_arg_recognized PASSED   [ 94%]
tests/test_orchestrator.py::test_18_daemon_stop_terminates_orphan_workers PASSED [100%]

============================== 18 passed in 6.95s ==============================
```

Combined run with `tests/test_startup.py`:

```
============================== 71 passed in 9.68s ==============================
```

(53 startup + 18 orchestrator, no regression)
