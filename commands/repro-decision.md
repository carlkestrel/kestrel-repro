# /repro-decision

Produce a final Go / Pivot / No-Go report for the paper reproduction.

## Usage

```
/repro-decision
```

Should be run after all gates have been completed (or after verification reveals critical issues).

## What This Command Does

### Step 1 — Gather Evidence

Collect all evidence from previous phases:

1. Paper audit results (`repro_audit/source_audit/`)
2. Data audit results (`repro_audit/data_audit/`)
3. Metric audit results (`repro_audit/metric_audit/`)
4. Preflight results (`repro_audit/runtime_audit/`)
5. Short-loop results (`repro_audit/short_loop/`)
6. Benchmark results (`repro_audit/benchmark/`)
7. Training runs (`experiments/`)
8. Verification results (`repro_audit/evidence_chain/`)

### Step 2 — Assess Gate Completion

Review the status of each gate:

| Gate | Status | Evidence |
|---|---|---|
| Gate 0 — Paper Audit | PASSED/FAILED | `source_audit/` |
| Gate 1 — Preflight | PASSED/FAILED | `runtime_audit/` |
| Gate 2 — Short Loop | PASSED/FAILED | `short_loop/` |
| Gate 3 — Parity | PASSED/FAILED | `benchmark/` |
| Gate 4 — Full Training | PASSED/FAILED | `experiments/` |
| Gate 5 — Evidence | PASSED/FAILED | `evidence_chain/` |

### Step 3 — Compute Final Metrics

For each completed run:

```json
{
  "run_id": "<uuid>",
  "seed": 42,
  "mode": "strict_repro",
  "epochs": 300,
  "best_val_metric": 73.2,
  "best_epoch": 287,
  "test_metric": null,
  "paper_target": 73.9,
  "gap": -0.7,
  "status": "success"
}
```

For multi-seed runs:

```json
{
  "seeds": [42, 123, 2024],
  "mean_metric": 73.1,
  "std_metric": 0.3,
  "paper_target": 73.9,
  "gap": -0.8,
  "status": "success"
}
```

### Step 4 — Decision Classification

**GO** — The reproduction succeeded
- All critical gates passed
- Metrics are within acceptable tolerance of the paper
- Evidence chain is complete
- Can claim results as a successful paper reproduction

**PIVOT** — The reproduction partially succeeded but with limitations
- Critical gates passed but with caveats
- Metrics are close but outside tolerance
- Evidence chain is mostly complete
- Can report results with documented limitations

**NO-GO** — The reproduction failed
- Critical gates failed (data unavailable, metric mismatch, etc.)
- Metrics are far from paper targets
- Evidence chain is incomplete or broken
- Cannot claim results as a paper reproduction

### Step 5 — Gap Analysis

For PIVOT and NO-GO decisions, analyze the gap:

**Possible gap sources:**
- Dataset version mismatch
- Label mapping difference
- Evaluation protocol difference
- Hyperparameter difference
- Random seed sensitivity
- Hardware difference (GPU architecture)
- Metric computation difference
- Checkpoint selection difference

**For each gap source:**
1. Identify the difference
2. Estimate its impact on metrics
3. Document as a limitation in the report

### Step 6 — Generate Final Report

Produce a comprehensive report:

