# Control Flags

> **Canonical defaults** for `scripts/reproctl.py`. Each flag has a default,
> a value type, and the gate / behavior it controls. A mode switch may
> temporarily override a flag, but every override must be recorded as a
> `risk_override` row in `DECISION_LOG.md`.

## Defaults

| Flag | Default | Type | Meaning |
|---|---|---|---|
| `HUMAN_CHECKPOINT` | `true` | bool | `plan → reproduce` and `reproduce → evolve` transitions require a prior human-approval decision row. |
| `AUTO_RETRY` | `false` | bool | If `true`, transient failures auto-retry up to `retry_limit`. Keep `false` unless you trust the failure classifier. |
| `ALLOW_NETWORK` | `true` | bool | If `false`, any download, clone, or pip install is blocked (offline mode). |
| `REQUIRE_GIT_PIN` | `true` | bool | Reject `main` / `master`; upstream repos must be pinned to a commit SHA. |
| `TOLERANCE_MIOU` | `0.5` | float | Absolute percentage points tolerance for paper-vs-reproduced parity. |
| `WIP_LIMIT` | `1` | int | Max simultaneously `IN_PROGRESS` tasks per plan. |
| `EVIDENCE_REQUIRED` | `true` | bool | A task cannot be marked `PASS` without an evidence JSON in `.execution/evidence/`. |

## Resolution order

When multiple sources exist, resolution order is:

1. CLI flag (`reproctl set flag=value ...`)
2. `.repro/repro_audit/STATE.json` `flags` block
3. This template's defaults

## Gate mapping

| Gate | Condition |
|---|---|
| `human_checkpoint` | `HUMAN_CHECKPOINT=false` *or* a prior `gate_approval` row referencing the destination mode exists |
| `git_pin` | `REQUIRE_GIT_PIN=false` *or* `reproctl check git-pin` returns PASS |
| `evidence_present` | `EVIDENCE_REQUIRED=false` *or* evidence JSON exists for the task being closed |

## Example override

```python
# scripts/reproctl.py (illustrative; do not edit at runtime)
set_control_flag("AUTO_RETRY", True, reason="network blips expected in CI",
                 decision_type="risk_override", task_id="P11_T03")
```

That call writes a `risk_override` row to `DECISION_LOG.md`. To roll back,
set the flag back to `false` and record another row.