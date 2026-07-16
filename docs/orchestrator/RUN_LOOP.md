# Run Loop & Control Surface (`RUN_LOOP.md`)

The orchestrator is a single Python process that owns the SQLite state store,
the append-only event journal, and the subprocess arena. It runs **until one
of five exit states** is reached and is otherwise persistent across process
restarts.

## Five exit states

| State               | Meaning | Code |
|---------------------|---------|------|
| `COMPLETE`          | All mandatory tasks `PASS` and no executable tasks remain. | 0 |
| `BLOCKED`           | A mandatory task is not `PASS`, a task exhausted retries, or a dependency deadlock was detected. | 7 |
| `WAITING_APPROVAL`  | At least one task is `WAITING_APPROVAL`; no executable tasks remain. | 0 |
| `PAUSED`            | Operator paused the controller. | 0 |
| `STOPPED`           | Operator stopped the controller (running children are terminated). | 0 |

The controller never exits while there is a `READY`, `APPROVED`, `RUNNING`,
`VERIFYING`, `RETRY_WAIT`, or `WAITING_APPROVAL` task in the store.

## Tick loop

Each iteration is exactly:

1. **Heartbeat** the controller PID into `.repro/execution/controller.heartbeat`.
2. **Cleanup expired approvals** (`approval_ttl_seconds` default 24h).
3. **Honor control state** (`PAUSED`/`STOPPED`) — these exit immediately.
4. **Poll running processes** — finished children transition to `VERIFYING`
   (exit 0) or `FAIL` (any non-zero exit or timeout).
5. **Run verifications** — every `acceptance_tests` entry is executed via
   `ProcessManager.run`; only an all-zero exit set transitions the task to
   `PASS`.
6. **Refresh the scheduler** — promote `RETRY_WAIT` whose `retry_at` has passed
   and unblock `PENDING` tasks whose deps are all `PASS`.
7. **Schedule** — select up to `max_parallel_tasks - active` candidates,
   evaluate them with `PolicyEngine`, and either launch them, request an
   approval, or reject them.
8. **Compute terminal result** — if no executable task remains and no
   `BLOCKED` task is left, exit `COMPLETE`; otherwise emit one of the other
   exit states.
9. **Wait** — if no progress was made, sleep for the minimum of the next
   `retry_at` and the configured poll interval (default 50 ms).

The tick loop is event-driven via SQLite polling; no busy-waiting.

## Subprocess arena

* All tasks are spawned via `ProcessManager.start` with `start_new_session=True`
  (POSIX setsid equivalent) and detached stdio captured to
  `.repro/execution/logs/<task>.attempt-<n>.log`.
* Killing the controller **does not** kill running children. They can be
  recovered by the next `reproctl run --resume`.
* `Watchdog` enforces `timeout_min`, sends `SIGTERM` first and `SIGKILL`
  after `grace_seconds`, and records the event.

## Safe-auto boundary

* `safe-auto` re-reads `automation_policy.yaml` before every decision.
* `gate: modify_project_files` is `REQUIRE_APPROVAL` unless every `writes`
  entry lives under `.repro/`, `.execution/`, `output/`, or `reports/`.
* Commands that touch `src/`, `configs/`, `scripts/`, `README.md`, or paper
  assets are automatically `REJECT` (the task transitions to `REJECTED` and
  the run continues).

## State durability

* SQLite (`state.sqlite3`) is the single source of truth — JSON / YAML / CSV
  snapshots are derived and refreshed at every controller exit.
* Every commit is followed by `fsync` and a mirror append into
  `.repro/execution/events.jsonl`. The mirror is consulted by `RecoveryManager`
  to repair torn rows after a crash.

## User control surface (reproctl)

| Command                                 | Effect |
|-----------------------------------------|--------|
| `reproctl run --project <P> --plan <Y>` | Start the loop in foreground; exit when blocked-or-complete. |
| `reproctl run … --resume`               | Re-load the plan, run recovery, then start. |
| `reproctl pause --project <P>`          | Stop on the next tick; running children keep going. |
| `reproctl continue --project <P>`       | Resume from `PAUSED`. |
| `reproctl stop --project <P>`           | Set `STOPPED` and terminate all running children. |
| `reproctl status --project <P>`         | Print the in-memory status summary (counts, tasks, pending approvals, heartbeat). |
| `reproctl next --project <P> --plan <Y>`| Show the next task the scheduler would pick. |
| `reproctl approve <apr_…|task> --project <P>` | Approve a `WAITING_APPROVAL` task. |
| `reproctl reject <apr_…|task> --project <P>`  | Reject a `WAITING_APPROVAL` task. |
| `reproctl events --project <P>`         | Dump the event log (JSON). |
| `reproctl daemon start --project <P> --plan <Y>` | Detach via `nohup` + `setsid`; writes `controller.pid`. |
| `reproctl daemon status --project <P>`  | Inspect pid + heartbeat. |
| `reproctl daemon stop --project <P>`    | Send `SIGTERM`, then `SIGKILL` after 5 s. |

The daemon mode uses `nohup` + `start_new_session` + an explicit PID file —
no systemd / tmux dependency.

## Recovery guarantees

When the controller restarts it:

1. Repairs torn journal rows (writes missing events to the JSONL mirror).
2. Walks every `RUNNING` task — alive PIDs continue running; dead ones move
   to `VERIFYING` and re-execute their `acceptance_tests`.
3. Surfaces a summary in `CONTROLLER_EXIT.recovery` so the operator can see
   what happened.
4. Resumes from the persisted `control_state`. If the previous exit was
   `STOPPED`, the next `run` call must clear it before resuming.