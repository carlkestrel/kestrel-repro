# /repro-benchmark

Profile hardware throughput and validate numerical parity between strict and optimized execution modes.

## Usage

```
/repro-benchmark [mode=<strict|optimized|parity>] [duration=<seconds>]
```

Defaults to running all three phases: strict profiling, optimized profiling, and parity comparison.

## What This Command Does

### Phase 1 — Strict Mode Profiling

Profile the baseline configuration (FP32, single GPU, paper-specified batch size):

**Metrics captured:**
- Throughput: samples/second, steps/second
- GPU utilization: average and peak
- GPU memory: allocated, reserved, peak
- CPU utilization: average
- DataLoader throughput: samples/second from loader
- GPU→CPU transfer time (if using pin_memory)

**Steps:**
1. Warm up for 10 steps (JIT compilation, GPU warmup)
2. Profile for N steps (default: 100)
3. Capture all metrics
4. Compute summary statistics (mean, std, min, max)

Script: `scripts/benchmark_runtime.py --mode strict`
Output: `repro_audit/benchmark/strict_profile.md` and `.json`

### Phase 2 — Optimized Mode Profiling

Profile the optimized configuration (AMP, adjusted batch size, DDP if applicable):

**Configurations to test:**
- AMP/BF16 mixed precision
- Adjusted physical batch size (with gradient accumulation if needed)
- DDP (if multiple GPUs available)
- DataLoader optimizations (num_workers, pin_memory)

**Metrics captured:** Same as Phase 1

**Steps:**
1. Warm up for 10 steps
2. Profile for N steps
3. Capture all metrics
4. Compute summary statistics

Script: `scripts/benchmark_runtime.py --mode optimized`
Output: `repro_audit/benchmark/optimized_profile.md` and `.json`

### Phase 3 — Numerical Parity Testing

Compare strict and optimized modes for numerical equivalence:

**What to compare:**
- Loss curves (step-by-step loss values)
- Final metrics (mIoU, accuracy, etc.)
- Gradient norms
- Parameter values after training

**Pass criteria:**
- Final metrics within tolerance (typically ±0.5% absolute for mIoU)
- Loss curves within tolerance (max deviation < 0.1% per step)
- No NaN or Inf in optimized mode when strict mode is stable
- Gradient norms within same order of magnitude

Script: `scripts/compare_runs.py strict optimized`
Output: `repro_audit/benchmark/parity_report.md` and `.json`

### Phase 4 — Optimization Recommendations

Based on profiling results, recommend:
- Optimal batch size for throughput vs. memory tradeoff
- Optimal num_workers for DataLoader
- Whether AMP/BF16 is safe to use (based on parity test)
- Whether DDP is worth the overhead
- Whether torch.compile is stable (if requested)

Script: `scripts/reproctl.py recommend-optimizations`
Output: `repro_audit/benchmark/optimization_recommendations.md`

## Output Artifacts

```
repro_audit/
├── benchmark/
│   ├── strict_profile.md
│   ├── strict_profile.json
│   ├── optimized_profile.md
│   ├── optimized_profile.json
│   ├── parity_report.md
│   ├── parity_report.json
│   ├── optimization_recommendations.md
│   └── throughput_comparison.csv
└── raw_metrics/
    ├── strict_profile.csv
    └── optimized_profile.csv
```

## Gate 3 Completion

After parity testing passes, update `state.json`:

```json
{
  "gates": {
    "gate_3_parity": {
      "status": "passed",
      "timestamp": "<ISO 8601>",
      "evidence": "repro_audit/benchmark/",
      "parity_results": {
        "amp_parity": "passed",
        "ddp_parity": "not_tested",
        "batch_size_parity": "passed",
        "tolerance": 0.5
      }
    }
  },
  "phase": "benchmark"
}
```

If parity fails:

```json
{
  "gates": {
    "gate_3_parity": {
      "status": "failed",
      "timestamp": "<ISO 8601>",
      "evidence": "",
      "failure_reasons": [
        "AMP final mIoU differs by 1.2% from strict (tolerance: 0.5%)"
      ]
    }
  }
}
```

## What This Command Does NOT Do

- Does NOT run full training
- Does NOT evaluate on the full test set
- Does NOT modify the repository code
- Does NOT change any training hyperparameters
- Does NOT claim paper-level results

## Parity Tolerance Reference

| Metric | Typical Tolerance | Notes |
|---|---|---|
| mIoU | ±0.5% absolute | Tight tolerance for semantic segmentation |
| Accuracy | ±0.5% absolute | Image classification |
| F1 Score | ±0.5% absolute | Detection, retrieval |
| Loss | No fixed tolerance | Watch for NaN/divergence |
| Per-class IoU | ±1.0% absolute | Check individual class IoUs, not just mean |

## Next Steps

After `/repro-benchmark` (Gate 3):
- If parity passes: proceed with `/repro-launch` for full training
- If parity fails: fall back to strict_repro mode, document the failure, and proceed with `/repro-launch` in strict mode
- If optimized mode is needed but parity fails: report the failure and require user decision

## Integration with reproctl

`reproctl.py` enforces that optimized_repro_safe mode can only be used for paper results if Gate 3 is passed. Attempting to run full training in optimized mode without passing parity will be blocked.
