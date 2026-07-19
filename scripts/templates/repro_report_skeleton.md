# Reproduction Report Skeleton (10 sections)

> Canonical structure for any `output/reports/reproduction_report.md`
> produced by `/repro-report`. Each section has a fixed header, a fixed
> minimum content list, and a "source:" rule.

## §1  Reproduction Goal (复现目标)

- Paper title + arXiv id
- Table / Figure being targeted
- Metric (with unit, e.g., mIoU%)
- Paper-reported value (with paper page reference)
- Tolerance (default 0.5 pp; specify otherwise)
- **source:** `templates/research_contract.md` §1

## §2  Code Source (代码来源)

- Repo URL (canonical)
- Pinned commit SHA (7–40 hex)
- License (SPDX id)
- Author / maintainer (with affiliation)
- Whether `is_official=True` (paper-author repo)
- Third-party clones considered + decision (Accept/Adapt/Reference Only/Reject)
- **source:** `templates/research_contract.md` §2

## §3  Data Card (数据卡)

- Dataset name + version
- License + redistribution status
- Train / val / test split (with file count + checksum)
- Class mapping (id → label, ignore labels)
- Preprocessing applied (voxel size, crop, augmentation)
- Link to `templates/data_card.md` §A
- **source:** `templates/research_contract.md` §3 + `templates/data_card.md`

## §4  Environment Card (环境卡)

- GPU model + driver + CUDA
- Python + PyTorch + key library versions
- Container hash (if used)
- Random seed policy
- Determinism flags (cuDNN, deterministic algorithms)
- Link to `templates/environment_card.md` §A
- **source:** `templates/environment_card.md`

## §5  Run Method (运行方法)

- Command(s) used to launch (verbatim)
- Number of GPUs, distributed config
- Total wall-clock + per-epoch time
- Resource benchmark (throughput in samples/sec)
- Link to `templates/parameter_table.md` §6
- **source:** `experiments/<run_id>/run_manifest.json`

## §6  Experiment Results (实验结果)

- Final metric (reproduced vs. paper; gap)
- Per-class breakdown (with confusion-matrix summary)
- Multi-seed mean ± std (if applicable)
- Visualization reference (`experiments/<run_id>/training_curve.png`)
- Link to `templates/parameter_table.md` §4
- **source:** `experiments/<run_id>/raw_metrics.json`

## §7  Failures & Issues (失败与问题)

- Per-failure rows: symptom → impact → fix → evidence
- Categorized: 已修复 / 已规避 / 未验证
- Link to `templates/failure_case_report.md`
- **source:** `templates/failure_case_report.md`

## §8  Reproduction Comparison & Gaps (复现对比不足)

- Side-by-side: paper | reproduced | gap | source
- Gap-source taxonomy (data / label / eval / hyperparam / seed / hardware / metric / ckpt)
- Tolerance check (`TOLERANCE_MIOU` from `templates/control_flags.md`)
- **source:** `templates/narrative_report.md` §6 + §8

## §9  Reproduction Conclusion (复现结论)

- Verdict: Reproduced / Partial / Not Reproduced / Protocol Unclear
- Confidence (0.0–1.0) + supporting/blocking dimensions
- Limitations explicitly listed
- **source:** `commands/repro-decision.md` §"Reproduction decision taxonomy"

## §10  Deliverables (交付物清单)

- Code (`external/<repo>/<sha>/`)
- Configs (`experiments/<run_id>/configs/`)
- Logs (`experiments/<run_id>/logs/`)
- Metrics (`experiments/<run_id>/raw_metrics.json`)
- Report (`output/reports/reproduction_report.md`)
- Cards (`templates/data_card.md`, `templates/environment_card.md`)
- **source:** `templates/project_structure.md`

---

## Cross-reference rules

Every "source:" link MUST point to a file that exists on disk. The
traceability check from `/repro-report` (P6_T02) walks every "source:"
and aborts on any broken link.