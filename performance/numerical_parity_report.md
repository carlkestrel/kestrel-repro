# Numerical Parity Report

> Baseline: `test-baseline`
> Candidate: `test-candidate`
> Timestamp: 2026-07-15T21:06:43.002543+00:00

## Tolerances

| Precision | Relative | Absolute |
|---|---|---|
| FP32 | 1e-6 | 1e-8 |
| TF32 | 1e-3 | 1e-5 |
| BF16 | 1e-2 | 1e-4 |
| FP16 | 1e-2 | 1e-4 |

## Results

| Check | Value | Within Tolerance? |
|---|---|---|
| Model output (L2) | 0.00e+00 | ✅ |
| Loss relative diff | 0.00e+00 | ✅ |
| Gradient L2 | 0.00e+00 | ✅ |
| NaN count | 0 | ✅ |
| Inf count | 0 | ✅ |
| Gradient vanishing | False | ✅ |
| Gradient exploding | False | ✅ |
| Checkpoint save/load | True | ✅ |

## Verdict

**ERROR: No module named 'torch'**

Numerical difference detected — candidate fails parity.

## Details

- No module named 'torch'

## Source

`performance/numerical_parity_report.md`
