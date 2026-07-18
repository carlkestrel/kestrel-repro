# Human Checkpoints — 12 Mandatory Pause-and-Ask Behaviors

> **Why this file exists**: certain actions are *silently catastrophic* for a
> reproduction. They look harmless in isolation but invalidate the entire
> claim-evidence chain. This list is the canonical "stop and ask the human"
> registry. `scripts/reproctl.py human-checkpoint` enforces it before any
> `/repro-launch`.

> **Rule**: a behavior not on this list is not necessarily allowed — see
> `templates/research_contract.md` §7 (Allowed / Forbidden) for the per-project
> scope. This file defines the **always-forbidden** baseline.

---

## The 12 items (do not paraphrase, do not reorder)

| # | Behavior | Why it must pause | What to do instead |
|---|---|---|---|
| 1 | **Synthesize / augment data beyond what the paper describes** | Distorts the dataset claim; numbers stop being comparable to the paper. | Cite the paper section that authorizes the augmentation; otherwise revert. |
| 2 | **Change dataset split (train/val/test boundaries)** | Changes the metric semantics — Area-6 vs Area-5 are different evaluations in S3DIS. | Stick to paper split; if a different split is needed, file a scope_change. |
| 3 | **Change metric definition** (IoU formula, mIoU class averaging, ignore-label list) | Same numbers, different meaning → false PASS. | Reuse `data_contract.md` §Metric Definition verbatim. |
| 4 | **Reduce model / batch / resolution to fit OOM** | Quietly degrades the protocol; "PASS" no longer comparable. | Try smaller batch with same model first; otherwise file a `risk_override` row. |
| 5 | **Modify loss function** (reweighting, adding auxiliary losses) | Changes what the model is optimizing; result is no longer a reproduction. | Use the paper's loss exactly; if a regularization is needed, document as out-of-scope. |
| 6 | **Use a different physical batch size than the paper** | Affects BN statistics, learning-rate scaling, and convergence path. | Match paper, then scale LR proportionally (cite the formula used). |
| 7 | **Enable AMP / fp16 when paper used fp32** | Different numerics → different convergence; reproducibility audit (M8) will fail. | Keep fp32 unless paper explicitly uses AMP; otherwise override + document. |
| 8 | **Substitute a different pretrained checkpoint** | Pretraining is part of the recipe; swapping silently = a different experiment. | Use the paper-specified checkpoint or train from scratch. |
| 9 | **Selectively report results** (cherry-pick seeds, drop outliers) | Reproducibility is *about* the variance; cherry-picking is fabrication. | Report all runs; if a seed fails, log it and report both mean±std and median. |
| 10 | **Switch to `extend` mode** (start adding new claims) without prior `evolve` approval | New claims pollute the matrix; `P5_review` cannot separate old from new. | File a `gate_approval` row with explicit human sign-off on the new scope. |
| 11 | **Exceed compute budget** (wall-clock or GPU-hours) without a new decision row | Budget overrun is a contractual violation; the project's priority is to *finish* the contracted scope. | Stop, write a `risk_override` row, request human approval to extend. |
| 12 | **Report a number you cannot re-derive from logs / artifacts** | If you can't recompute it, you can't defend it. Every value in `claim_evidence_matrix.md` must trace to a logged metric file. | Re-derive or mark the row `FAIL` with a `Gap` and `Explanation`. |

---

## Enforcement

`scripts/reproctl.py human-checkpoint` reads `.repro/repro_audit/STATE.json`
and:

1. Looks up `flags.HUMAN_CHECKPOINT` (default `true`).
2. If `true`: emits the 12-item list, requires the human to type
   `APPROVE <reason>` interactively (or supply a `--approved-by <name>` flag
   + prior decision row), and exits non-zero on refusal.
3. If `false`: emits a warning, logs a `risk_override` row, and exits zero.

## Per-project augmentation

Projects MAY extend this list in `templates/research_contract.md` §7
"Forbidden" but MUST NOT remove or relax items. Removing an item requires
a new contract revision + a decision row of type `risk_override` with
explicit human sign-off.

## Decision row shape

```
| D__ | <ts> | human | P3_human_checkpoint | <task_id> | risk_override | <item #> → approved_with_conditions | <reason> | evidence/<path> |
```