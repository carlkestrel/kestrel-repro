# ReproPerf Recommendation

> Timestamp: 2026-07-15T21:06:43.063754+00:00

## Headline Results

| Metric | Baseline | Optimized | Delta | Speedup |
|---|---|---|---|---|
| Throughput (samples/s) | 0.00 | — | — | — |
| Step time mean (s) | — | — | — | — |
| GPU memory peak (MB) | — | — | — | — |

## Recommendation

| Parameter | Baseline | Recommended |
|---|---|---|
| Precision | FP32 | (from tuning trials) |
| Micro-batch | 5 | (from capacity search) |
| num_workers | ? | (from dataloader search) |
| torch_compile | false | (from compute search) |

## Verdict

**NO_SAFE_SPEEDUP** — tuning trials not yet collected. Run phases:
1. `python repro_perf_tuner.py --phase baseline`
2. `python repro_perf_tuner.py --phase capacity`
3. `python repro_perf_tuner.py --phase dataloader`
4. `python repro_perf_tuner.py --phase compute`
5. `python repro_perf_tuner.py --phase parity`
6. `python repro_perf_tuner.py --phase recommend`

## Source

`performance/recommendation.md`
