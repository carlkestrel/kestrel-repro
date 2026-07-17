# Repro: Plan Overnight Soak

> Run a 30-minute pre-flight rehearsal before starting an overnight soak test.

## Usage

```
reproctl soak plan --project . [--duration 30m]
```

## What it does

1. Runs the full pre-flight **guard** (Git status, hardware inventory, competing process check, heartbeat mechanism, state recovery)
2. Writes `soak/guard_result.json`
3. Executes a 30-minute **rehearsal** covering:
   - One CI smoke run
   - One GPU short-loop (5 steps)
   - State save/restore cycle
   - Report generation dry-run
4. Reports each check's pass/fail status
5. If all pass → prints plan summary and instructions to start the full soak
6. If any fail → exits with code 3 and explains what to fix

## Flags

| Flag | Default | Description |
|---|---|---|
| `--project` | `.` | Project root |
| `--duration` | `30m` | Rehearsal duration |

## Exit codes

- `0` — Rehearsal passed, plan ready
- `3` — Guard failed (fix before continuing)
- `5` — Rehearsal failed

## Related commands

- `Repro: Start Overnight Soak` — begin the full 8-hour soak
- `Repro: View Soak Status` — check current soak status
- `Repro: Open Morning Report` — open the generated report
