---
description: Generate the Claim-Evidence matrix and Experiment Plan from the Research Contract, then initialize the experiment tracker.
---

# /repro-plan

> **Discoverable Cursor command**. Reads `templates/research_contract.md`
> (after human approval), materializes the matrix + plan, initializes the
> tracker, and switches the project into P2 (claim_evidence) phase.

## Usage

```
/repro-plan                       # run the full 5-step flow
/rerepro-plan status              # show what would be created (dry-run)
/repro-plan help                  # this file
```

## 5-step flow

| Step | Reads | Writes | Failure |
|---|---|---|---|
| **1. Read contract** | `templates/research_contract.md`, `.repro/repro_audit/STATE.json` | — | abort if contract §8 (Human Confirmation) not signed |
| **2. Generate matrix** | `templates/claim_evidence_matrix.md` | `experiments/claim_evidence_matrix.md` | abort if paper has zero claims |
| **3. Generate plan** | `templates/experiment_plan.md` | `experiments/EXPERIMENT_PLAN.md` | warn if M0 already PASS (skip) |
| **4. Init tracker** | `templates/experiment_tracker.csv` | `experiments/experiment_tracker.csv` | abort if file already has rows |
| **5. Phase switch** | `task_graph.yaml` | `.execution/execution_state.json` | abort if P1 not PASS |

A `D__` row is appended to `DECISION_LOG.md` at the end of each step that
mutates state.

## Pre-conditions

- `templates/research_contract.md` §8 (Human Confirmation) is signed.
- `project_mode == 'reproduce'`.
- `experiments/claim_evidence_matrix.md` does **not** already exist.
- `experiments/EXPERIMENT_PLAN.md` does **not** already exist.
- `experiments/experiment_tracker.csv` has no data rows (header-only is OK).

## Output

After a successful run:

```
[repro-plan] step 1/5 read_contract       OK (signed by <name>)
[repro-plan] step 2/5 generate_matrix     OK (experiments/claim_evidence_matrix.md, 7 claims)
[repro-plan] step 3/5 generate_plan       OK (experiments/EXPERIMENT_PLAN.md, 5 experiments)
[repro-plan] step 4/5 init_tracker        OK (experiments/experiment_tracker.csv)
[repro-plan] step 5/5 phase_switch        OK (P2_claim_evidence → IN_PROGRESS)
[repro-plan] decision = D__ → DECISION_LOG.md
```

## Implementation

Implemented via `reproctl.py run repro-plan` (calls
`_generate_matrix_from_contract`, `_generate_plan_from_matrix`,
`_init_tracker_from_plan`, `_set_phase(P2_claim_evidence)`).

## Failure modes

- `contract §8 not signed` → open `templates/research_contract.md`, fill the
  approval box, then retry.
- `matrix already exists` → either delete it (after writing a `rollback`
  decision row) or open the existing file to continue editing.
- `tracker has rows` → either archive to `experiments/archive/` and start
  fresh, or resume editing the existing tracker.