# dl-paper-repro Unified Startup System

> One unified, verifiable startup method. All entry points (Cursor commands
> and the shell CLI) call the **same** Python module. No triple maintenance.

---

## 1. The 4 canonical commands

```bash
reproctl doctor --project <PROJECT_ROOT>
reproctl start  --project <PROJECT_ROOT> --plan <PLAN_PATH> --mode strict
reproctl resume --project <PROJECT_ROOT>
reproctl status --project <PROJECT_ROOT>
reproctl stop   --project <PROJECT_ROOT>
```

Auxiliary (used less often, still part of the unified system):

```bash
reproctl verify  --project <PROJECT_ROOT>   # evidence-chain check
reproctl version                              # plugin + CLI version
```

The same five commands are exposed to Cursor as thin wrappers under
`commands/`:

| Cursor command | Forwards to                            |
|---|---|
| `/repro-doctor` | `reproctl doctor --project …`          |
| `/repro-start`  | `reproctl start  --project … --plan …` |
| `/repro-resume` | `reproctl resume --project …`          |
| `/repro-status` | `reproctl status --project …`          |
| `/repro-stop`   | `reproctl stop   --project …`          |
| `/repro-verify` | `reproctl verify --project …`          |

Each wrapper file is ≤ 30 lines and contains **no parallel logic** — it
literally runs the Python CLI.

---

## 2. Architecture

```
┌───────────────────────────────────────────────────────────────┐
│ Cursor /repro-*    OR    shell `reproctl …`                   │
└──────────┬────────────────────────────────┬───────────────────┘
           │                                │
           └──────────► scripts/reproctl.py ◄──── scripts/reproctl (shebang)
                          │
                ┌─────────┴─────────┐
                │ dispatcher        │  new subcommands go here:
                │ (additive)        │  start | doctor | status | resume |
                │                   │  stop | verify | version
                ▼                   ▼
   legacy commands          scripts/startup/cli.py
   (init, can-launch, …)            │
                                    ├── state_machine.py
                                    ├── doctor.py
                                    ├── plan_validate.py
                                    ├── lock.py
                                    ├── recovery.py
                                    ├── stop.py
                                    ├── config.py
                                    ├── log_setup.py
                                    └── secrets_redactor.py
```

The legacy subcommands (`init`, `status` (old), `can-launch`, `launch`,
`run-short-loop`, `report`, `update-gate`, `record-experiment`,
`update-experiment`, `get-experiments`, `human-checkpoint`,
`check-principles`, `help`) are **unchanged** — the dispatcher in
`scripts/reproctl.py` only intercepts the seven new subcommands and hands
the rest off to the legacy implementation.

`status` and `verify` exist in both forms; the **new** implementation
(preferred) wins because the dispatcher fires first.

---

## 3. State machine

```
BOOTSTRAP → DISCOVER → PREFLIGHT → STATE_CHECK → LOCK
           → PLAN_VALIDATE → READY → EXECUTE_NEXT
```

Each stage is a function in `scripts/startup/state_machine.py`. Any
failure exits cleanly with the appropriate exit code; nothing is
silently skipped.

---

## 4. Project exec layout (auto-created)

```
<PROJECT_ROOT>/.repro/
├── config.yaml
├── startup/
│   ├── startup_state.json
│   ├── startup.log
│   ├── doctor_report.json
│   └── startup_summary.md
├── execution/
│   ├── plan_snapshot.md
│   ├── task_graph.yaml
│   ├── execution_state.json
│   ├── task_journal.jsonl
│   ├── requirement_traceability.csv
│   ├── checkpoints/
│   ├── heartbeats/
│   └── evidence/
├── performance/
├── repair/
└── reports/
```

The plugin never writes raw data or source code into `.repro/`.

---

## 5. Configuration priority

Highest priority first:

1. CLI flags (`--mode`, `--plan`, `--project`, `--expected-cuda`,
   `--dry-run`)
2. `<PROJECT>/.repro/config.yaml`
3. `<PROJECT>/repro.yaml`
4. Plugin defaults (built-in)
5. Auto-detection

Environment variables (lower than CLI but above YAML):

- `REPRO_PROJECT_ROOT`
- `REPRO_PLAN_PATH`
- `REPRO_MODE`
- `REPRO_CONFIG`
- `REPRO_LOG_LEVEL`

No hardcoded user paths, GPU IDs, or dataset locations anywhere in the
plugin defaults. (`tests/test_no_hardcoded_paths_in_new_code` enforces
this.)

---

## 6. Single-instance lock

`<PROJECT>/.repro/run.lock` carries:

| Field | Purpose |
|---|---|
| `process_id` | PID of the live reproctl process |
| `hostname`   | host of the live process |
| `start_time` | ISO-8601 of lock creation |
| `project_root` | absolute path to the project |
| `plan_hash` | SHA-256 of the plan file |
| `command` | which subcommand acquired the lock |
| `heartbeat` | ISO-8601 of last update |
| `plugin_version` | `0.2.0` |

