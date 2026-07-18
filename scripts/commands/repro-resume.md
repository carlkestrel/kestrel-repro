# /repro-resume

Resume an interrupted project. Re-acquires the lock, validates plan_hash,
skips already-PASS tasks, and claims the next READY task only.

## Usage

```
/repro-resume --project <PROJECT_ROOT>
```

## What This Command Does

1. Reads execution_state.json
2. Verifies plan_hash matches (else emits `plan_change_report.md` and exit 8)
3. Inspects last task artifacts
4. Does NOT re-execute PASS tasks
5. Claims next READY only
6. Exit 8 on resume failure; exit 4 on duplicate start

## Implementation

```bash
python scripts/reproctl.py resume --project "$REPRO_PROJECT_ROOT"
```
