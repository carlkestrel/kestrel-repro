# Repro: Start Overnight Soak

> Start the overnight soak test (TEST → REPRODUCE → REPAIR → RESUME loop).

## Usage

```
reproctl soak start --project . \
  --duration 8h \
  --auto-repair safe \
  [--end-time 06:00] \
  [--timezone Asia/Singapore] \
  [--max-repairs 10] \
  [--gpu-temperature-limit 87]
```

## Default schedule

- **Timezone**: Asia/Singapore
- **Duration**: 8 hours
- **Auto-repair level**: `safe`
- **Max repairs**: 10
- **GPU temperature limit**: 87°C (warn at 82°C)

## What happens

1. **Pre-flight guard** runs first — blocks start if checks fail
2. **Soak loop** runs continuously until:
   - Duration ends (default: 8h)
   - Max repairs reached (default: 10)
   - Hardware safety limit exceeded (GPU temp, disk space)
   - P0 unresolvable issue detected
   - Same bug fails 3 consecutive repair attempts
3. **Morning reports** generated automatically in `soak/reports/`

## Anti-infinite-loop guards

- Same bug: max 3 repair attempts, then BLOCKED
- Consecutive crashes: max 3, then abort
- Max repairs: 10 total, then stop

## Auto-repair levels

| Level | Behavior |
|---|---|
| `none` | Detect and report only, no fixes |
| `safe` | Fix known-safe categories (CODE, CONFIG, RESOURCE, STATE, CLI, CHECKPOINT, FIXTURE, METRIC, ENV) |
| `full` | Attempt fix for all non-BLOCKED classes |

### BLOCKED (never auto-repair)
`PROTOCOL`, `DATA`, `MODEL`, `LOSS`, `SCHEDULER`

## Reports

After completion, reports are in `soak/reports/`:
- `overnight_summary.md` / `.html`
- `failure_timeline.csv`
- `repair_history.csv`
- `ci_reliability.csv`
- `resource_trends.csv`
- `unresolved_issues.md`
- `final_gate.json`

## Related commands

- `Repro: Plan Overnight Soak` — run pre-flight rehearsal first
- `Repro: Pause Soak` — pause the running soak
- `Repro: View Soak Status` — check progress
- `Repro: Stop Soak` — graceful stop
- `Repro: Open Morning Report` — open the report
