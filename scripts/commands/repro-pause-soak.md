# Repro: Pause Soak

> Pause a running overnight soak test (SIGSTOP).

## Usage

```
reproctl soak pause --project .
```

## Behavior

- Sends `SIGSTOP` to the soak daemon process
- State is preserved; resume picks up exactly where it left off
- All subprocesses are also paused via process group

## Related commands

- `Repro: Resume Soak` — continue from pause
- `Repro: Stop Soak` — graceful stop (SIGTERM)
