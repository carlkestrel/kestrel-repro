---
description: Resume a project from a templates/handoff.json snapshot after a context boundary.
---

# /repro-handoff

> **Resumes** a project whose execution was interrupted (chat ended, agent
> crashed, machine restarted). Reads `handoff.json` written by the previous
> session, validates consistency against `.execution/execution_state.json`,
> and re-launches the run from the documented `next_step`.

## Usage

```
/repro-handoff                                  # auto-detect handoff.json in cwd
/repro-handoff --path .repro/handoff.json       # explicit path
/repro-handoff --check                          # dry-run, print what would be done
/repro-handoff help                             # this file
```

## Recovery flow (5 steps)

| Step | Reads | Validates | Action |
|---|---|---|---|
| **1. Locate handoff** | `--path` or auto-discover `.repro/handoff.json` | file exists + parses as JSON | abort with `handoff.json missing` |
| **2. Schema check** | `handoff.json` | all 12 required fields present | abort with `missing field: <name>` |
| **3. State consistency** | `handoff.json` + `.execution/execution_state.json` | `project_mode` and `current_phase` agree | abort with `state drift: handoff.X != state.X` |
| **4. Required files** | `recovery_required_files[]` | every path exists | abort with `missing required file: <path>` |
| **5. Resume** | `next_step` + `run_command` | none (best-effort) | call `reproctl.py launch` (or restart the documented command) + write a decision row |

## Pre-conditions

- A previous session wrote `handoff.json` (typically on `Ctrl-C`, end of
  chat, or via `reproctl.py handoff`).
- `.execution/execution_state.json` is the same file the previous session
  committed (i.e., git-clean or git-committed).
- The training process from the previous run is **not** still running. If
  `handoff.process_id` resolves to a live PID, the recovery aborts with
  `previous process still alive, refuse to double-launch`.

## Output

```
[repro-handoff] reading .repro/handoff.json ............ OK (12/12 fields)
[repro-handoff] state consistency .................... OK (mode=reproduce, phase=P4_monitor)
[repro-handoff] required files (3) ................... OK
[repro-handoff] resuming: "Resume from epoch 50, ..." . OK (reproctl launch)
[repro-handoff] decision = D__ → DECISION_LOG.md
```

## Failure modes

- `state drift` → `handoff.json` was written by an older plan or different
  branch. Re-run the previous step manually before `/repro-handoff`.
- `previous process still alive` → `kill -9 <handoff.process_id>` (or
  `reproctl kill <run_id>`) before retrying.
- `missing required file` → the recovery list is a contract; either
  restore the file or amend `next_step` and start a fresh run.

## Implementation

`reproctl.py` implements this as `reproctl.py handoff [--path PATH]
[--check]`. The command appends a `checkpoint` row to `DECISION_LOG.md`
after step 5 succeeds.