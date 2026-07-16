# Soak Test Report

> Config ID: (candidate config)
> Duration: (requested) → (actual)
> Timestamp: (ISO-8601)

## Summary

| Check | Status | Detail |
|---|---|---|
| Memory leak (no growth) | OK / FAIL | XX MB growth over YY steps |
| Step time stability | OK / WARN / FAIL | p95/std = X.XX |
| Loss validity | OK / FAIL | final = XX, trend = |
| OOM events | 0 | |
| NaN/Inf | 0 | |
| Data process leaks | 0 | |
| Orphan processes | 0 | |
| Temperature stable | OK / WARN | max = XX°C |
| Thermal throttling | 0 | |
| Checkpoint save | OK / FAIL | |
| Checkpoint resume | OK / FAIL | |
| **Overall verdict** | **PASS / FAIL** | |

## Step Time Over Time

| Step | Step time (s) | GPU mem (MB) | Temp (°C) | Loss | Notes |
|---|---|---|---|---|---|
| 0 | | | | | |
| 100 | | | | | |
| 200 | | | | | |
| ... | | | | | |

## Memory Trend

| Metric | Value |
|---|---|
| Initial GPU memory | XX MB |
| Final GPU memory | XX MB |
| Growth | XX MB |
| Growth rate | XX MB/100steps |
| Leaking? | YES / NO |

## Temperature Trend

| Metric | Value |
|---|---|
| Initial temp | XX°C |
| Max temp | XX°C |
| Final temp | XX°C |
| Thermal throttling events | 0 |

## Checkpoint Integrity

| Check | Status |
|---|---|
| Checkpoint saved at step X | OK |
| File size > 0 | OK |
| SHA256 matches log | OK |
| Resumed state matches pre-save | OK |

## Decision

```
[soak] memory_leak          : OK (XX MB growth < threshold)
[soak] step_time_stable      : OK (p95/std = X.XX < 1.5)
[soak] loss_valid           : OK (no NaN/Inf)
[soak] no_oom                : OK (0 OOMs)
[soak] temperature_stable    : OK (max=XX°C)
[soak] no_throttle           : OK (0 events)
[soak] checkpoint_save        : OK
[soak] checkpoint_resume      : OK
[soak] verdict               : PASS
```

## Source

`performance/soak_test_report.md`