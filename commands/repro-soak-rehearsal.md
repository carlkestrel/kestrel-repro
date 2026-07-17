# Repro: Run Soak Rehearsal

> Run a short soak rehearsal covering all key code paths.

## Usage

```
reproctl soak plan --project . [--duration 30m]
```

## What gets tested

The rehearsal exercises the complete OSTAR pipeline at small scale:

1. **Pre-flight guard** — Git status, hardware inventory, competing process detection, heartbeat, state recovery
2. **CI smoke** — one pytest run
3. **GPU short-loop** — 5 steps forward/backward
4. **State save/restore** — write and read back a checkpoint
5. **Report generation** — generate all report files

Total time: **30 minutes** (configurable with `--duration`).

## When to use

- Before the first overnight soak
- After modifying OSTAR internals
- After upgrading dependencies
- When resuming on new hardware

## Related commands

- `Repro: Start Overnight Soak` — run the full 8-hour soak
