# /repro-start

Unified startup entry. Forwards directly to the Python CLI — no parallel logic.

## Usage
```
/repro-start --project <PROJECT_ROOT> --plan <PLAN_PATH> [--mode strict] [--dry-run]
```

## What This Command Does
1. Locate workspace, project config, plan
2. Check historical state
3. If interrupted, prompt to resume (`reproctl resume`)
4. If new, init `.repro/execution/`
5. Run doctor
6. Emit start summary
7. Execute only the FIRST safe atomic task
8. NEVER auto-launch full training

If multiple plans exist, the Python CLI lists candidates and requires
explicit choice via `--plan`. Mode defaults to `strict`.

## Implementation
This is a thin wrapper. All behavior lives in
`scripts/reproctl.py` → `scripts/startup/cli.py`.

```bash
python scripts/reproctl.py start --project "$REPRO_PROJECT_ROOT" --plan "$REPRO_PLAN_PATH" --mode strict
```
