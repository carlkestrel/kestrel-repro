---
description: Record a new failure case in the failure_case_report.md with automatic classification into 已修复 / 已规避 / 未验证.
---

# /repro-failure

> Append a single new failure case row to
> `templates/failure_case_report.md`. The command does the four-column
> "现象→影响→修复→证据" structuring and the
> 已修复/已规避/未验证 classification automatically.

## Usage

```
/repro-failure log
/repro-failure log --category fixed
/repro-failure log --category worked_around
/repro-failure log --category unverified
/repro-failure list
/repro-failure summary
/repro-failure help
```

## 5-step flow (per `log`)

| Step | Reads | Writes |
|---|---|---|
| **1. Prompt for the 4 fields** | – | in-memory tuple (symptom, impact, fix, evidence) |
| **2. Classify** | the tuple + decision logic | category ∈ {fixed, worked_around, unverified} |
| **3. Assign ID** | existing `failure_case_report.md` | next sequential id (F0NN / W0NN / U0NN) |
| **4. Append row** | category section | one new row in the matching table |
| **5. Update top counts** | – | refresh the "总览" counts |

## Classification rules

| Rule | Category |
|---|---|
| `fix` row contains a re-verification reference (e.g., `verified by re-run`) | `fixed` |
| `fix` row contains "lower batch size" / "downgrade precision" / "use alternative X" | `worked_around` |
| `fix` row is empty or "TODO" | `unverified` |

These rules are heuristic — the human can override via `--category`.

## Output (for `log`)

```
[repro-failure] step 1/5 prompt ............... 4 fields captured
[repro-failure] step 2/5 classify ............. category = fixed (rule: re-verification)
[repro-failure] step 3/5 assign_id ............ F007
[repro-failure] step 4/5 append_row ............ row added to §1
[repro-failure] step 5/5 update_counts ......... 总览 refreshed: 6 fixed, 2 worked_around, 1 unverified
```

## `summary` output

```
[repro-failure] total = 9
  fixed (已修复) = 6
  worked_around (已规避) = 2
  unverified (未验证) = 1
[repro-failure] oldest unverified: U001 (2026-07-08)
[repro-failure] recommendation: raise U001 to "fixed" or "worked_around" before next /repro-report
```

## Failure modes

- `failure_case_report.md` missing → REFUSE; the user must run
  `/repro-card` first to scaffold.
- ID collision (you manually wrote F007 already) → REFUSE; do not
  silently renumber.
- `--strict` with a missing evidence file → REFUSE.

## What this command does NOT do

- Does NOT silently re-categorize past rows.
- Does NOT generate fix recommendations; that's `/repro-review`'s job.
- Does NOT write to `DECISION_LOG.md`; failure cases are operational,
  not decisions.