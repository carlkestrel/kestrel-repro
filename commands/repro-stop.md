# /repro-stop

Graceful stop. Saves execution state checkpoint, signals managed children
(SIGTERM only), clears the project lock. Does NOT touch other projects.

## Usage

```
/repro-stop --project <PROJECT_ROOT>
```

## What This Command Does

1. Snapshot last valid state to `.repro/execution/checkpoints/execution_state.last_valid.json`
2. SIGTERM only managed children recorded in state
3. Update execution_state.json with `stopped_at`
4. Clear `.repro/run.lock`
5. Bounded wait — bounded by the SIGTERM delivery itself

## Implementation

```bash
python scripts/reproctl.py stop --project "$REPRO_PROJECT_ROOT"
```
