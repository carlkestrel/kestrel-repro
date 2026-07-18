# /repro-preflight

Run environment, dataset, and system checks before any code execution.

## Usage

```
/repro-preflight
```

Requires that `/repro-init` and `/repro-acquire` have been run.

## What This Command Does

### Step 1 — Environment Check

Run and verify:
- [ ] Python version matches repository requirements
- [ ] CUDA version is compatible with PyTorch
- [ ] cuDNN version is available
- [ ] PyTorch version matches requirements
- [ ] All required Python packages are installed
- [ ] Custom CUDA extensions can be compiled (if applicable)
- [ ] GPU is detected and accessible
- [ ] torch.utils.collect_env output is captured

Script: `scripts/environment_check.py`
Output: `repro_audit/runtime_audit/environment_check.md`

### Step 2 — Dataset Check

Verify and document:
- [ ] Dataset root directory exists
- [ ] All required data files are present
- [ ] Data split files are present (train/val/test lists)
- [ ] Label files are present
- [ ] Dataset can be loaded by the repository's dataset class
- [ ] Number of classes matches paper
- [ ] Point cloud files can be read (for point cloud datasets)
- [ ] No corrupted or missing files

Script: Uses repository's dataset class (via `repo_adapter.yaml`)
Output: `repro_audit/data_audit/dataset_check.md`

### Step 3 — Disk Space Check

Verify:
- [ ] Sufficient space for dataset (if not pre-downloaded)
- [ ] Sufficient space for checkpoints (estimated)
- [ ] Sufficient space for logs and raw metrics
- [ ] Sufficient space for predictions and evaluations
- [ ] Path structure is correct (no permission issues)

Script: `scripts/environment_check.py`
Output: `repro_audit/runtime_audit/disk_space.md`

### Step 4 — Hardware Profile

Capture and document:
- [ ] GPU model and compute capability
- [ ] GPU memory (total and available)
- [ ] CUDA driver version
- [ ] Number of GPUs
- [ ] CPU model and core count
- [ ] RAM total and available
- [ ] Disk type and free space
- [ ] PyTorch/CUDA compatibility check

Script: `scripts/hardware_profile.py`
Output: `repro_audit/runtime_audit/hardware_profile.md` and `.json`

### Step 5 — Repository Integrity Check

Verify:
- [ ] All required files are present in the repository
- [ ] No uncommitted changes that could affect reproducibility
- [ ] Git working tree is clean (or uncommitted changes are documented)
- [ ] Required entrypoints (model, dataset, loss) are accessible

## Output Artifacts

```
repro_audit/
├── runtime_audit/
│   ├── environment_check.md
│   ├── environment_check.json
│   ├── disk_space.md
│   ├── hardware_profile.md
│   └── hardware_profile.json
└── data_audit/
    └── dataset_check.md
```

## Gate 1 Completion

After all preflight checks pass, update `state.json`:

```json
{
  "gates": {
    "gate_1_preflight": {
      "status": "passed",
      "timestamp": "<ISO 8601>",
      "evidence": "repro_audit/runtime_audit/"
    }
  },
  "phase": "preflight"
}
```

If any check fails, mark the gate as failed with the specific reason:

```json
{
  "gates": {
    "gate_1_preflight": {
      "status": "failed",
      "timestamp": "<ISO 8601>",
      "evidence": "",
      "failure_reasons": [
        "CUDA version mismatch: requires 11.8, found 11.3",
        "Dataset files missing: 3 training files not found"
      ]
    }
  }
}
```

## What This Command Does NOT Do

- Does NOT install missing packages (flags them for manual resolution)
- Does NOT download missing data (flags them for manual download)
- Does NOT modify the repository
- Does NOT run training or evaluation
- Does NOT create checkpoints or metrics

## Common Preflight Failures

| Failure | Severity | Resolution |
|---|---|---|
| CUDA version mismatch | CRITICAL | Install correct CUDA version or use container |
| Dataset files missing | CRITICAL | Download dataset from official source |
| Insufficient disk space | HIGH | Free disk space or set different paths |
| GPU not detected | CRITICAL | Check CUDA installation, driver, PyTorch build |
| Package version mismatch | HIGH | Install correct version from requirements.txt |
| Custom CUDA extension build failure | HIGH | Compile extension manually or check CUDA version |

## Next Steps

After `/repro-preflight` passes, proceed with:

1. `/repro-short-loop` — Validate the network can train on small data
2. `/repro-fit-hardware` — Get hardware fit recommendations (can be parallel with short-loop)
