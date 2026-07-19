# Repro: Stop Soak

> Stop the overnight soak test gracefully (SIGTERM then SIGKILL).

## Usage

```
reproctl soak stop --project .
```

## Behavior

1. Sends `SIGTERM` to the soak daemon
2. Waits up to 10 seconds for graceful exit
3. Falls back to `SIGKILL` if still running
4. Clears the PID file
5. Preserves all state and evidence

## Related commands

- `Repro: Pause Soak` — pause without stopping
- `Repro: View Soak Status` — check current state