```markdown
# Paper Reproduction Report

## Paper
- Title: <paper title>
- arXiv: <link>
- Target: <Table X, Metric Y = value>

## Decision: GO / PIVOT / NO-GO

## Summary
<2-3 sentence executive summary>

## Gate Status
| Gate | Status | Evidence |
|---|---|---|
| Gate 0 | ✅ PASSED | source_audit/ |
| Gate 1 | ✅ PASSED | runtime_audit/ |
| Gate 2 | ✅ PASSED | short_loop/ |
| Gate 3 | ✅ PASSED | benchmark/ |
| Gate 4 | ✅ PASSED | experiments/ |
| Gate 5 | ✅ PASSED | evidence_chain/ |

## Results

### Single-Seed Results
| Run ID | Seed | Mode | Best Val mIoU | Best Epoch | Paper Target | Gap |
|---|---|---|---|---|---|---|
| <uuid> | 42 | strict_repro | 73.2 | 287 | 73.9 | -0.7 |

### Multi-Seed Results (if applicable)
| Seeds | Mean | Std | Paper Target | Gap |
|---|---|---|---|---|
| 42, 123, 2024 | 73.1 | 0.3 | 73.9 | -0.8 |

## Evidence Chain
- Commit: <hash>
- Config: <path>
- Dataset: <version>
- Seeds: <list>
- Checkpoints: <path>
- Raw metrics: <path>

## Gap Analysis
<Analysis of any gap between reproduced and paper metrics>

## Limitations
<Any known limitations of this reproduction>

## Failed Runs
| Run ID | Failure Reason | Evidence |
|---|---|---|
| <uuid> | OOM on full-PC voting | experiments/<run_id>/logs/ |

## Recommendations
<Recommendations for future work>
```

## Output Artifacts

```
repro_audit/
└── reports/
    ├── reproduction_report.md
    ├── reproduction_report.json
    ├── decision_summary.md
    └── decision_summary.json
```

## State Update

After decision is made, update `state.json`:

```json
{
  "phase": "decision",
  "decision": "GO",
  "decision_timestamp": "<ISO 8601>",
  "decision_reasons": [
    "All gates passed",
    "Metrics within 0.7% of paper target",
    "Evidence chain complete"
  ],
  "final_metrics": {
    "mean": 73.1,
    "std": 0.3,
    "gap_from_paper": -0.8,
    "seeds": [42, 123, 2024]
  }
}
```

## What This Command Does NOT Do

- Does NOT re-run any experiments
- Does NOT modify evidence or metrics
- Does NOT guarantee that a "GO" decision means perfect reproduction
- Does NOT resolve fundamental blockers (missing data, unreproducible paper)

## GO Criteria

A GO decision requires ALL of:
- [ ] All critical gates (0, 1, 2, 4, 5) passed
- [ ] Final metrics within ±1.0% of paper target (or documented justification for larger gap)
- [ ] Evidence chain is complete
- [ ] No critical failures in multi-seed runs (unless documented)

## PIVOT Criteria

A PIVOT decision applies when:
- [ ] Critical gates passed but with documented limitations
- [ ] Metrics are close to paper target but outside tolerance
- [ ] Evidence chain is mostly complete
- [ ] Gap source is identified and documented

## NO-GO Criteria

A NO-GO decision applies when:
- [ ] Any critical gate failed
- [ ] Metrics are far from paper target (>5% gap)
- [ ] Evidence chain is broken or incomplete
- [ ] Reproduction is fundamentally not possible (missing data, etc.)

---

## Final Reviewer Format (P5_T04)

When the Final Reviewer (`agents/review-auditor.md`) has produced
`REVIEW_STATE.json`, `/repro-decision` MUST also emit a **Final Reviewer
Report** alongside the Go/Pivot/No-Go verdict.

### 8-dimension scoring table

| # | Dimension | Score (1–5) | Best score (cumulative) | Notes |
|---|---|---|---|---|
| 1 | Source |  |  | |
| 2 | Data |  |  | |
| 3 | Protocol |  |  | |
| 4 | Evidence |  |  | |
| 5 | Metric |  |  | |
| 6 | Runtime |  |  | |
| 7 | Reproducibility |  |  | |
| 8 | Reporting |  |  | |

Each row is `score_this_round → best_score_cumulative`. If `best_score <
score_this_round`, the reviewer improved; if equal, no change; if
decreased, a regression is recorded in `REVIEW_STATE.open_actions`.

### Verdict with confidence

```
verdict: <GO | PIVOT | NO-GO>
confidence: <0.0 - 1.0>          # probability the verdict is correct given current evidence
supporting_dimensions: [<ids with score >= 4>]
blocking_dimensions:   [<ids with score <= 2 or any blocker action open>]
justification:         "<one paragraph>"
```

### Decision rule

