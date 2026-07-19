---
description: Run the ReproPerf AutoTuner to find the fastest safe training configuration without compromising paper reproduction semantics.
---

# /repro-perf

> Run the ReproPerf AutoTuner (`scripts/repro_perf_tuner.py`) through the
> full tuning pipeline. Must be preceded by a baseline gate pass.

## Usage

```
/repro-perf                          # run all phases sequentially
/repro-perf --phase health          # hardware health check only
/repro-perf --phase baseline        # measure paper protocol baseline
/repro-perf --phase capacity        # find max micro-batch (OOM search)
/repro-perf --phase dataloader      # tune DataLoader workers
/repro-perf --phase compute         # tune precision / compile / AMP
/repro-perf --phase parity          # verify numerical equivalence
/repro-perf --phase soak            # sustained-load verification
/repro-perf --phase recommend       # generate final recommendation
/repro-perf --phase all             # full pipeline
```

## 5-Phase Flow

| Phase | Reads | Writes | Blocks if |
|---|---|---|---|
| **Health** | hardware | `hardware_inventory.json`, `health_report.md` | GPU temp > 83°C, ECC error, hardware unstable |
| **Baseline** | `research_contract.md`, model | `baseline_metrics.csv`, `baseline_profile.json` | Gate 0 not passed |
| **Capacity** | `baseline_profile.json` | `capacity_trials.csv`, `safe_capacity.yaml` | health FAIL |
| **Dataloader** | `safe_capacity.yaml` | `tuning_trials.csv` | capacity not done |
| **Compute** | `safe_capacity.yaml` | `tuning_trials.csv` | dataloader not done |
| **Parity** | baseline + candidate profiles | `numerical_parity_report.md` | numerical diff detected |
| **Soak** | `optimized_performance.yaml` | `soak_test_report.md` | parity FAIL |
| **Recommend** | all above | `recommendation.md`, `strict_performance.yaml`, `optimized_performance.yaml`, `rollback.yaml` | soak FAIL |

## 12 Fundamental Rules (enforced by the script)

1. Always measure baseline before attempting optimization.
2. Use real model, real loss, and real DataLoader for all tests.
3. Capacity tests use short loops only — never long training.
4. Max non-OOM ≠ recommended config; reserve memory safety margin.
5. strict and optimized configs are stored separately.
6. strict mode preserves: model, data, loss, optimizer, LR, scheduler, effective global batch, eval protocol.
7. Only one primary variable changes per trial; complex combos are handled by the controlled searcher.
8. Each config is measured multiple times after warm-up; single-step comparisons are rejected.
9. Optimization gain must exceed measurement noise.
10. Numerical equivalence failure triggers immediate rollback.
11. No overclocking, power limit, fan, voltage, driver, or BIOS modification.
12. No quality reduction (fewer points, skipped data, reduced evaluation) to fake speedup.

## Pre-conditions

- Gate 0 (Paper Audit) passed.
- `research_contract.md` filled and signed.
- GPU present and healthy (health phase).
- No active GPU processes from previous runs.

## Output files

```
performance/
├── hardware_inventory.json        ← health phase
├── health_report.md             ← health phase
├── baseline_metrics.csv          ← baseline phase
├── baseline_profile.json         ← baseline phase
├── capacity_trials.csv           ← capacity phase
├── safe_capacity.yaml           ← capacity phase
├── tuning_trials.csv            ← dataloader + compute phases
├── bottleneck_report.md          ← dataloader + compute phases
├── numerical_parity_report.md    ← parity phase
├── soak_test_report.md          ← soak phase
├── strict_performance.yaml       ← always written (paper protocol)
├── optimized_performance.yaml    ← written if a safe winner found
├── rollback.yaml                ← always written
└── recommendation.md            ← final recommendation
```

## NO_SAFE_SPEEDUP Rule

If no candidate config is consistently faster than baseline, the script:

1. Writes `recommendation.md` with verdict `NO_SAFE_SPEEDUP`.
2. Leaves `optimized_performance.yaml` empty.
3. Recommends using `strict_performance.yaml`.
4. **Does not** force-apply optimization for demonstration purposes.

## Strict vs. Optimized Separation

| File | Contents |
|---|---|
| `strict_performance.yaml` | Paper protocol exactly; FP32; zero optimizations |
| `optimized_performance.yaml` | Safe speedup; same semantics; within numerical tolerance |
| `rollback.yaml` | Triggers and rollback targets for all failure modes |

## Source

`scripts/repro_perf_tuner.py`

## What this command does NOT do

- Does NOT modify model architecture.
- Does NOT change dataset or labels.
- Does NOT alter loss function or evaluation protocol.
- Does NOT reduce data quality or sample count.
- Does NOT auto-apply a config that fails parity or soak.
- Does NOT claim speedup that does not exceed measurement noise.