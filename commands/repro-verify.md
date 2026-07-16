# /repro-verify

Verify the startup evidence chain: startup_state.json, doctor_report.json,
execution_state.json, plan_hash. Pure-read; safe to run any time.

## Usage

```
/repro-verify --project <PROJECT_ROOT>
```

## What This Command Does

1. Validates `.repro/startup/startup_state.json`
2. Validates `.repro/startup/doctor_report.json`
3. Validates `.repro/execution/execution_state.json`
4. Confirms plan_hash matches between plan file and recorded state

Exit 0 if all PASS; exit 8 on FAIL.

## Implementation

```bash
python scripts/reproctl.py verify --project "$REPRO_PROJECT_ROOT"
```
