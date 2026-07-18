---
description: Run the read-only review-auditor across all 8 dimensions, generate actions, and feed them into /repro-decision.
---

# /repro-review

> **Five-step review loop**. Each round writes 2 markdown files + 1 JSON.
> All work happens inside `.execution/review/`. No other path is touched.

## Usage

```
/repro-review                              # full 8-dim round
/repro-review --round N                    # annotate existing round N
/repro-review --dimension evidence         # single dimension
/repro-review --since round_K              # incremental review
/repro-review help                         # this file
```

## 5-step flow

| Step | Reads | Writes | Output |
|---|---|---|---|
| **1. Invoke reviewer** | `.execution/review/REVIEW_STATE.json` (last_round + open_actions) | — | list of dimensions to revisit |
| **2. Read round_N_raw** | all 8 dimensions × paper + repo + data + telemetry + matrix | `.execution/review/round_<N+1>_raw.md` | per-dimension notes |
| **3. Generate actions** | `round_<N+1>_raw.md` | `.execution/review/round_<N+1>_actions.md` | action list, severity-tagged |
| **4. Update REVIEW_STATE** | round_<N+1> actions + previous state | `.execution/review/REVIEW_STATE.json` | best_scores_per_dimension, open_actions |
| **5. Execute (or queue) actions** | action list | (depends on action) | either done, or queued for next round |

## Pre-conditions

- The previous phase (P4_monitor) is `PASS` OR a justified override row exists.
- `REVIEW_STATE.json` either does not exist (round 1) or `last_round`
  matches the highest existing `round_N_raw.md`.
- All 8 dimensions are inspectable: no missing evidence paths.

## Output

```
[repro-review] round 1, 8 dimensions ............................... START
[repro-review] step 2/5 read round_1_raw.md ......................... OK (8 sections, 1 [unsupported])
[repro-review] step 3/5 generate round_1_actions.md ................. OK (4 actions: 1 blocker, 2 major, 1 minor)
[repro-review] step 4/5 update REVIEW_STATE.json .................... OK (last_round=1, best_scores={source:5,...})
[repro-review] step 5/5 execute actions ............................. 3/4 done, 1 queued for next round
[repro-review] decision = D__ → DECISION_LOG.md
```

## Round file templates

### `round_<N>_raw.md`

```markdown
# Review Round <N> — Raw Notes

## 1. Source (score: 5)
- Paper title matches arXiv 2401.12345
- Author repo: github.com/foo/bar @ commit abc123 (matches research_contract §2)
- License: MIT — compatible with reproduction

## 2. Data (score: 4)
- MD5 of all 6 files matches
- File count: train=204, val=42, test=80 — matches data_contract.md
- ⚠ Split boundary: paper says "Area 1-5 train" but our root has Areas 2-6 (suspected documentation drift)
...
```

### `round_<N>_actions.md`

```markdown
# Round <N> Actions

| # | Severity | Dimension | Action | Owner | Status |
|---|---|---|---|---|---|
| A1 | blocker | data | Confirm Area split boundary against paper §4.2 | human | open |
| A2 | major | metric | Recompute mIoU with ignore-label list from §A.1 | agent | done |
| A3 | major | runtime | Investigate GPU util dip at epoch 80 | agent | open |
| A4 | minor | reporting | Add decision log D__ reference to §8 of report | agent | done |
```

## Failure modes

- `[unsupported]` claims appear → the reviewer's confidence is recorded as
  low; `/repro-decision` will down-grade the verdict.
- `REVIEW_STATE.json` drift → delete it and re-run from round 1; the
  reviewer will rebuild it. Previous `round_*_actions.md` files are
  preserved for forensics.
- A blocker action remains open → `/repro-launch` and `/repro-decision`
  will refuse a Go verdict until it closes.

## Implementation

`scripts/reproctl.py review [--round N] [--dimension D]` (optional helper).