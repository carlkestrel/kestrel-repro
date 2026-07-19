---
description: Run a controlled GitHub absorption round, applying the 7-state lifecycle and 4-decision categorization.
---

# /repro-evolution

> One absorption round. Reads external GitHub lessons (from
> `templates/topic_graph.json` Tier-A/B or a candidate list provided by
> the user), runs them through the 7-state lifecycle, and writes the
> 5 output files under `output/evolution/`.

## Usage

```
/repro-evolution                           # absorb all Tier-A/B topics
/repro-evolution --since 2026-07-01        # only topics updated since date
/repro-evolution --topic <id>              # one specific topic
/repro-evolution --dry-run                 # print plan, no writes
/repro-evolution help
```

## 8-step flow

| Step | Reads | Writes | Failure |
|---|---|---|---|
| **1. Collect** | `templates/topic_graph.json` + `templates/project_memory.md` | candidate list | abort if no candidates |
| **2. Deduplicate** | candidate list | dedup'd list | warn if any hash collisions |
| **3. Classify** | dedup'd list | per-candidate category (`workflow`/`knowledge`/`tooling`/`trap`) | warn on uncategorized |
| **4. Generate proposal** | classified list | `output/evolution/evolution_proposal.md` (diff against current §2) | abort on diff parse error |
| **5. Regression** | `tests/test_regression.py` | `output/evolution/evolution_regression_report.md` | abort on any FAIL |
| **6. evolution_report** | proposal + regression + audit | `output/evolution/evolution_audit.json` | abort if regression FAIL |
| **7. Human approval** | proposal + regression + audit | `DECISION_LOG.md` (decision_type=gate_approval) + `output/evolution/evolution_lessons.jsonl` | refuse without `--approved-by` |
| **8. Release** | approved proposal | `templates/project_memory.md` §2 diff + `output/evolution/evolution_failures.jsonl` (rejections) | refuse if step 7 missing |

## Pre-conditions

- `templates/topic_graph.json` has at least 1 entry.
- `tests/test_regression.py` is callable (PYTHONPATH covers it).
- `templates/project_memory.md` §2 exists (even if empty).
- The user has invoked `--approved-by <name>` for step 7 (or
  `--dry-run`).

## Output

```
[repro-evolution] step 1/8 collect ............... 12 candidates (Tier-A=5, Tier-B=7)
[repro-evolution] step 2/8 deduplicate ........... 12 (0 collisions)
[repro-evolution] step 3/8 classify .............. 12 (4 workflow, 5 knowledge, 2 tooling, 1 trap)
[repro-evolution] step 4/8 proposal .............. OK (3 §2 inserts, 1 amend)
[repro-evolution] step 5/8 regression ............ 9/9 PASS
[repro-evolution] step 6/8 evolution_report ...... OK
[repro-evolution] step 7/8 human approval ........ OK (approved_by=alice)
[repro-evolution] step 8/8 release ............... §2 updated; 1 reject logged
[repro-evolution] decision = D__ → DECISION_LOG.md
```

## Failure modes

- Step 1 returns 0 candidates → abort, no writes.
- Step 5 has any FAIL → abort at step 6, do not request approval.
- Step 7 missing `--approved-by` → refuse (cannot silently auto-approve).
- Step 8 detects a §2 conflict → write a conflict row to
  `evolution_failures.jsonl` and ask the user to resolve.

## Implementation

`scripts/reproctl.py evolution [--since DATE] [--topic ID] [--approved-by N]`