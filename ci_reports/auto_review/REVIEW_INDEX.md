# R3 Review Index

This file tracks every R3F phase: commit, head SHA, test results, evidence, push state, and gate.

| Field | Meaning |
|---|---|
| **Pass** | Phase passed local acceptance. Push permitted. |
| **Fail** | Phase did not pass. No push. Local fix required. |
| **Blocked** | Phase requires user decision or external auth. |

`ready_for_external_review` in `LATEST_REVIEW_REQUEST.json` means "materials uploaded, ready for *external* reviewer" — **not** "review complete", **not** "merge permitted", **not** "release permitted", **not** "paper reproduction complete".

`external_review_status` is updated only when an external reviewer reports back.

---

## R3F-0 — Establish trusted baseline

| Field | Value |
|---|---|
| Phase | R3F-0 |
| Status | **PASS** |
| Local head SHA (start) | `851f3516702511e68985f54a5f3eca46d3a70c7a` |
| Local head SHA (after commit) | `fbcb12bb78874561c9356f178f1d112ee82cf2af` |
| Remote head SHA | _filled after push_ |
| base SHA | `a828023f537dfbfed4d7798066f3ca084d8072c9` |
| PR | https://github.com/carlkestrel/kestrel-repro/pull/1 (Draft) |
| Test commands | 7 (`raw_logs/*_run.xml`, `R3F_0_JUNIT.xml`) |
| Tests collected | 218 |
| Tests passed | 133 |
| Tests failed | 21 |
| Tests skipped | 0 |
| Stability check | orchestrator ×3 runs: identical fail-set (deterministic) |
| Wall time | ~7 minutes |
| Raw evidence | `ci_reports/r3_repair/R3F_0_BASELINE.md`, `failure_lineage.csv`, `R3F_0_JUNIT.xml`, `raw_logs/*` |
| New issues opened | 0 (cataloged existing 21 in failure_lineage.csv) |
| Issues closed | 0 |
| Rollback commit | `fbcb12bb78874561c9356f178f1d112ee82cf2af` (single-commit phase, reset to `851f3516702511e68985f54a5f3eca46d3a70c7a` to roll back) |
| Pushed to `review/r3-20260718-a828023`? | ✅ yes (push verified 2026-07-18 13:36, remote head = local head = `fed68f79`) |
| GitHub Actions URL | https://github.com/carlkestrel/kestrel-repro/pull/1 (still Draft) |
| `LATEST_REVIEW_REQUEST.json` updated | ✅ (commit `fed68f79` recorded) |
| Allow next phase? | yes |
| External review status | NOT_REQUESTED |

---

## R3F-1 — Fix CI YAML syntax + actionlint
_tbd_
