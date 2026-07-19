# Performance File Templates

This directory contains **template skeletons** (column headers, JSON
shape, markdown front-matter) for every runtime artefact emitted by the
`runtime-optimizer` and `hardware-fit-auditor` agents.

The actual values live under `../../performance/` (the `performance/`
folder at the repo root) and are gitignored.

## Why split templates from data

- **Schema checkpoint.** Committed templates lock the file shape —
  any change to a column / JSON key / Markdown section becomes a
  diff-able change in version control.
- **Runtime decoupled.** Runtime artefacts stay out of the repo so the
  same repo works on every host.
- **Same regeneration command.** Both template and runtime variants
  are produced by the same tool:

    ```bash
    python scripts/runtime/repro_perf_tuner.py --phase all
    ```

## Files

| File | Purpose |
|------|---------|
| `baseline_metrics.csv`     | Trial-level timing & throughput columns (header only) |
| `baseline_profile.json`    | Per-step forward / backward / optimizer timing |
| `bottleneck_report.md`     | Markdown skeleton for bottleneck analysis section |
| `capacity_trials.csv`      | Memory / saturation sweep trials |
| `hardware_inventory.json`  | GPU / CPU / RAM / disk inventory |
| `health_report.md`         | Markdown skeleton for health-check summary |
| `numerical_parity_report.md` | Markdown skeleton for parity check |
| `optimized_performance.yaml` | Final tuned configuration |
| `recommendation.md`        | Markdown skeleton for tuning recommendation |
| `rollback.yaml`            | Snapshot used to revert to a prior tuning |
| `safe_capacity.yaml`       | Maximum safe batch × sequence × world-size |
| `soak_test_report.md`      | Markdown skeleton for long-running stability run |
| `strict_performance.yaml`  | Strict-mode performance baseline |
| `tuning_trials.csv`        | Concatenation of all trial rows during tuning |

When adding a new runtime artefact, **first add the template here**,
then regenerate via `repro_perf_tuner.py`. The diff against the
template is your schema change.
