# /repro-launch

Launch full training for deep learning paper reproduction.

## Usage

```
/repro-launch [mode=<strict_repro|optimized_repro_safe>] [seeds=<n>] [epochs=<n>]
```

Requires that Gates 0, 1, and 2 (and Gate 3 if using optimized mode) have all passed.

## What This Command Does

### Gate Verification

Before launching, `reproctl.py` checks:

```
python scripts/reproctl.py can-launch --mode=<mode>
```

If any required gate is not passed, `reproctl` refuses to launch and reports which gate failed:

```
ERROR: Cannot launch full training. Required gates not passed:
  - gate_1_preflight: FAILED (dataset files missing)
  - gate_2_short_loop: PENDING (L0-L3 not completed)
```

### Launch Preparation

1. **Record exact configuration:**
   - Git commit hash
   - Config file (with all overrides)
   - Random seed(s)
   - Environment snapshot (Python, PyTorch, CUDA versions)
   - Command with all arguments
   - Working directory

2. **Set up output directories:**
   ```
   experiments/
   └── <run_id>/
       ├── config/
       │   ├── original.yaml
       │   └── override.yaml
       ├── checkpoints/
       │   └── epoch_*.pth
       ├── logs/
       │   ├── train.log
       │   ├── eval.log
       │   └── events/  (TensorBoard)
       ├── metrics/
       │   ├── raw_metrics.json
       │   └── eval_results.json
       └── artifacts/
           ├── environment.txt
           └── command.sh
   ```

3. **Create run record:**
   ```json
   {
     "run_id": "<uuid>",
     "timestamp": "<ISO 8601>",
     "commit": "<git hash>",
     "branch": "<branch>",
     "config": "<path>",
     "seed": <seed>,
     "mode": "<strict_repro|optimized_repro_safe>",
     "epochs": <n>,
     "command": "<full command>",
     "phase": "training"
   }
   ```

### Training Execution

1. **Single-seed run (default):**
   ```
   python scripts/reproctl.py launch --mode=strict_repro --seed=42
   ```

2. **Multi-seed run:**
   ```
   python scripts/reproctl.py launch --mode=strict_repro --seeds=3
   # Seeds: 42, 123, 2024
   ```

3. **With custom epochs:**
   ```
   python scripts/reproctl.py launch --mode=strict_repro --epochs=300
   ```

### Checkpointing

- Save checkpoint every N epochs (configurable, default: 10)
- Save best checkpoint based on validation metric
- Save last checkpoint
- Record checkpoint metadata (epoch, step, metric values, loss)

### Metrics Logging

- Log raw metrics at every training step (loss, lr, grad_norm)
- Log evaluation metrics at every eval epoch (per-class and mean)
- Log system metrics (GPU util, memory, throughput) every N steps
- Preserve all logs — never filter or discard

### Run Manifest Updates

After each run, update `runs_manifest.csv`:

```csv
run_id,timestamp,commit,seed,mode,epochs,best_val_metric,best_epoch,status,evidence
<uuid>,2024-03-15T10:00:00Z,<hash>,42,strict_repro,300,73.2,287,success,experiments/<run_id>/
```

## Output Artifacts

```
experiments/
└── <run_id>/
    ├── config/
    ├── checkpoints/
    ├── logs/
    ├── metrics/
    └── artifacts/

repro_audit/
├── runs_manifest.csv
└── training_runs/
    └── <run_id>/
        └── run_record.json
```

## Gate 4 Completion

After training completes, update `state.json`:

```json
{
  "gates": {
    "gate_4_full_training": {
      "status": "passed",
      "timestamp": "<ISO 8601>",
      "evidence": "experiments/<run_id>/"
    }
  },
  "phase": "full_training"
}
```

## What This Command Does NOT Do

- Does NOT skip any gate requirements
- Does NOT use cherry-picked checkpoints
- Does NOT discard failed runs
- Does NOT modify the model architecture
- Does NOT change hyperparameters from the paper's specification
- Does NOT use test set for validation or checkpoint selection

## Monitoring Training

