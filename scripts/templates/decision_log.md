# Decision Log

A **chronological**, **append-only** record of human and agent decisions
during a reproduction project. Every entry is immutable; corrections
are recorded as a new row that references the previous one.

This file is the single source of truth for *why* a project is in its
current state. `scripts/reproctl.py` writes rows via `_append_decision_log()`
when modes are switched or major checkpoints are approved.

---

## Header (do not delete)

| Field | Meaning |
|---|---|
| **id** | Monotonically increasing row id (`D000`, `D001`, ...). Never reuse. |
| **ts** | ISO-8601 timestamp (UTC) when the decision was made. |
| **actor** | `human` \| `agent` \| `cursor_cmd` \| `external_reviewer`. |
| **phase** | Plan phase at decision time: `P0_preparation`, `P1_mode_contract`, ... |
| **task_id** | Granular task id (e.g. `P1_T03`), or `—` if non-task event. |
| **decision_type** | `mode_switch` \| `gate_approval` \| `scope_change` \| `risk_override` \| `checkpoint` \| `rollback` \| `note`. |
| **before / after** | Compact diff of the changed value (state path or flag). |
| **reason** | One or two sentences of justification; cite evidence by path. |
| **links** | Comma-separated paths to evidence (`evidence/P1_T01_state_diff.json`), or `—`. |

---

## Rows

<!--
DO NOT EDIT THIS SECTION BY HAND EXCEPT TO ADD NEW ROWS.
Always append; never delete or reorder existing rows.
Row format (Markdown pipe table, one row per decision):

| D{id} | {ts} | {actor} | {phase} | {task_id} | {decision_type} | {before} → {after} | {reason} | {links} |
-->

| id | ts | actor | phase | task_id | decision_type | before → after | reason | links |
|---|---|---|---|---|---|---|---|---|
| D000 | 2026-07-15T21:51:30+08:00 | agent | P1_mode_contract | P1_T01 | note | — → project_mode='reproduce' in default state | Phase 1 baseline established; reproduce mode is the project default per Plan §4 | evidence/P1_T01_state_diff.json |