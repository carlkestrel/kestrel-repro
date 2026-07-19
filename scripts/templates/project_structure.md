# Project Structure (8 directories)

> Canonical layout for a single paper reproduction. Every project MUST
> follow this 8-directory skeleton. The `external/`, `data/`, and
> `experiments/` directories are tracked; everything else is regenerable.

## §1  `data/` — Data card & raw data

- **Purpose:** Hold the canonical dataset files for this paper.
- **Required contents:**
  - `data_card.md` (filled version of `templates/data_card.md`)
  - `data_hashes.json` (per-file MD5/SHA256)
  - `download.log` (verbatim download + verify commands)
  - raw data files (read-only; symlinks acceptable)
- **Forbidden:** any code (`.py`); any checkpoints; any logs.
- **source:** `templates/data_card.md`

## §2  `env/` — Environment card

- **Purpose:** Hold the environment card.
- **Required contents:**
  - `environment_card.md` (filled version of `templates/environment_card.md`)
  - `pip-freeze.txt` (verbatim)
  - `nvidia-smi.txt` (verbatim snapshot)
- **Forbidden:** any data, code, or checkpoints.
- **source:** `templates/environment_card.md`

## §3  `configs/` — Per-run configs

- **Purpose:** Hold the YAML/JSON configs for each run.
- **Required contents:**
  - `<run_id>/model.yaml`, `<run_id>/train.yaml`, `<run_id>/data.yaml`, `<run_id>/eval.yaml`
  - `<run_id>/all.yaml` (combined)
- **Forbidden:** any executable code; any binary checkpoints.
- **source:** `templates/parameter_table.md`

## §4  `scripts/` — Launch & utility scripts

- **Purpose:** Hold the exact scripts that drive the run.
- **Required contents:**
  - `launch.sh` (the verbatim launch command)
  - `verify.sh` (the verbatim verification command)
- **Forbidden:** any hard-coded paths; any data files.
- **source:** `experiments/<run_id>/run_manifest.json`

## §5  `logs/` — Logs

- **Purpose:** Hold the run logs.
- **Required contents:**
  - `train.log` (verbatim stdout/stderr)
  - `failures.jsonl` (one row per failure)
- **Forbidden:** any sensitive data (passwords, tokens).
- **source:** `templates/failure_case_report.md`

## §6  `results/` — Output artifacts

- **Purpose:** Hold the reproduction's outputs.
- **Required contents:**
  - `raw_metrics.json` (the canonical metric file)
  - `training_curve.png`
  - `confusion_matrix.json`
  - `per_class_iou.json`
- **Forbidden:** any processed data that loses traceability.
- **source:** `templates/parameter_table.md` §4

## §7  `docs/` — Narrative & reports

- **Purpose:** Hold human-readable narrative documents.
- **Required contents:**
  - `narrative_report.md` (filled version of `templates/narrative_report.md`)
  - `reproduction_report.md` (filled version of `templates/repro_report_skeleton.md`)
  - `failure_case_report.md` (filled version of `templates/failure_case_report.md`)
- **Forbidden:** any number without a "source:" link.
- **source:** `templates/repro_report_skeleton.md`

## §8  `README.md` — Root README

- **Purpose:** Hold the top-level navigation README.
- **Required contents:**
  - 1-line project summary
  - Link to `docs/reproduction_report.md`
  - Link to `data/data_card.md`
  - Link to `env/environment_card.md`
  - Link to `results/raw_metrics.json`
  - Quick-start command (verbatim)
- **Forbidden:** stale numbers; numbers without `source:`.
- **source:** `templates/repro_report_skeleton.md` §10

---

## Layout diagram

```
project_root/
├── README.md
├── data/
├── env/
├── configs/
├── scripts/
├── logs/
├── results/
└── docs/
```

## Forbidden anywhere

- Hard-coded absolute paths.
- Numbers without a `source:` link.
- Untracked binaries (`*.pt`, `*.bin`, `*.onnx` > 10 MB).