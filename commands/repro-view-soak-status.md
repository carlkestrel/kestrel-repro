# Repro: View Soak Status

> Check the current status of an overnight soak test.

## Usage

```
reproctl soak status --project .
```

## Output includes

- **Process**: alive/dead PID
- **Status**: INIT / RUNNING / PAUSED / COMPLETED / FAILED
- **Verdict**: SOAK_VERIFIED / REPAIRED_BUT_NOT_SOAK_VERIFIED / FAILED_WITH_UNRESOLVED_BUGS / etc.
- **Heartbeat**: age in seconds (warn if >60s)
- **Hardware**: GPU temp, GPU memory, CPU RAM, disk free
- **Bug count**: active and total
- **CI reliability**: per-suite pass/fail/flaky counts

## Related commands

- `Repro: Start Overnight Soak` — begin a soak
- `Repro: Open Morning Report` — view the report
