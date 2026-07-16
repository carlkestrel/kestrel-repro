# Recovery Test Report (v0.2.0)

## What is exercised

1. **Interrupted recovery** — execution_state.json carries
   `interrupted=True` and `current_task=<T>`. `reproctl resume`
   re-acquires the lock, validates the plan_hash, and claims the
   next READY task.
2. **Plan hash changed** — execution_state.json has a different
   `plan_hash` than the on-disk plan. `reproctl resume` writes a
   `plan_change_report.md` and exits with code 8.
3. **Corrupted state** — execution_state.json contains invalid
   JSON. The corrupt file is archived under
   `.repro/execution/checkpoints/execution_state.corrupt.<ts>.json`
   and the startup pipeline exits with code 8.
4. **Stale lock** — `.repro/run.lock` has a hostname / pid / age
   signature that does not match the live process. The lock is
   archived as `run.lock.stale.<ts>` and a state-consistency check
   is run before a fresh lock is acquired.
5. **Recovery never re-executes PASS tasks** — verified by
   `test_recovery_skips_passed_tasks`.

## Test functions

| Recovery scenario | Test | Status |
|---|---|---|
| Recovery skips PASS | `test_recovery_skips_passed_tasks` | PASS |
| Interrupted recovery | `test_integ_11_interrupted_recovery` | PASS |
| Plan hash changed | `test_integ_12_plan_hash_changed` | PASS |
| Corrupted state | `test_integ_13_corrupted_state` | PASS |
| Corrupted checkpoint | `test_integ_14_corrupted_checkpoint` | PASS |
| Stale lock cleared | `test_integ_10_stale_lock` | PASS |

## Operational notes

- `plan_change_report.md` is written to
  `.repro/execution/plan_change_report.md` whenever a hash mismatch
  is detected.
- The corrupt-state archive name uses the unix timestamp at the
  moment of detection; never silently overwritten.
- Recovery does **not** re-execute tasks already marked PASS; the
  journal `.repro/execution/task_journal.jsonl` is append-only.
