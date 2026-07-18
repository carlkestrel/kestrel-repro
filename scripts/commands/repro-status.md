# /repro-status

Show project state, lock info, plan hash, and last completed task. Read-only.

## Usage

```
/repro-status --project <PROJECT_ROOT>
```

## What This Command Does

- Prints JSON: project root, plugin version, execution state, lock info, last check time.

## Implementation

```bash
python scripts/reproctl.py status --project "$REPRO_PROJECT_ROOT"
```
