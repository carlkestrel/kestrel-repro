---
description: Watch, check, or diagnose an in-progress training run via scripts/training_monitor.py.
---

# /repro-monitor

> **Three modes**: `--check` (one snapshot), `--watch` (continuous), `--diagnose`
> (interpret a finished run). All three read the run's log file + GPU/process
> state and produce a 15-metric + 9-status snapshot.

## Usage

```
/repro-monitor --run-id r-001 check                              # one snapshot
/repro-monitor --run-id r-001 --interval 10 watch                 # continuous
/repro-monitor --run-id r-001 --log experiments/r-001/logs/train.log diagnose
```

## What this command does

It is a thin wrapper around `scripts/training_monitor.py`:

```
python scripts/training_monitor.py check --run-id r-001 --log <log_path> --telemetry-dir <dir>
python scripts/training_monitor.py watch --run-id r-001 --log <log_path> --telemetry-dir <dir> --interval 10
```

## Three modes

| Mode | Reads | Writes | Use when |
|---|---|---|---|
| **check** | one sample of GPU / process / log state | one JSON line on stdout | before a decision ("is it OK to launch?") |
| **watch** | continuous samples every `--interval` seconds | `experiments/<run_id>/TELEMETRY.jsonl` per sample + `TELEMETRY_STAGES.jsonl` per stage | during a long run |
| **diagnose** | full log scan + last 1000 TELEMETRY rows | markdown summary on stdout | after a failure |

## Output schema

Each snapshot has 15 metrics (P4_T01):

| # | Metric | Source |
|---|---|---|
| 1 | `gpu_util_pct` | `nvidia-smi` |
| 2 | `gpu_mem_used_mb` | `nvidia-smi` |
| 3 | `gpu_mem_peak_mb` | `nvidia-smi` memory.total (snapshot ceiling) |
| 4 | `gpu_temp_c` | `nvidia-smi` |
| 5 | `cpu_pct` | `psutil` |
| 6 | `ram_used_mb` | `psutil` |
| 7 | `disk_used_pct` | `psutil` |
| 8 | `step_time_s` | caller (training loop) |
| 9 | `loss` | caller |
| 10 | `grad_norm` | caller |
| 11 | `has_nan` | derived from loss/grad_norm |
| 12 | `has_oom` | derived from log keyword scan |
| 13 | `last_ckpt_age_s` | mtime of newest `checkpoints/*.pth` |
| 14 | `class_distribution_entropy` | caller-supplied class histogram |
| 15 | `log_keyword_hits` | regex scan of last 200 log lines |

The status is one of **9** values: `OK`, `STALLED`, `DIVERGED`, `OOM`,
`NAN`, `CKPT_STUCK`, `CLASS_COLLAPSE`, `OVERHEAT`, `UNKNOWN`.

## Status priority

If multiple rules fire, the most severe wins (priority order, top = highest):

`NAN > OOM > OVERHEAT > DIVERGED > CLASS_COLLAPSE > CKPT_STUCK > STALLED > UNKNOWN`

`OK` is the default when nothing fires.

## Decision-log integration

Any non-OK snapshot from `diagnose` is automatically appended to
`DECISION_LOG.md` as a `risk_override` row if the agent decides to proceed.
The agent must not silently swallow a non-OK status.

## Examples

```
$ /repro-monitor --run-id r-001 check
{"ts": "2026-07-15T22:30:00Z", "status": "OK", "gpu_util_pct": 87.3, "loss": 0.42, ...}

$ /repro-monitor --run-id r-001 watch --interval 30
...continues until SIGINT, writes TELEMETRY.jsonl every 30s
```

## Failure modes

- `nvidia-smi not found` → GPU fields default to 0; classifier may mis-fire
  on STALLED. Set `MONITOR_NO_GPU=1` to suppress GPU sampling entirely.
- `log path missing` → keyword hits default to 0; classifier relies on
  caller-supplied `loss` / `grad_norm` instead.
- `permission denied writing TELEMETRY.jsonl` → check ownership of
  `experiments/<run_id>/`.