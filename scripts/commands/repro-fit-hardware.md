# /repro-fit-hardware

Assess repository hardware requirements against local hardware configuration and recommend execution modes.

## Usage

```
/repro-fit-hardware [repo=<repository-url-or-path>]
```

If no repository is specified, assesses all candidate repositories from `candidate_repositories.csv`.

## What This Command Does

### Step 1 — Hardware Detection

Run and interpret hardware detection:

```bash
nvidia-smi
python -m torch.utils.collect_env
lscpu
free -h
df -h
```

Capture:
- GPU model and compute capability (e.g., Ampere, Ada Lovelace)
- CUDA compute capability (e.g., 8.9 for RTX 4080)
- VRAM total and available
- Number of GPUs
- CUDA driver version
- CUDA toolkit version
- cuDNN version
- PyTorch version and build
- CPU model, cores, threads
- RAM total and available
- Disk type (SSD/NVMe vs HDD) and free space

Script: `scripts/hardware_profile.py`
Output: `repro_audit/hardware/hardware_profile.md` and `.json`

### Step 2 — Per-Repository Compatibility Assessment

For each candidate repository, assess:

1. **GPU compute capability compatibility:**
   - Does the GPU support required CUDA features?
   - Are custom CUDA extensions compatible?
   - Does the code use BF16/TF32 intrinsics?
   - Is Ampere+ required for the model?

2. **VRAM assessment:**
   - Physical batch size the GPU can handle
   - Gradient accumulation requirements
   - Full-point-cloud voting memory (for point cloud models)
   - Checkpoint and optimizer state memory

3. **Multi-GPU efficiency:**
   - Is DDP worth the communication overhead?
   - What is the expected speedup from multi-GPU?
   - Is the dataset large enough to benefit?

4. **Data loading assessment:**
   - Is the SSD fast enough for data loading?
   - Optimal num_workers based on CPU cores
   - RAM requirements for data caching

5. **Estimated disk space:**
   - Dataset size (raw and cached)
   - Checkpoint storage
   - Log and prediction storage

### Step 3 — Execution Mode Recommendations

For each repository, recommend one of three modes:

#### Mode 1 — strict_repro
Paper-accurate configuration, no optimizations:
- FP32 precision
- Single GPU
- Paper-specified batch size
- No gradient accumulation workarounds
- No mixed precision

**When to use:** Always start here. This is the baseline.

#### Mode 2 — optimized_repro_safe
Proven-safe optimizations with verified numerical parity:
- AMP or BF16 with verified parity (within ±0.5% mIoU)
- DDP with verified parity
- Adjusted batch size with verified parity
- DataLoader optimizations (num_workers, pin_memory)
- Gradient accumulation to simulate larger batches

**When to use:** Only after Gate 3 parity testing passes.

#### Mode 3 — experimental_fast
Performance experiments NOT for paper results:
- torch.compile
- Aggressive batch sizes beyond GPU limits
- Custom CUDA optimizations
- Changes requiring additional validation

**When to use:** Never for paper results. Only for exploring performance.

### Step 4 — Parity Test Requirements

For any optimization beyond strict_repro, document required tests:

| Optimization | Required Parity Test |
|---|---|
| AMP/BF16 | Run 3 epochs FP32 vs. AMP; compare loss curves and final mIoU |
| DDP | Run 3 epochs single vs. multi-GPU; compare metrics |
| Batch size increase | Run with gradient accumulation; compare to original batch |
| torch.compile | Run 3 epochs; compare loss curves and metrics |
| DataLoader changes | Profile throughput; verify no NaN/divergence |

### Step 5 — Hardware Fit Report

Generate a comprehensive report:

```markdown
# Hardware Fit Report

## Local Hardware
- GPU: NVIDIA RTX 5080 (Compute 8.9)
- VRAM: 16 GB
- GPUs: 1
- CPU: AMD Ryzen 9 9950X (16 cores)
- RAM: 64 GB
- Disk: NVMe SSD (2 TB free)

## Repository Compatibility

### Primary: official (author/official)
| Aspect | Assessment | Details |
|---|---|---|
| GPU capability | ✅ Compatible | RTX 5080 supports all required features |
| VRAM | ⚠️ Tight | 16 GB; may need batch=4 with grad accum |
| Multi-GPU | ❌ Not needed | Single GPU sufficient for dataset size |
| Data loading | ✅ Fast | NVMe SSD handles PLY loading well |
| Estimated time | ~4 hours | Full training on S3DIS at batch=4 |

**Recommended mode:** strict_repro (batch=4, FP32)
**Optimization potential:** AMP safe after parity test; DDP not needed

### Reference: impl-a (other/impl-a)
| Aspect | Assessment | Details |
|---|---|---|
| GPU capability | ✅ Compatible | Same requirements as primary |
| VRAM | ⚠️ Tight | Custom CUDA ops use more memory |
| Estimated time | ~5 hours | KPConv ops less optimized |

**Recommended mode:** strict_repro
**Optimization potential:** AMP unsafe due to custom CUDA ops

## Execution Mode Summary

| Repository | Recommended Mode | Reason |
|---|---|---|
| official | strict_repro | Baseline; AMP safe after parity |
| impl-a | strict_repro | Baseline; CUDA ops incompatible with AMP |
| impl-b | strict_repro | Baseline; smaller model fits in memory |

## Parity Test Plan

| Test | Repositories | Duration | Pass Criteria |
|---|---|---|---|
| AMP vs FP32 | official | 30 min | \|mIoU_amp - mIoU_fp32\| < 0.5% |
| DDP vs single | N/A | N/A | Not recommended |
| Batch scaling | official | 1 hour | \|mIoU_grad_accum - mIoU_native\| < 0.5% |
```

## Output Artifacts

```
repro_audit/
├── hardware/
│   ├── hardware_profile.md
│   ├── hardware_profile.json
│   ├── hardware_fit_report.md
│   ├── hardware_fit_report.json
│   └── execution_mode_recommendations.md
└── parity_test_plan.md
```

## Gate 2 Supplement

`/repro-fit-hardware` complements Gate 2 (Short-Loop) by providing:
- Confirmed hardware compatibility before running short-loop
- Recommended configuration adjustments for the hardware
- Parity test requirements for any planned optimizations

## What This Command Does NOT Do

- Does NOT modify any code or configuration
- Does NOT run training or evaluation
- Does NOT install dependencies
- Does NOT change the repository
- Does NOT guarantee that recommended settings will work — short-loop still validates

## Next Steps

After `/repro-fit-hardware`:
1. Review the hardware fit report
2. Confirm the recommended execution mode
3. Proceed with `/repro-short-loop` using the recommended configuration
4. Then proceed with `/repro-benchmark` for parity testing
