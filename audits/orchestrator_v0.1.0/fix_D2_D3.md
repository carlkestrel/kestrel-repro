# Orchestrator v0.1.0 — D2/D3 Patch Note

Two blocking bugs in the daemon path were uncovered while running the daemon
end-to-end against a fresh project. Both fixes are surgical patches to
`scripts/orchestrator/cli.py`. The state machine, scheduler, state store,
verifier, watchdog, recovery, policy engine, process manager, approval gate,
event journal, and task executor are untouched.

## D2 — `daemon start` crashed on a fresh project

**Root cause:**
`_daemon_start()` opened the daemon log file via `log_path.open("ab")` *before*
the `.repro/execution/` directory existed. On a brand-new project the directory
is created lazily by `StateStore.__init__` inside the child process, but the
parent invokes `open()` first and gets `FileNotFoundError`. The crash also
leaves the pid file in a half-written state because the line follows `Popen`.

**Fix:**
Call `log_path.parent.mkdir(parents=True, exist_ok=True)` immediately after
computing `log_path`, before `Popen` opens it. This is the most local patch
and matches the recommended approach in the bug report.

**Files touched:**
- `scripts/orchestrator/cli.py` (`_daemon_start`)

## D3 — Daemon child exited 2 because `--daemon-child` was unknown

**Root cause:**
The dispatcher in `_daemon_start` passed `--daemon-child` to the re-exec'd
`reproctl.py run` so the parent could recognize the daemon-spawned process.
The `run` subparser in `orchestrator/cli.py` did not declare that flag, so
argparse immediately returned `SystemExit(2)`, the child died, and the pid
file pointed at a process that never came up.

**Fix:**
Declare `--daemon-child` on the `run` subparser with `argparse.SUPPRESS` help
and a `store_true` action. Acceptance, not behavior — the flag is recorded on
the namespace so a future code path can tell a daemon re-exec from a
foreground run if it ever needs to, but today it is a no-op. While there we
also:

* Conditionally append `--mode $X` only when the operator actually passed a
  mode (avoids forwarding `--mode None` which argparse coerces to the string
  `"None"`).
* Poll the child for ~2 s after `Popen` and clean up the pid file if the
  child exited immediately (defensive against any future argparse or env
  regression).

**Files touched:**
- `scripts/orchestrator/cli.py` (`_daemon_start`, `build_parser`)

## New tests

* `tests/test_orchestrator.py::test_16_daemon_start_on_fresh_project`
  — starts a daemon against a tmp project without `.repro/execution/`,
  asserts the log file, pid file, and heartbeat file all appear, then stops
  the daemon and confirms the child process is gone and the pid file is
  removed.
* `tests/test_orchestrator.py::test_17_daemon_child_arg_recognized`
  — parses the exact argv the daemon-spawned re-exec produces
  (including `--daemon-child`) and asserts it returns exit code != 2
  (i.e. argparse accepted the flag end-to-end through `reproctl.py`).

## pytest output (orchestrator)

```
============================= test session starts ==============================
platform linux -- Python 3.13.13, pytest-9.1.1, pluggy-1.6.0
collected 17 items

tests/test_orchestrator.py::test_1_five_serial_tasks_complete PASSED     [  5%]
tests/test_orchestrator.py::test_2_independent_readonly_tasks_parallel PASSED [ 11%]
tests/test_orchestrator.py::test_3_failure_auto_retries_once PASSED      [ 17%]
tests/test_orchestrator.py::test_4_blocked_after_max_retries PASSED      [ 23%]
tests/test_orchestrator.py::test_5_require_approval_pauses PASSED        [ 29%]
tests/test_orchestrator.py::test_6_approve_resumes PASSED                [ 35%]
tests/test_orchestrator.py::test_7_reject_skips_task PASSED              [ 41%]
tests/test_orchestrator.py::test_8_long_task_auto_verify PASSED          [ 47%]
tests/test_orchestrator.py::test_9_recover_after_kill PASSED             [ 52%]
tests/test_orchestrator.py::test_10_passed_task_not_re_run PASSED        [ 58%]
tests/test_orchestrator.py::test_11_cycle_dependency_blocked PASSED      [ 64%]
tests/test_orchestrator.py::test_12_no_ready_exits_blocked PASSED        [ 70%]
tests/test_orchestrator.py::test_13_pause_continue_stop PASSED           [ 76%]
tests/test_orchestrator.py::test_14_final_acceptance_failure_blocks PASSED [ 82%]
tests/test_orchestrator.py::test_15_policy_change_takes_effect PASSED    [ 88%]
tests/test_orchestrator.py::test_16_daemon_start_on_fresh_project PASSED [ 94%]
tests/test_orchestrator.py::test_17_daemon_child_arg_recognized PASSED   [100%]

============================== 17 passed in 6.77s ==============================
```

Combined run with `tests/test_startup.py`:

```
============================== 70 passed in 9.49s ==============================
```

(53 startup + 17 orchestrator)
