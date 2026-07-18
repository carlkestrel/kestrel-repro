# Numerical Parity Report

> Baseline: `test-baseline`
> Candidate: `test-candidate`
> Timestamp: 2026-07-18T14:53:35.424843+00:00

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
| Model output (L2) | 3.96e-07 | ✅ |
| Loss relative diff | 1.26e-07 | ✅ |
| Gradient L2 | 1.27e-07 | ✅ |
| NaN count | 0 | ✅ |
| Inf count | 0 | ✅ |
| Gradient vanishing | False | ✅ |
| Gradient exploding | False | ✅ |
| Checkpoint save/load | True | ✅ |

## Verdict

**NUMERICAL_EQUIVALENT**

All numerical checks passed within tolerance.

## Details

*(none)*

## Source

`performance/numerical_parity_report.md`
