# Experiment Plan (M0–M10)

> **Why this file exists**: before any training run, we agree on a numbered
> sequence of *modules* (M0…M10) so that progress is auditable and a failure
> at M_k can be attributed to the smallest unit that was supposed to validate
> it. Each module has **exactly 12 metadata fields** (see schema). Adding a
> field is a contract change and must be reflected in `scripts/reproctl.py`.

## Module sequence (M0 → M10)

| ID | Title | Purpose | Pass criterion (default) |
|---|---|---|---|
| **M0** | Data sanity | Dataset MD5 / file count / split integrity | `data_contract.md` integrity rows all PASS |
| **M1** | Repo clone + git-pin | Upstream code pinned to commit | `reproctl check git-pin` PASS |
| **M2** | Environment bootstrap | CUDA / Python / pip deps installed | `python -c "import torch; print(torch.cuda.is_available())"` PASS |
| **M3** | Smoke run (1 epoch, tiny subset) | Code path end-to-end, no NaN | loss finite, checkpoint written |
| **M4** | Full-protocol training (paper settings) | Reproduce paper's reported numbers | metric within `TOLERANCE_MIOU` of paper value |
| **M5** | Multi-seed runs (≥3) | Variance estimate | mean ± std reported, no seed > 1σ outlier |
| **M6** | Ablations (paper-listed) | Each ablation matches paper's ablation table | per-row delta within tolerance |
| **M7** | Robustness / corner cases | Distribution shift, missing labels, partial inputs | behaviour documented |
| **M8** | Reproducibility audit | Re-run M4 from scratch, compare | bitwise or seed-equivalent match |
| **M9** | Efficiency measurement | Wall-clock, GPU-hours, peak VRAM | reported in `runs_manifest.csv` |
| **M10** | Approved extensions | Out-of-scope experiments approved via decision row | new claim row added to matrix |

## Per-experiment metadata (12 fields, exact order)

1. `experiment_id` — `M{n}-{short-slug}` (e.g., `M4-kpconv-s3dis`)
2. `claim_id` — claim from `claim_evidence_matrix.md` (`C1`, `C2`, …)
3. `module` — `M0`…`M10`
4. `dataset` — dataset name + split (e.g., `s3dis/Area-6`)
5. `protocol` — eval protocol reference (`data_contract.md` §Evaluation)
6. `seeds` — comma-separated seed list
7. `expected_metric` — paper value + tolerance (e.g., `73.9% ± 0.5pp`)
8. `compute_budget` — wall-clock / GPU-hours cap
9. `risk_level` — `low` | `medium` | `high`
10. `depends_on` — `experiment_id` list this run needs to wait for
11. `evidence_paths` — comma-separated output paths (log, ckpt, metric)
12. `notes` — free text, 1–2 sentences

## Header (do not delete)

| experiment_id | claim_id | module | dataset | protocol | seeds | expected_metric | compute_budget | risk_level | depends_on | evidence_paths | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|

## Rows

(Append one row per experiment. Format: `| E1 | C1 | M4 | ... |`)

| experiment_id | claim_id | module | dataset | protocol | seeds | expected_metric | compute_budget | risk_level | depends_on | evidence_paths | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|

---

## Contract change protocol

Adding/removing a metadata field requires:

1. Update this header table.
2. Update the parser in `scripts/reproctl.py` (`parse_experiment_plan`).
3. Append a `risk_override` row to `DECISION_LOG.md` citing this section.