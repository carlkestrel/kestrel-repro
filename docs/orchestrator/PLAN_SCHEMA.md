# Plan Schema (`plan.yaml`)

Every orchestrator run reads a single YAML plan that completely describes the
work graph. The plan must validate against the rules below or the controller
refuses to load it.

## Top-level fields

| Field                 | Type              | Required | Notes |
|-----------------------|-------------------|----------|-------|
| `plan_id`             | string            | yes      | Stable id used in events and audit. |
| `mode`                | `strict` / `optimized` | yes  | Controls scheduler hints, not policy. |
| `automation`          | `safe-auto` (default) | no | Re-read at runtime; not stored on plan. |
| `tasks`               | array of objects  | yes      | At least one task. |
| `approvals_required`  | array of strings  | yes      | Task ids that should pause for human approval. |
| `mandatory_task_ids`  | array of strings  | yes      | Tasks that MUST end in `PASS` for COMPLETE. |
| `budgets`             | object            | yes      | Hard limits (see below). |
| `metadata`            | object            | no       | Free-form text surfaced in audits. |

### Budgets

```yaml
budgets:
  max_parallel_tasks: 4           # integer, scheduler cap
  wall_clock_minutes: 0           # 0 == unbounded (kept for forward compat)
  approval_ttl_seconds: 86400     # pending approvals expire after this long
  heartbeat_interval_seconds: 5   # reserved for future use
```

## Tasks

Each entry of `tasks` MUST contain:

| Field              | Type                  | Notes |
|--------------------|-----------------------|-------|
| `id`               | string                | Globally unique within the plan. |
| `name`             | string                | Human-readable summary. |
| `gate`             | enum                  | One of: `read_only`, `safe`, `modify_project_files`, `gpu_training`, `destructive`. |
| `deps`             | array of strings      | Task ids that must be `PASS` before this is `READY`. |
| `command`          | string or array       | Shell command (or argv) executed by the managed subprocess. |
| `timeout_min`      | number                | Wall-clock budget for the command. |
| `acceptance_tests` | array of objects      | Optional verification commands (must exit 0). |
| `retry_policy`     | object                | `{max_retries: int, delay_seconds: number, backoff_seconds: number}`. |
| `writes`           | array of strings      | Required when `gate == modify_project_files`. Must live under `.repro/`, `.execution/`, `output/`, or `reports/` in safe-auto. |
| `checkpoint`       | string                | Optional relative path the verifier may inspect on recovery. |
| `parallel_group`   | string                | Optional. Tasks sharing the same group are eligible to run concurrently when their deps are satisfied. |

### Example

```yaml
plan_id: demo-2026-07-16
mode: strict
automation: safe-auto
mandatory_task_ids: [setup, audit, train, verify]
approvals_required: [train]
budgets:
  max_parallel_tasks: 4
  wall_clock_minutes: 0
  approval_ttl_seconds: 86400
tasks:
  - id: setup
    name: Prepare sandbox
    gate: read_only
    deps: []
    command: "mkdir -p .repro/sandbox"
    timeout_min: 1
    acceptance_tests: []
    retry_policy: {max_retries: 0, delay_seconds: 0}
  - id: audit
    name: Static audit
    gate: safe
    deps: [setup]
    command: "python -c 'print(\"ok\")'"
    timeout_min: 2
    acceptance_tests:
      - {command: "test -f .repro/sandbox/.exists", timeout_sec: 5}
    retry_policy: {max_retries: 1, delay_seconds: 1}
  - id: train
    name: Mock training
    gate: gpu_training
    deps: [audit]
    command: "python -m tests.helpers.mock_train"
    timeout_min: 30
    acceptance_tests:
      - {command: "test -f output/metric.json"}
    retry_policy: {max_retries: 2, delay_seconds: 2}
  - id: verify
    name: Acceptance audit
    gate: safe
    deps: [train]
    command: "python -m tests.helpers.mock_verify"
    timeout_min: 5
    acceptance_tests: []
    retry_policy: {max_retries: 0, delay_seconds: 0}
```

## Lifecycle invariants

* The plan is loaded once and persisted into SQLite. Subsequent reloads must
  preserve already-`PASS` tasks even if the plan on disk changed.
* All deps must exist (declared in `tasks`); the controller fails fast with a
  `CycleDependencyError` when a cycle is detected.
* The combination of `mandatory_task_ids` and `approvals_required` is consulted
  by the exit logic. Missing mandatory tasks or any non-`PASS` mandatory task
  ends the run as `BLOCKED`.