---
description: Transition from reproduce mode to extend mode after a baseline is verified.
---

# /research-extend

> Switches the project from `reproduce` mode to `extend` mode and creates
> an isolated `experiments/improvements/` directory tree so that
> improvement experiments can never contaminate the baseline numbers.

## Usage

```
/research-extend                                            # check pre-conditions only
/research-extend --approve "<reason>" --approved-by <name>   # request mode switch
/research-extend help                                       # this file
```

## 3 pre-conditions (ALL must be true)

| # | Pre-condition | Check |
|---|---|---|
| 1 | **`phase == verification`** | `STATE.json.phase` reads `verification`. |
| 2 | **`gate_5_evidence.passed`** | The evidence-chain gate is `passed` in `STATE.json.gates`. |
| 3 | **User explicit approval** | The command was invoked with `--approve "<reason>"` AND `--approved-by <name>` AND a `gate_approval` decision row exists referencing `experiments/<baseline-run>/`. |

If any pre-condition fails, the command aborts with a numbered list of
which pre-conditions failed and how to fix them.

## Mode switch

On approval:

1. `STATE.json.project_mode` → `extend`.
2. A `mode_switch` row is appended to `DECISION_LOG.md`:
   ```
   | D__ | <ts> | human | P7_command_agent | P7_T01 | mode_switch | reproduce → extend | <reason from --approve> | evidence/<baseline> |
   ```
3. `experiments/improvements/` directory is created (if missing) with a
   README explaining what may live there.
4. `decision_type=scope_change` row is appended recording the directory
   creation.
5. `human-checkpoint --action check` is re-run; if `HUMAN_CHECKPOINT`
   is still `true`, the new directory is created but the user is warned
   that any non-trivial improvement will be blocked until the flag is
   flipped.

## Output

```
[research-extend] pre-conditions ........................... 3/3 PASS
[research-extend] state.project_mode: reproduce → extend ..... OK
[research-extend] experiments/improvements/ .................. OK (created)
[research-extend] decision = D__ → DECISION_LOG.md
```

## What may live in `experiments/improvements/`

- M6 ablation rows whose `parent_run_id` points at a baseline run.
- M10 approved-extension rows from `research_contract.md` §10.
- Standalone scripts under `experiments/improvements/scripts/`.

What may **NOT** live there:
- Baseline retraining artifacts (those stay in `experiments/<run_id>/`).
- Any modification to `experiments/<baseline-run>/`.
- Any decision that re-runs a baseline run with different settings.

## Failure modes

- `phase != verification` → the project has not finished reproducing
  the paper; reproduce first.
- `gate_5_evidence not passed` → run `/repro-review` and re-evaluate.
- `--approved-by` missing → refuse; this command cannot be silently
  auto-approved.
- `experiments/improvements/` already exists with non-trivial content
  → emit warning + ask for `--force` (which records another
  `scope_change` row).

## Implementation

`scripts/reproctl.py research-extend --approve "<r>" --approved-by <n>`.