Lock state transitions:

| Current state | Next action |
|---|---|
| missing  | create the lock |
| valid    | reject duplicate start (exit 4) |
| stale    | copy aside as `run.lock.stale.<ts>`, run state-consistency check, then clear and re-acquire |

A lock is stale when any of these is true:

- `process_id` is no longer alive
- `hostname` does not match the current host
- `start_time` is older than 6 hours, **or** `heartbeat` is older than 6 hours

Stale locks are NEVER silently deleted; the file is always preserved as
`run.lock.stale.<unix-ts>`.

---

## 7. Exit codes

| Code | Meaning |
|---|---|
| 0  | success |
| 2  | bad args / config |
| 3  | doctor FAIL |
| 4  | already running (duplicate lock) |
| 5  | invalid plan |
| 6  | task failed |
| 7  | task blocked |
| 8  | resume failed (corrupt state, plan-hash mismatch, …) |
| 9  | security policy block |
| 10 | internal error |

The codes are identical whether the call originates from a Cursor
`/repro-*` command or from the shell.

---

## 8. Doctor checks (preflight)

| Check | What it verifies | FAIL blocks start? |
|---|---|---|
| `plugin_manifest` | `.cursor-plugin/plugin.json` parses | yes |
| `python`            | interpreter version recorded    | no |
| `deps`              | pyyaml / torch if needed        | no (WARNING) |
| `config_format`     | `<PROJECT>/.repro/config.yaml` parses | yes |
| `git`               | project is a git repo           | no (WARNING) |
| `plan_exists`       | the plan file exists            | yes |
| `task_graph`        | plan's task deps resolve        | yes |
| `disk_space`        | ≥ 1 GB free (or `REPRO_FAKE_DISK_FREE` override) | yes |
| `rw`                | project is writable             | yes |
| `gpu`               | torch.cuda available            | no (WARNING) |
| `cuda_match`        | CUDA version matches `--expected-cuda` if given | yes |
| `driver`            | `nvidia-smi` works              | no (WARNING) |
| `torch`             | torch importable                | no (WARNING) |
| `security`          | no credential-shaped strings in source tree | no (WARNING) |
| `leftover_procs`    | no orphan reproctl processes    | no (WARNING) |
| `state_file`        | execution_state.json parses     | no (WARNING; recovery handles it) |
| `checkpoint`        | no corrupt checkpoint files     | no (WARNING) |

---

## 9. Output format (success)

```
Repro Agent Ready
Project: <abs path>
Plan:    <abs path>
Mode:    strict
Plugin Version: 0.2.0
Git Commit: <sha or unknown>
GPU: <none | Nx <model>>
Execution State: missing | present
Last Completed Task: <id> | (none)
Next Task: <id>
Log: <abs path to startup.log>
Status Command: reproctl status --project <abs path>
Stop Command:   reproctl stop   --project <abs path>
```

No big raw dumps; everything is one labelled line per fact.

## 10. Output format (failure)

```
Repro Agent FAILED
  Stage:        PREFLIGHT
  Error Number: 3
  Reason:       1 mandatory doctor check(s) failed: disk_space
  Related File: <abs path to plan>
  Suggested Fix: free at least 1 GB before starting
  Full Log:     <abs path to startup.log>
```

---

## 11. What `start` does NOT do (guarantees)

- Does NOT install unknown dependencies
- Does NOT run scripts from unfamiliar repos
- Does NOT download large data
- Does NOT launch full training
- Does NOT edit paper config
- Does NOT delete user data
- Does NOT `git commit` / `git push`
- Does NOT change GPU power / clock / fan
- Does NOT delete old state
- Does NOT bypass doctor FAIL
- Does NOT run two instances of the same project
- Does NOT silently treat WARNING as PASS

---

## 12. Tests

```bash
cd <plugin-root>
python -m pytest tests/test_startup.py -q
```

53 tests cover all 20 mandatory requirements plus module-level unit
tests. The full pytest output and the four spec artifacts are in
`audits/startup_v0.2.0/`:

- `startup_test_report.md`
- `command_matrix.csv`
- `recovery_test_report.md`
- `installation_checklist.md`

Regenerate them any time with:

```bash
python scripts/startup/generate_artifacts.py
```

---

## 13. Dev notes

- The startup package is fully self-contained under
  `scripts/startup/`. Each module imports only from its siblings and
  from the Python stdlib + `pyyaml`.
- The package is imported as `startup.*`. The shim in
  `scripts/reproctl.py` adds `scripts/` to `sys.path` before importing.
- All credentials in logs are redacted by
  `scripts/startup/secrets_redactor.py`; a logging filter is attached
  to every logger in `log_setup.get_logger`.
- The plugin's own `.repro/state.json`, `.execution/execution_state.json`,
  and `.execution/task_graph.yaml` (the existing NORA enhancement
  artifacts) are NOT touched by the startup system. The startup system
  writes to `<PROJECT>/.repro/...`, where `<PROJECT>` is whatever the
  user passes via `--project`.
