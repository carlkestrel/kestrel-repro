# /repro-short-loop

Run staged short-loop validation (L0–L3) to verify the network can train before full training.

## Usage

```
/repro-short-loop [level=<L0|L1|L2|L3|all>] [config=<path>]
```

Defaults to running all levels (L0–L3) in sequence.

## What This Command Does

### L0 — Real Forward/Backward Smoke Test

**Purpose:** Verify the network can actually run forward and backward passes.

Steps:
1. Load one batch of real data (not synthetic)
2. Run forward pass — verify no NaN, no crash
3. Run backward pass — verify gradients are computed
4. Verify gradient norms are reasonable (not all zeros, not inf)

Pass criteria:
- Forward pass completes without error
- Backward pass completes without error
- All parameters have non-zero gradients
- No NaN or Inf in any tensor

Script: `scripts/reproctl.py run-l0`
Output: `repro_audit/short_loop/l0_smoke.md`

### L1 — Fixed-Batch Overfit

**Purpose:** Verify the network can memorize a single batch of random labels.

Steps:
1. Take one batch of real data
2. Overwrite labels with random integers in valid range
3. Train for 100 steps (or until loss < 0.01)
4. Verify training loss decreases toward zero
5. Verify predictions approach the random labels

Pass criteria:
- Training loss decreases consistently
- Final loss < 0.1 (network memorized random labels)
- No NaN or divergence
- If L1 fails, the network architecture or loss is broken

Script: `scripts/reproctl.py run-l1`
Output: `repro_audit/short_loop/l1_overfit.md`

### L2 — Mini-Dataset End-to-End Loop

**Purpose:** Verify the full training pipeline works end-to-end on a small dataset.

Steps:
1. Create a mini dataset (e.g., 5% of training data, stratified by class)
2. Train for 3 epochs on the mini dataset
3. Evaluate on the mini validation set
4. Verify loss decreases epoch-over-epoch
5. Verify evaluation metrics are computed correctly
6. Verify checkpoint saving and loading works

Pass criteria:
- Loss decreases each epoch
- Evaluation completes without error
- Metrics are in a reasonable range (not NaN, not 0.0 unless expected)
- Checkpoint can be loaded and produces identical metrics
- No data augmentation inconsistencies between train and eval

Script: `scripts/reproctl.py run-l2`
Output: `repro_audit/short_loop/l2_mini_loop.md`

### L3 — Checkpoint Resume Comparison

**Purpose:** Verify that resuming from checkpoint produces identical results.

Steps:
1. Train for N steps, save checkpoint at step N
2. Load checkpoint, resume training for M more steps
3. Compare loss curves: checkpointed run vs. continuous run
4. Verify final metrics are within numerical tolerance

Pass criteria:
- Loss curves match within tolerance (max 0.1% deviation from step N onward)
- Final metrics match within tolerance
- No state is lost during checkpoint save/load (dropout RNG, optimizer state, etc.)

Script: `scripts/reproctl.py run-l3`
Output: `repro_audit/short_loop/l3_checkpoint_resume.md`

## Output Artifacts

```
repro_audit/
├── short_loop/
│   ├── l0_smoke.md
│   ├── l0_smoke.json
│   ├── l1_overfit.md
│   ├── l1_overfit.json
│   ├── l2_mini_loop.md
│   ├── l2_mini_loop.json
│   ├── l3_checkpoint_resume.md
│   └── l3_checkpoint_resume.json
└── raw_metrics/
    ├── l0_smoke.csv
    ├── l1_overfit.csv
    ├── l2_mini_loop.csv
    └── l3_checkpoint_resume.csv
```

## Gate 2 Completion

After all L0–L3 checks pass, update `state.json`:

```json
{
  "gates": {
    "gate_2_short_loop": {
      "status": "passed",
      "timestamp": "<ISO 8601>",
      "evidence": "repro_audit/short_loop/",
      "details": {
        "l0_smoke": "passed",
        "l1_overfit": "passed",
        "l2_mini_loop": "passed",
        "l3_checkpoint_resume": "passed"
      }
    }
  },
  "phase": "short_loop"
}
```

## What This Command Does NOT Do

- Does NOT run full training
- Does NOT evaluate on the test set
- Does NOT modify the repository code
- Does NOT use the full dataset (only mini splits)
- Does NOT claim any paper-level results

## Running Individual Levels

To run a specific level:
```
/repro-short-loop level=L0
/repro-short-loop level=L1
/repro-short-loop level=L2
/repro-short-loop level=L3
```

## Common Short-Loop Failures

| Failure | Level | Symptom | Resolution |
|---|---|---|---|
| Forward pass NaN | L0 | NaN in output | Check input data, reduce learning rate, check normalization |
| Backward pass crash | L0 | RuntimeError in backward | Check loss function, check gradient computation |
| No gradient | L0 | All-zero gradients | Check `requires_grad`, check loss computation |
| Cannot overfit | L1 | Loss doesn't decrease | Increase learning rate, check loss function, check model |
| DataLoader broken | L2 | Cannot load mini dataset | Check dataset class, check data paths |
| Checkpoint state loss | L3 | Curves diverge after resume | Fix dropout RNG, optimizer state, batch norm state |

## Next Steps

After `/repro-short-loop` passes, proceed with:

1. `/repro-benchmark` — Measure hardware throughput and validate parity
2. `/repro-launch` — Start full training (only after all previous gates pass)
