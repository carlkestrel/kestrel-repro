# /repro-audit

Audit the paper, upstream repository, data, and evaluation metrics for a deep learning paper reproduction.

## Usage

```
/repro-audit
```

Requires that `/repro-init` has been run and a repository has been cloned via `/repro-acquire`.

## What This Command Does

### Phase 0 — Paper Audit

Verify and document:
- [ ] Paper title, authors, and submission date
- [ ] Target table/figure and metric values
- [ ] Model architecture description
- [ ] Dataset description and split
- [ ] Training protocol (hyperparameters, augmentation, scheduler)
- [ ] Evaluation protocol (checkpoint selection, voting, TTA)
- [ ] Any ambiguities or discrepancies in the paper
- [ ] Any discrepancies between paper and repository README

Output: `repro_audit/source_audit/paper_summary.md`

### Phase 1 — Source Audit

Verify and document:
- [ ] Repository URL matches paper-author's official repo
- [ ] Commit hash is aligned with paper submission date
- [ ] All configuration files are present and match paper
- [ ] No uncommitted changes in the repository
- [ ] Required dependencies are pinned
- [ ] Custom CUDA extensions are identified
- [ ] Training script matches paper's protocol
- [ ] Evaluation script matches paper's metric definition
- [ ] No security concerns in installation scripts

Output: `repro_audit/source_audit/source_audit.md` and `.json`

### Phase 2 — Data Audit

Verify and document:
- [ ] Dataset is available (downloaded, licensed, accessible)
- [ ] Dataset version matches paper
- [ ] Data split matches paper (train/val/test ratios)
- [ ] Label definitions match paper's metric definitions
- [ ] Raw-to-remapped label mapping is verified
- [ ] Ignored/void labels are handled correctly
- [ ] Data augmentation in training matches evaluation
- [ ] No data leakage between train and test

Output: `repro_audit/data_audit/data_audit.md` and `.json`

### Phase 3 — Metric Protocol Audit

Verify and document:
- [ ] Metric computation matches paper (per-class then mean vs. other)
- [ ] Checkpoint selection criteria match paper (best val, last, specific epoch)
- [ ] Evaluation mode matches paper (sub-points, full-PC voting, TTA)
- [ ] Metric computation uses correct label mappings
- [ ] Multi-scale or multi-crop evaluation is handled correctly
- [ ] Class-wise IoU is computed before averaging

Output: `repro_audit/metric_audit/metric_audit.md` and `.json`

## Output Artifacts

```
repro_audit/
├── source_audit/
│   ├── paper_summary.md
│   ├── source_audit.md
│   ├── source_audit.json
│   └── config_matrix.md
├── data_audit/
│   ├── data_audit.md
│   ├── data_audit.json
│   └── label_matrix.md
└── metric_audit/
    ├── metric_audit.md
    └── metric_audit.json
```

## Gate 0 Completion

This command completes Gate 0 (Paper & Source Audit). After running `/repro-audit`, the agent should update `state.json`:

```json
{
  "gates": {
    "gate_0_paper_audit": {
      "status": "passed",
      "timestamp": "<ISO 8601>",
      "evidence": "repro_audit/source_audit/"
    }
  }
}
```

## What This Command Does NOT Do

- Does NOT install dependencies or run code
- Does NOT modify the repository
- Does NOT download data
- Does NOT start training or evaluation
- Does NOT generate checkpoints or metrics

## Requirements

- Requires `.repro/repro_spec.yaml` (from `/repro-init`)
- Requires that a repository is cloned into `primary/` (from `/repro-acquire`)
- Does NOT require environment setup or data to be downloaded
- This is a read-only audit — no code execution

## Next Steps

After `/repro-audit` passes, proceed with:

1. `/repro-preflight` — Verify environment, data, and disk space
2. `/repro-short-loop` — Validate network can train and checkpointing works
