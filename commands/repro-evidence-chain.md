---
description: Verify the 5-link evidence chain between raw artifacts and reported numbers.
---

# /repro-evidence-chain

> A read-only audit that walks the 5 edges of the evidence chain and
> confirms every reported number in `templates/narrative_report.md`
> traces back to a real artifact on disk.

## Usage

```
/repro-evidence-chain
/repro-evidence-chain --report <path-to-narrative_report.md>
/repro-evidence-chain --strict
/repro-evidence-chain help
```

## 5-link verification

| # | Edge | What's checked | Failure mode |
|---|---|---|---|
| 1 | `run_id` ↔ `run_manifest` | Every `run_id` in the report exists in some `experiments/<run>/run_manifest.json` | REFUSE if any orphan run_id |
| 2 | `raw_metrics` ↔ `config + ckpt + env` | Every reported metric value appears verbatim in `experiments/<run>/raw_metrics.json` AND that raw file's `git_commit`, `checkpoint_sha256`, `env_fingerprint` all resolve to existing files | REFUSE if any number is phantom |
| 3 | `confusion_matrix` ↔ `predictions` | For any `confusion_matrix.json`, summing rows reproduces the per-class totals within 1e-6 | REFUSE if CM row sum ≠ predictions |
| 4 | Training curve ↔ raw log | Plotted values in `experiments/<run>/training_curve.png` must equal the last line of `experiments/<run>/logs/train.log` for each epoch | REFUSE if any curve point differs |
| 5 | Checkpoint hash ↔ training log | The `sha256` recorded in `experiments/<run>/raw_metrics.json` matches the on-disk `.pt`/`.bin` file hash AND matches the SHA quoted in the training log when the checkpoint was written | REFUSE if any drift |

## Output

```
[repro-evidence-chain] edge 1/5 run_id↔run_manifest ....... 7/7 ✓
[repro-evidence-chain] edge 2/5 raw_metrics↔config+ckpt+env 12/12 ✓
[repro-evidence-chain] edge 3/5 confmat↔predictions ....... 2/2 ✓
[repro-evidence-chain] edge 4/5 curve↔log ................. 8/8 ✓
[repro-evidence-chain] edge 5/5 ckpt_hash↔log .............. 3/3 ✓
[repro-evidence-chain] verdict = CLEAN (5/5 edges, 32/32 checks)
```

If any edge fails, the output includes:

- the file path
- the offending line
- the expected vs. actual value
- an "action:" suggestion (e.g., `action: re-verify run <run_id>`)

## Failure modes

- **Missing file** — REFUSE; do not attempt to repair. The user must
  decide whether to re-run or to mark the run as PARTIAL.
- **Drifted hash** — REFUSE; do not silently re-hash. The original
  checkpoint must be restored or re-trained.
- **`--strict`** — same as default; the command is always strict.

## Implementation

`scripts/artifact_verify.py` provides the underlying primitives
(`verify_paper_identity`, `verify_commit_sha_pinned`,
`verify_license`, `verify_checkpoint_source`).

## What this command does NOT do

- Does NOT modify any artifact.
- Does NOT auto-correct mismatches.
- Does NOT mark runs as PARTIAL on its own — that is the user's call.