# Startup Completion Checklist (v0.2.0)

This document checks off each of the 10 DONE criteria from the user spec
and records where the evidence lives.

| # | Criterion | Evidence | Status |
|---|---|---|---|
| 1 | `reproctl start` runs | `scripts/reproctl.py` dispatches `start` → `scripts/startup/cli.py::cmd_start` → `state_machine.claim_one`. Verified live: `python scripts/reproctl.py start --project <P> --plan <P>` exits 0. | DONE |
| 2 | `/repro-start` calls the same entry | `commands/repro-start.md` line 28: ``python scripts/reproctl.py start ...``. Verified `grep -c 'scripts/reproctl.py' commands/repro-start.md` → 2. | DONE |
| 3 | doctor blocks invalid starts | `scripts/startup/doctor.py::run` returns `overall=FAIL` if any check is FAIL; `cmd_start` then returns exit 3 (`EXIT_DOCTOR_FAIL`). Verified live: missing plan → exit 5; bad CUDA → exit 3; disk full → exit 3. Test: `test_integ_07_cuda_mismatch`, `test_integ_08_disk_full`. | DONE |
| 4 | duplicate start blocked | `scripts/startup/lock.py::acquire` raises `LockHeld` for a live, valid lock; `cmd_start` returns exit 4. Test: `test_integ_09_duplicate_start`, `test_lock_acquire_and_reject_duplicate`. | DONE |
| 5 | dry-run has no training side-effects | `scripts/startup/state_machine.py::claim_one(dry_run=True)` returns `WOULD_CLAIM` without writing state; `cmd_start --dry-run` skips `lock_acquire`. Test: `test_integ_02_dry_run`, `test_dry_run_no_training_side_effects`. | DONE |
| 6 | resume does not re-run PASS tasks | `scripts/startup/recovery.py::run` reads `last_completed_task` / `completed_tasks`, never re-claims them, only asks `state_machine.claim_one` for the next READY. Test: `test_recovery_skips_passed_tasks`. | DONE |
| 7 | stop saves state and cleans up | `scripts/startup/stop.py::run` snapshots state to `checkpoints/execution_state.last_valid.json`, writes `stopped_at`, releases the lock. Test: `test_integ_15_stop_graceful`, `test_stop_records_state`, `test_stop_clears_lock`. | DONE |
| 8 | startup logs/state complete | On success, `cmd_start` writes `startup_state.json`, `startup.log`, `doctor_report.json`, `startup_summary.md` under `<PROJECT>/.repro/startup/`, plus `execution_state.json`, `task_graph.yaml`, `task_journal.jsonl` under `.repro/execution/`. Verified live (artifacts in `audits/startup_v0.2.0/`). | DONE |
| 9 | no hardcoded paths | `scripts/startup/*.py` uses only `Path(__file__).parents[…]`, env vars, and CLI args. Test: `test_no_hardcoded_paths_in_new_code` greps for `/home/carlkestrel`, `/Users/carlkestrel`, `/data/`, etc. | DONE |
| 10 | all mandatory startup tests PASS | 53/53 tests pass in `tests/test_startup.py`. Covers all 20 spec requirements via `test_integ_01_*` … `test_integ_20_*`. | DONE |

## Live verification log

```text
$ python scripts/reproctl.py version
{
  "reproctl": "0.2.0",
  "plugin": "0.2.0",
  "plugin_root": "/home/carlkestrel/.cursor/plugins/local/dl-paper-repro",
  "platform": "linux"
}

$ python scripts/reproctl.py start --project /tmp --plan /nonexistent.md
Repro Agent FAILED
  Stage:        DISCOVER
  Error Number: 5
  Reason:       missing --plan or plan does not exist
  Related File: /nonexistent.md
  Suggested Fix: pass --plan <PLAN_PATH> with a YAML-frontmatter plan
  Full Log:     /tmp/.repro/startup/startup.log
exit=5

$ python -m pytest tests/test_startup.py -q
.....................................................                    [100%]
53 passed in 2.74s

$ wc -l commands/repro-{start,doctor,status,resume,stop,verify}.md
29 repro-start.md
23 repro-doctor.md
19 repro-status.md
25 repro-resume.md
24 repro-stop.md
25 repro-verify.md
```

## Artifacts

All four mandated artifacts are generated under
`audits/startup_v0.2.0/` by `scripts/startup/generate_artifacts.py`:

- `startup_test_report.md`
- `command_matrix.csv`
- `recovery_test_report.md`
- `installation_checklist.md`

## Compatibility

- Legacy `reproctl.py` subcommands (`init`, `can-launch`, `launch`,
  `run-short-loop`, `report`, `update-gate`, `record-experiment`,
  `update-experiment`, `get-experiments`, `human-checkpoint`,
  `check-principles`, `help`) remain available. The dispatcher only
  intercepts the seven new unified subcommands.
- All 48 pre-existing tests still pass (101/101 across the whole
  plugin).
- Plugin version bumped `0.1.0` → `0.2.0` in `.cursor-plugin/plugin.json`.

## What was deliberately NOT done

- No `git commit`, `git push`, or publish of any kind.
- No edits to user data under `/home/carlkestrel/dl/data` (out of scope
  and explicitly forbidden by the spec).
- No `pip install` of unknown packages during the start phase.
- No hardcoded absolute paths, GPU IDs, or dataset locations.
- No auto-launch of full training during the start phase (only the
  first safe atomic task is claimed).
- The working tree is intentionally left dirty; the user will commit.