During training, monitor:
- Loss curves (should decrease, no NaN)
- Validation metrics (should improve, no divergence)
- GPU utilization (should be stable, not fluctuating wildly)
- Memory usage (should be stable, no leaks)

Use `scripts/benchmark_runtime.py` for ongoing profiling during training.

## What If Training Fails

1. **Do NOT delete the failed run.**
2. **Record the failure reason** in `runs_manifest.csv`.
3. **Preserve all logs and checkpoints** from the failed run.
4. **Diagnose the failure** using `scripts/reproctl.py diagnose`.
5. **Fix the issue** (environment, data, code bug).
6. **Start a new run** — do not resume from a failed run's checkpoint.
7. **Document the failure** in the final report.

## Multi-Seed Requirements

If the paper reports mean ± std across multiple seeds:
- Run at least 3 seeds (more if variance is high)
- All seeds must pass short-loop (Gate 2) first
- Report mean and std in the final evidence
- Do NOT drop outlier seeds without documented justification

## Next Steps

After `/repro-launch` completes:

1. `/repro-verify` — Verify metrics are reproducible from checkpoints
2. `/repro-decision` — Produce Go/Pivot/No-Go report

## reproctl Launch Blocking

`reproctl.py` enforces this launch sequence. Attempting to run training without passing required gates will produce:

```
$ python scripts/reproctl.py launch
[REPROCTL] Gate check FAILED:
  gate_0_paper_audit: PENDING
  gate_1_preflight: PASSED
  gate_2_short_loop: FAILED (L1 overfit did not converge)

Cannot launch full training. Resolve gate failures before proceeding.
[REPROCTL] Refusing to launch. Exit code: 1
```

---

## Pre-launch Checks (P3 hardening)

In addition to Gate 0/1/2 enforcement above, `/repro-launch` runs three
**pre-launch checks** before any training command is dispatched. These
correspond to the Phase-3 hardening (`P3_human_checkpoint` phase) and the
`templates/human_checkpoints.md` 12-item list.

The three checks are: **Human Checkpoint**, **Compute Budget**, and
**Project Mode (not `extend`)**. Each is described below.

### Check 1 — Human Checkpoint (`human-checkpoint`)

`reproctl.py` invokes:

```
python scripts/reproctl.py human-checkpoint --action check
```

Behavior:
- If `flags.HUMAN_CHECKPOINT=true` (default): the command exits 1 and
  prints the 12-item list. `/repro-launch` aborts.
- If `flags.HUMAN_CHECKPOINT=false` and a `risk_override` decision row
  exists in `DECISION_LOG.md`: the check passes.
- If `flags.HUMAN_CHECKPOINT=false` *without* a prior `risk_override`
  row: `/repro-launch` aborts with `[preflight] flags changed but no
  decision row — refusing`.

### Check 2 — Compute Budget (`compute-budget`)

Reads `templates/research_contract.md` §6 + `.execution/execution_state.json`
for cumulative GPU-hours spent so far. Aborts if:

- `cumulative_gpu_hours + this_run_estimate > wall-clock / GPU budget`, OR
- The training run has no `expected_duration_hours` field (config incomplete).

On abort, `/repro-launch` writes a `risk_override` row template into
`DECISION_LOG.md` (still empty) so the human can edit it before approving.

### Check 3 — Project Mode (`mode != extend`)

Reads `STATE.json.project_mode`:

- `reproduce` → proceed.
- `plan` → abort with "still in plan mode; complete P3 first".
- `extend` → only proceed if a `VERIFIED` marker is present in
  `DECISION_LOG.md` (i.e., a human has explicitly approved leaving the
  reproduction scope). Otherwise abort.

### Abort sequence

When any check fails, `/repro-launch`:

1. Does **not** invoke `reproctl launch`.
2. Prints which check failed and the precise blocking condition.
3. Exits with code `1` and writes a `note` row (not `checkpoint`) into
  `DECISION_LOG.md` so the abort is auditable.
4. Returns the user to `/repro-plan` or `/repro-short-loop` for resolution.
