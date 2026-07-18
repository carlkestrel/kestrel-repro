# /repro-doctor

Run preflight checks without mutating state. Thin wrapper over the Python CLI.

## Usage

```
/repro-doctor --project <PROJECT_ROOT> [--plan <PLAN_PATH>]
```

## What This Command Does

- Checks plugin structure, manifest, Python, deps, config, git, plan, task-graph,
  CPU/RAM/GPU, driver+CUDA, torch, disk, R/W, network, leftover procs, state file,
  checkpoint, security risk.
- Status enum: PASS / WARNING / FAIL / BLOCKED / UNSUPPORTED.
- Mandatory FAIL blocks `start`. Exit code 3 on doctor FAIL.

## Implementation

```bash
python scripts/reproctl.py doctor --project "$REPRO_PROJECT_ROOT" --plan "$REPRO_PLAN_PATH"
```
