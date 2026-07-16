# Bug-002: Hardcoded metric 73.5% in narrative_report.md

## Triage

- **Report:** `acceptance_summary.md` / failed_tests.md
- **File:** `templates/narrative_report.md` line 30
- **Evidence:** `metric: 73.5%` in traceability rule example
- **Severity:** MEDIUM

## Expected vs Actual

| | Value |
|---|---|
| Expected | `metric: [METRIC]` (placeholder) or `metric: <value from raw_metrics.json>` |
| Actual | `metric: 73.5%` (concrete number without source:) |

## Reproduction

Status: **REPRODUCED**

```bash
$ grep -n "73\.5" templates/narrative_report.md
30:metric: 73.5%
```

The line is inside the Traceability Rule illustration block (§ Traceability rule, lines 27-37).

## Root Cause

The Traceability Rule section in `templates/narrative_report.md` uses a concrete example number `73.5%` to demonstrate the required format:

```
metric: 73.5%
source: experiments/r-001/metrics/eval_results.json:line_42
paper:  Table 3, row "Ours (KPConv)"
gap:    -0.4 pp (within ±0.5 pp tolerance)
```

While this is in a "how to format" illustration (not a live result section), it violates the hard rule that "every number must have a source:". If a user copies this template without replacing the example, the resulting report would contain an unattributed number.

## Regression Test

Added `tests/test_hardcoded_metrics.py`:
- Greps for `\d+\.\d+%` in narrative_report.md
- Should find 0 matches for concrete metric values without source: annotation
- Before fix: finds 1 match (73.5%)
- After fix: finds 0 matches

## Fix

Replace `73.5%` with `[METRIC]` in the traceability rule example.

## Verification

```
$ python3 tests/test_hardcoded_metrics.py
test_hardcoded_metrics: PASS (0 hardcoded metrics found in narrative_report.md)
```

## Root Cause File

`.repair/root_causes/BUG-002_root_cause.md`
