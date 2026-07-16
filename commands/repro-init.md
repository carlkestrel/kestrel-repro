# /repro-init

Initialize a new deep learning paper reproduction project.

## Usage

```
/repro-init paper=<paper-url-or-arxiv-id> target=<target-table-or-metric>
```

## What This Command Does

### Step 1 — Parse Paper Information

Accept a paper URL (arXiv, PDF, or GitHub) or arXiv ID. Extract:
- Paper title and authors
- Target metrics (e.g., "Table 3, mIoU", "Figure 5, accuracy")
- Dataset and model architecture
- Training protocol (if available in abstract/appendix)

### Step 2 — Create Project Structure

Create the `.repro/` directory and files:

```
<repository-root>/
├── .repro/
│   ├── repro_spec.yaml         # Paper and repository metadata
│   ├── repo_adapter.yaml       # Repository-specific commands
│   ├── sources.lock.yaml       # Pinned repository URLs and commits
│   ├── state.json              # Gate status and phase tracking
│   └── runs_manifest.csv      # All experiment runs
├── primary/                    # (created by /repro-acquire)
├── references/                # (created by /repro-acquire)
└── repro_audit/               # Audit reports and evidence
    ├── source_audit/
    ├── data_audit/
    ├── runtime_audit/
    └── evidence_chain/
```

### Step 3 — Generate repro_spec.yaml

Populate the reproduction specification:

```yaml
paper:
  title: "<from paper>"
  url: "<provided URL>"
  arxiv_id: "<if applicable>"
  target_table: "<e.g., Table 3>"
  target_metrics:
    - metric: mIoU
      value: 73.9
      column: S3DIS (val)
  submission_date: "<from paper>"

code:
  upstream_url: ""  # to be filled by /repro-discover
  target_commit: ""  # to be determined
  current_commit: ""  # to be determined

data:
  root_env: DATA_ROOT
  version: ""
  split: ""
  restricted: false

protocol:
  epochs: null
  seeds: []
  checkpoint_selection: ""
  evaluation_mode: ""
  ignored_labels: []

compute:
  policy: strict_then_optimized
  allow_amp_after_parity: true
  allow_ddp_after_parity: true

artifacts:
  root: repro_audit
```

### Step 4 — Generate repo_adapter.yaml Template

Create a template for repository-specific commands:

```yaml
# TO BE COMPLETED after /repro-acquire
commands:
  environment_check: ""
  preprocess: ""
  train: ""
  evaluate: ""
  predict: ""
  full_pc_vote: ""

entrypoints:
  model: ""
  dataset: ""
  loss: ""
  metrics: ""

artifacts:
  checkpoints: ""
  logs: ""
  metrics: ""
  predictions: ""

smoke:
  config: ""
  max_steps: 1

short_loop:
  overfit_steps: 100
  mini_epochs: 3
```

### Step 5 — Create State File

Initialize `state.json` with all gates pending:

```json
{
  "paper_url": "<provided>",
  "target_metrics": [],
  "phase": "init",
  "gates": {
    "gate_0_paper_audit": {"status": "pending", "timestamp": "", "evidence": ""},
    "gate_1_preflight": {"status": "pending", "timestamp": "", "evidence": ""},
    "gate_2_short_loop": {"status": "pending", "timestamp": "", "evidence": ""},
    "gate_3_parity": {"status": "pending", "timestamp": "", "evidence": ""},
    "gate_4_full_training": {"status": "pending", "timestamp": "", "evidence": ""},
    "gate_5_evidence": {"status": "pending", "timestamp": "", "evidence": ""}
  },
  "current_mode": "strict_repro",
  "repositories": {},
  "runs": []
}
```

## What This Command Does NOT Do

- Does NOT clone repositories (use `/repro-acquire` for that)
- Does NOT install dependencies
- Does NOT audit code or data
- Does NOT run any experiments
- Does NOT modify the primary repository

## Next Steps

After `/repro-init`, proceed with:

1. `/repro-discover` — Find and evaluate candidate repositories
2. `/repro-acquire` — Clone the primary and reference repositories
3. `/repro-fit-hardware` — Assess hardware compatibility
4. `/repro-audit` — Audit paper, source, data, and metrics
5. `/repro-preflight` — Verify environment and data

## Example

```
/repro-init paper=https://arxiv.org/abs/2103.14641 target="Table 2, mIoU on S3DIS"
```

This creates:
- `.repro/repro_spec.yaml` with paper metadata
- `.repro/repo_adapter.yaml` (empty template)
- `.repro/state.json` (all gates pending)
- `repro_audit/` directory structure
