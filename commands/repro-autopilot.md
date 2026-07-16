# /repro-autopilot

NORA-style continuous autopilot execution for paper reproduction. Runs the full task graph until blocked or complete.

## Usage
```
/repro-autopilot [action] [options]

Actions:
  run         - Run continuous autopilot until blocked or complete
  status      - Show autopilot status
  recover     - Recover from interrupted state
  pause       - Pause the autopilot
  stop        - Stop the autopilot
  continue    - Continue a paused autopilot
  takeover    - Analyze and takeover existing project
  l0l3        - Run L0-L3 verification loop
  report      - Generate reproduction report

Options:
  --project <PATH>     - Project root (default: current workspace)
  --plan <PATH>        - Plan file path
  --until <CONDITION>  - Run until: blocked, complete, blocked-or-complete
  --automation <MODE>  - Automation: safe-auto, auto, manual
  --resume             - Resume from interrupted state
  --skip-doctor        - Skip preflight checks
```

## What This Command Does

### run
1. Runs preflight doctor checks
2. Loads task graph from plan
3. Starts continuous execution loop
4. Automatically recovers from interruptions
5. Monitors GPU, memory, and training health
6. Collects evidence for each task
7. Runs verification after each task
8. Continues until blocked, complete, or manually stopped

### l0l3
Runs the automated L0-L3 verification loop:
- **L0**: Static smoke test (import, config, paths)
- **L1**: Real single batch (forward/backward/eval)
- **L2**: Tiny overfit (small dataset, verify memorization)
- **L3**: Short evaluation (checkpoint resume, evaluation pipeline)

Each stage must pass before the next begins.

## Implementation

```bash
# Start autopilot
python scripts/autopilot.py run --project "$REPRO_PROJECT_ROOT" --until blocked-or-complete

# L0-L3 loop
python scripts/l0_l3_loop.py --project "$REPRO_PROJECT_ROOT"

# Status check
python scripts/autopilot.py status --project "$REPRO_PROJECT_ROOT"

# Recovery
python scripts/autopilot.py recover --project "$REPRO_PROJECT_ROOT"
```

## Examples

```bash
# Full autopilot run
/repro-autopilot run --project . --until blocked-or-complete

# L0-L3 verification
/repro-autopilot l0l3 --project .

# Status check
/repro-autopilot status --project .

# Recover from interruption
/repro-autopilot recover --project .

# Generate report
/repro-autopilot report --project .
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (COMPLETE, PAUSED, STOPPED) |
| 3 | Doctor check failed |
| 7 | BLOCKED |
| 8 | Waiting approval |
| 10 | Internal error |

## Risk Levels

| Level | Description | Behavior |
|-------|-------------|----------|
| R0 | Read-only checks | Automatic |
| R1 | Project internal | Automatic with logging |
| R2 | Within budget | Automatic |
| R3 | Full training | Pre-authorized or approval |
| R4 | Destructive | Always requires approval |
