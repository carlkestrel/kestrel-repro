# Repro: Open Morning Report

> Open the overnight soak test report.

## Usage

```
reproctl soak report --project . [--format markdown]
```

## Formats

- `markdown` (default) — `overnight_summary.md` to stdout
- `html` — `overnight_summary.html` to stdout
- `json` — machine-readable `final_gate.json` to stdout

## What the report contains

| Section | Contents |
|---|---|
| Executive Summary | Duration, cycles, CI success rate, bug counts |
| Verdict | SOAK_VERIFIED / REPAIRED_BUT_NOT_SOAK_VERIFIED / FAILED_WITH_UNRESOLVED_BUGS / BLOCKED_REQUIRES_REVIEW / ABORTED_FOR_HARDWARE_SAFETY |
| Startup Readiness | FAST and STRICT can-start status |
| Unresolved Issues | P0/P1 bugs with severity, bug_id, occurrences |
| Flaky Tests | Per-suite flaky rate |
| Hardware | Max GPU temp, min disk free, memory leak detection |
| Acceptance Criteria | Full breakdown of all 11 criteria |

## Verdict meanings

| Verdict | FAST can start? | STRICT can start? |
|---|---|---|
| SOAK_VERIFIED | ✅ | ✅ |
| REPAIRED_BUT_NOT_SOAK_VERIFIED | ⚠️ | ❌ |
| FAILED_WITH_UNRESOLVED_BUGS | ❌ | ❌ |
| BLOCKED_REQUIRES_REVIEW | ❌ | ❌ |
| ABORTED_FOR_HARDWARE_SAFETY | ❌ | ❌ |

## Related commands

- `Repro: View Soak Status` — check current status
- `Repro: Start Overnight Soak` — run a new soak
