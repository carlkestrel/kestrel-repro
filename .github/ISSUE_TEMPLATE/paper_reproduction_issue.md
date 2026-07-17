---
name: Paper Reproduction Issue
about: Report a failure or discrepancy in reproducing a research paper
title: '[REPRO] '
labels: reproduction, reproduction-gate
assignees: ''
---

## Paper Citation

**Title:**
**Authors:**
**Venue/Year:**
**arXiv/Link:**

## Target Repository

**Repository URL:**
**Commit/Version:**
**Last Tested By:**

## Gate Status

Report the status of each reproduction gate (A-F):

| Gate | Status | Notes |
|------|--------|-------|
| A: Setup | :white_check_mark: Pass / :x: Fail / :warning: Partial |
| B: Data | :white_check_mark: Pass / :x: Fail / :warning: Partial |
| C: Train | :white_check_mark: Pass / :x: Fail / :warning: Partial |
| D: Evaluate | :white_check_mark: Pass / :x: Fail / :warning: Partial |
| E: Metrics | :white_check_mark: Pass / :x: Fail / :warning: Partial |
| F: Reproduce | :white_check_mark: Pass / :x: Fail / :warning: Partial |

## Evidence Chain Completeness

Check the evidence provided for each claim:

- [ ] Code runs without errors
- [ ] Training produces expected loss curves
- [ ] Evaluation produces results
- [ ] Metrics match claimed values
- [ ] Artifacts are saved and verifiable

**Missing Evidence:**

## Metrics Table

Compare expected vs actual metrics:

| Metric | Paper Claim | Reproduction | Delta | Notes |
|--------|-------------|--------------|-------|-------|
|        |             |              |       |       |

## Reproduction Environment

**OS:**
**Python Version:**
**CUDA/GPU:**
**Key Dependencies:**
```
# List pip packages with versions
```

## Detailed Logs

```python
# Paste training logs, evaluation output, or relevant traces
```

## Analysis

Describe the discrepancy between expected and actual results. Is this a:
- :x: **Critical failure** - Code does not run or produces fundamentally wrong results
- :warning: **Significant gap** - Results differ substantially from paper claims
- :warning: **Minor difference** - Results are close but not exact

## Questions / Open Items

- Question 1?
- Question 2?
