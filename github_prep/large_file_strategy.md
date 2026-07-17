# Large File Strategy for kestrel-repro

This document analyzes large files and data in the repository and provides recommendations for GitHub preparation.

---

## 1. Files Over 1MB

**Status: No files exceed 1MB**

The repository does not contain any files larger than 1MB. The largest files are:

| File | Size | Type |
|------|------|------|
| `docs/html/complete_manual.html` | 198 KB | Generated HTML documentation |
| `.execution/plan_snapshot.md` | 71 KB | Plan snapshot (JSON-like) |
| `scripts/reproctl.py` | 67 KB | Main control script |
| `scripts/repro_perf_tuner.py` | 41 KB | Performance tuning script |
| `tests/test_startup.py` | 41 KB | Startup test file |
| `.execution/task_graph.yaml` | 39 KB | Task graph configuration |

### Directory Sizes

| Directory | Size |
|-----------|------|
| `scripts/` | 1.7 MB |
| `docs/` | 1.3 MB |
| `tests/` | 280 KB |
| `commands/` | 208 KB |
| `templates/` | 200 KB |

---

## 2. Data Files That Should Not Be in Git

### Checkpoint Files (.pth, .pt, .ckpt)
**Status: None found**

No checkpoint files exist in the repository. The `.gitignore` already includes patterns for these files:
```
*.pt
*.pth
*.ckpt
```

### Dataset Files (.h5, .npy, train.*, test.*)
**Status: None found**

No dataset files exist in the repository.

### Log Files
**Status: Small logs only (156 bytes each)**

Log files are located in `.execution/evidence/` and are tiny test artifacts:
- `P11_T0X_test.log` (156 bytes each)
- `P12_T0X_test.log` (155 bytes each)
- `P2_T05_experiments_test.log`
- `P3_T02_human_checkpoint_test.log`
- `P4_T01_T06_monitor_test.log`

The `.gitignore` already includes:
```
*.log
logs/
```

### Cache Directories
**Status: Standard Python caches exist**

| Cache Type | Location |
|------------|----------|
| `__pycache__` | `tests/__pycache__`, `scripts/cvo/__pycache__`, `scripts/ostar/__pycache__` |
| `.pytest_cache` | `.pytest_cache` |
| `.cache/` | Contains crawler index at `.cache/crawler/_index.json` |

The `.gitignore` already includes:
```
__pycache__/
*.py[cod]
.pytest_cache/
.cache/
```

### Generated/Output Directories

| Directory | Type | Status |
|-----------|------|--------|
| `artifacts/` | Runtime output | Should remain gitignored |
| `artifacts/runs/run_20260716_085646/` | Experiment run output | Contains checkpoints, figures, predictions, confmat |
| `.repro/audit/` | Audit data | 41 JSON nodes + reports |
| `.execution/` | Execution evidence | Test logs, evidence files |
| `.stabilization/` | Stabilization state | Config/state files |
| `.repair/` | Bug patches | Patch files |

---

## 3. Git LFS Recommendations

**Git LFS is NOT required** for this repository.

Rationale:
- No files exceed 1MB
- No binary data files (checkpoints, datasets, models) exist
- All data is either generated on-the-fly or small JSON/text files
- The largest generated file is HTML documentation at 198KB

### If Git LFS Were Needed

The following patterns would be candidates:

```gitattributes
*.pth filter=lfs diff=lfs merge=lfs -text
*.pt filter=lfs diff=lfs merge=lfs -text
*.ckpt filter=lfs diff=lfs merge=lfs -text
*.h5 filter=lfs diff=lfs merge=lfs -text
*.hdf5 filter=lfs diff=lfs merge=lfs -text
*.npy filter=lfs diff=lfs merge=lfs -text
*.npz filter=lfs diff=lfs merge=lfs -text
*.pkl filter=lfs diff=lfs merge=lfs -text
*.pth.tar filter=lfs diff=lfs merge=lfs -text
```

---

## 4. Data Download Instructions

### How to Get Test Datasets

The repository uses **synthetic/fixture data** that is generated programmatically:

#### Option A: Generate Minimal Test Data (Recommended)

```bash
# Generate minimal test data for the minimal_pytorch_repo fixture
cd fixtures/minimal_pytorch_repo
python train.py --epochs 2 --seed 42 --output-dir experiments/fixture-run

# This creates:
#   experiments/fixture-run/checkpoints/epoch_001.pth
#   experiments/fixture-run/logs/train.log
#   experiments/fixture-run/metrics/raw_metrics.json
```

#### Option B: Generate Point Cloud Test Data

```bash
# Generate synthetic point cloud data for golden_pointcloud_B fixture
cd fixtures/golden_pointcloud_B
python generate_test_data.py

# This creates:
#   test_data/sample_000.bin ... sample_009.bin
#   test_data/metadata.json
```

### How to Get Checkpoints

**No pre-trained checkpoints are provided.**

Checkpoints are generated during fixture execution:
- `fixtures/minimal_pytorch_repo/train.py` generates checkpoints with `--epochs` flag
- Checkpoints are saved to `--output-dir/checkpoints/epoch_XXX.pth`

For real reproduction work, checkpoints would need to be downloaded from:
- Original paper's GitHub repository
- Hugging Face model hub
- Weights & Biases / cloud storage

### How to Get Example Data for Testing

#### Unit Tests
```bash
# Run tests that use small fixture data
pytest tests/ -v

# Specific fixture tests
pytest fixtures/golden_torch_A/test_golden_torch_A.py -v
pytest fixtures/golden_pointcloud_B/test_golden_pointcloud_B.py -v
```

#### Smoke Tests
```bash
# Run minimal end-to-end test
python scripts/smoke_test.py
```

#### Golden Tests
```bash
# Run golden tests with synthetic data
python scripts/repro_agent/metrics/golden_test.py
```

---

## 5. Proposed .gitignore Additions

The current `.gitignore` is comprehensive. The following additions are recommended to ensure completeness:

```gitignore
# --- Additional Python ---
*.whl
pip-log.txt
pip-delete-this-directory.txt

# --- Additional IDE/Cache ---
*.sln
*.suo
*.user
*.vsidx
.history/
.ionide/

# --- Additional Testing ---
.tox/
.nox/
cover/
htmlcov/
tests/.pytest_cache/
.pytest_cache/

# --- Model Checkpoints (if added) ---
checkpoints/
*.onnx
*.tflite

# --- Experiment Outputs ---
experiments/
*.wandb
wandb/
mlruns/

# --- Data (if added) ---
data/
raw/
processed/

# --- Performance/Runtime (if added) ---
*.prof
*.pstats
.profiling/

# --- Documentation Builds ---
docs/html/build/
site/
```

### Existing .gitignore Strengths

The current `.gitignore` already properly handles:
- Python bytecode and distributions
- Virtual environments
- IDE files
- Log files
- Build artifacts
- Model checkpoints (*.pt, *.pth, *.ckpt)
- Archives (*.zip, *.tar.gz)
- Test coverage and cache

---

## Summary

| Category | Status | Action Required |
|----------|--------|----------------|
| Files > 1MB | None | None |
| Checkpoint files | None exist | Already gitignored |
| Dataset files | None exist | None |
| Log files | Small (156B) | Already gitignored |
| Cache directories | Python std | Already gitignored |
| Git LFS needed | No | None |
| .gitignore gaps | Minor | Optional additions above |
| Data generation | Fixtures exist | Documented in Section 4 |