- **GO** if all 8 dimensions ≥ 4 AND no blocker action is open AND
  confidence ≥ 0.7.
- **PIVOT** if 6+ dimensions ≥ 3 AND no more than 1 blocker AND
  confidence ≥ 0.5.
- **NO-GO** otherwise.

A NO-GO may be reversed only by running another `/repro-review` round and
re-evaluating. The decision itself is immutable; corrections are
appended as new decision rows.

---

## Pre-conditions (P6_T03)

`/repro-decision` MUST refuse to issue any verdict until **all four** of
the following are true:

| # | Pre-condition | How it is checked |
|---|---|---|
| 1 | **Baseline VERIFIED** | A `gate_approval` row exists in `DECISION_LOG.md` with `decision_type=gate_approval`, `links` referencing `experiments/<baseline-run>/`, and `reason` containing the word "baseline". If only PARTIAL, the verdict must be PIVOT (not GO). If FAIL or missing entirely, refuse to render a verdict. |
| 2 | **All numbers have a `source:` citation** | The traceability check from `/repro-report` (P6_T02) reports 0 missing citations. If any section has missing sources, list them and refuse a GO verdict; PIVOT may still be issued with a note. |
| 3 | **Improvement experiments are separated** | Any row in `experiment_tracker.csv` with `module ∈ {M6, M10}` (ablations or approved extensions) must live in `experiments/improvements/` (not `experiments/<baseline-run>/`). If not, refuse a GO verdict. |
| 4 | **User approval** | The user must explicitly invoke `/repro-decision` AND sign the verdict block. A "draft" verdict rendered for inspection is allowed without a signature, but a published GO/PIVOT/NO-GO verdict cannot be written into `REVIEW_STATE.json` or `DECISION_LOG.md` without a signature row. |

### Refusal sequence

When any pre-condition fails, `/repro-decision`:

1. Prints which pre-conditions failed and why (with paths).
2. Writes a `note` row into `DECISION_LOG.md` (not `gate_approval` —
  this is informational).
3. Exits with code `2`.
4. Returns the user to `/repro-report` or `/repro-review` to resolve.

---

## Repo decision taxonomy (P11_T06)

When `/repro-decision` runs on a *candidate repository* (not yet
adopted), it MUST choose one of 4 decisions based on **actual file
evidence** — never on hearsay:

| Decision | Trigger | Output |
|---|---|---|
| **Accept** | Official repo with pinned commit, license OK, ≥1 verified run, dataset matches paper | row in `DECISION_LOG.md` (decision_type=`repo_accept`); candidate cloned into `external/<repo>/<sha>/` |
| **Adapt** | Repo runs but data or eval diverges; partial fit | row in `DECISION_LOG.md` (decision_type=`repo_adapt`); plan notes the divergence |
| **Reference Only** | Repo is informative but we will not use it for the baseline run | row in `DECISION_LOG.md` (decision_type=`repo_reference_only`); pointer in §1.3 of `templates/project_memory.md` |
| **Reject** | Repo license incompatible, or unmaintained >2 years, or metrics don't reproduce | row in `DECISION_LOG.md` (decision_type=`repo_reject`); reason logged in `evolution_failures.jsonl` |

The decision MUST cite the exact files inspected (e.g.,
`README.md §3.2` for license, `configs/<dataset>.yaml` for data
divergence).

## Reproduction decision taxonomy (P11_T06)

When `/repro-decision` runs on the **completed reproduction**, it MUST
choose one of 4:

| Decision | Trigger |
|---|---|
| **Reproduced** | All 8 review dimensions ≥ 4 AND final metrics within tolerance AND evidence chain complete |
| **Partial** | Critical gates passed AND metric gap ≤ 5% AND evidence chain mostly complete AND gap source identified |
| **Not Reproduced** | Critical gate failed OR metric gap > 5% OR evidence chain broken |
| **Protocol Unclear** | Paper protocol is ambiguous on a critical step and we cannot ask the authors; we report what we tried and stop |

A `Protocol Unclear` decision MUST include a `paper_protocol_questions.md`
file with the exact open questions.
