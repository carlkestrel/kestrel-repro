# Soak Test Report

> Config ID: `test-candidate`
> Requested: 10s → Actual: 10s
> Timestamp: 2026-07-18T13:37:50.439738+00:00

## Summary

| Check | Status | Detail |
|---|---|---|
| Memory leak | ✅ | 50 MB growth |
| Step time stability | ✅ | p95/std = 1.20 |
| Loss validity | ✅ | final=1.8000 |
| OOM events | ✅ | 0 |
| Temperature max | ✅ | 72°C |
| Thermal throttling | ✅ | 0 events |
| Checkpoint save | ✅ | |
| Checkpoint resume | ✅ | |
| **Overall verdict** | **✅ PASS** | |

## Decision

```
[soak] memory_leak          : OK (50 MB)
[soak] step_time_stable     : OK (p95/std=1.20)
[soak] loss_valid           : OK (no NaN)
[soak] no_oom               : OK (0 OOMs)
[soak] temperature_stable  : OK (max=72°C)
[soak] no_throttle          : OK (0 events)
[soak] checkpoint_save       : OK
[soak] checkpoint_resume     : OK
[soak] verdict              : PASS
```

## Source

`performance/soak_test_report.md`
