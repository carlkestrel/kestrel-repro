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

| Field | Value |
|---|---|
| Phase | R3F-1 |
| Status | **PASS** |
| Local head SHA (start) | `f28f0eb6832450355a5f5077b36bcfa394152cbb` |
| Local head SHA (after commit) | `25147075326ba96ece68344f599373624353467a` |
| Remote head SHA | `25147075326ba96ece68344f599373624353467a` |
| base SHA | `a828023f537dfbfed4d7798066f3ca084d8072c9` (untouched ✅) |
| PR | https://github.com/carlkestrel/kestrel-repro/pull/1 (Draft ✅) |
| Test commands | `/tmp/actionlint -no-color .github/workflows/*.yml`, `yaml.safe_load(...)` for each |
| actionlint errors | 0 |
| YAML parse errors | 0 |
| Jobs declared | 16 (5 + 4 + 7) |
| Exit-code swallow removed | 1 (`pytest ... || echo "..."` in ci-l3.yml `remaining-tests`) |
| GPU Job strategy | `if: ${{ inputs.gpu_enabled == true }}`, `runs-on: ubuntu-latest`, explicit NO_GPU/NO_TORCH reporting |
| Raw evidence | `ci_reports/r3_repair/R3F_1_BASELINE.md`, `R3F_1_actionlint.txt`, `R3F_1_jobs.json` |
| New issues opened | 0 |
| Issues closed | 0 |
| Rollback commit | `25147075326ba96ece68344f599373624353467a` (single-commit phase; reset to `f28f0eb` to roll back) |
| Pushed to `review/r3-20260718-a828023`? | ✅ yes (verified 2026-07-18 13:40; remote head = local head) |
| GitHub Actions URL | https://github.com/carlkestrel/kestrel-repro/pull/1 (still Draft) |
| `LATEST_REVIEW_REQUEST.json` updated | ✅ |
| Allow next phase? | yes |
| External review status | NOT_REQUESTED |

---

## R3F-2 — Single SQLite authority end-to-end verification

| Field | Value |
|---|---|
| Phase | R3F-2 |
| Status | **PASS** |
| Local head SHA (start) | `453a58b83294011ba47a0402f09bf5db2f3deaeb` |
| Local head SHA (after commit) | `4444c94cf8167cf6dc06568c29cf3880d7574b6e` |
| Remote head SHA | `4444c94cf8167cf6dc06568c29cf3880d7574b6e` |
| base SHA | `a828023f537dfbfed4d7798066f3ca084d8072c9` (untouched ✅) |
| PR | https://github.com/carlkestrel/kestrel-repro/pull/1 (Draft ✅) |
| Test commands | `pytest tests/test_r1_acceptance.py tests/test_r2_acceptance.py tests/test_r3_0_acceptance.py tests/test_r3f2_single_authority.py` |
| Tests collected | 67 |
| Tests passed | 67 |
| Tests failed | 0 |
| Raw evidence | `ci_reports/r3_repair/R3F_2_BASELINE.md`, `R3F_2_JUNIT.xml` |
| Issues fixed | (a) doc/impl path mismatch (`.repro/state/` vs `.repro/execution/`); (b) `find_active_state_dbs` now raises `BLOCKED_STATE_CONFLICT` on legacy JSON + active SQLite |
| New tests | `tests/test_r3f2_single_authority.py` — 7 tests |
| New module | `scripts/startup/errors.py` (StartupError + error code constants) |
| Rollback commit | `4444c94cf8167cf6dc06568c29cf3880d7574b6e` (single-commit phase; reset to `453a58b` to roll back) |
| Pushed to `review/r3-20260718-a828023`? | ✅ yes (verified 2026-07-18 13:50; remote head = local head) |
| GitHub Actions URL | https://github.com/carlkestrel/kestrel-repro/pull/1 (still Draft) |
| `LATEST_REVIEW_REQUEST.json` updated | ✅ |
| Allow next phase? | yes |
| External review status | NOT_REQUESTED |

---

## R3F-3 — Fix orchestrator execution chain

| Field | Value |
|---|---|
| Phase | R3F-3 |
| Status | **PASS** |
| Local head SHA (start) | `5cc1899028a38ba0cc7b5c931480e0087f482803` |
| Local head SHA (after commit) | `83f0c9ad4bbdea26efcede82177b2a2c43a07bbb` |
| Remote head SHA | `83f0c9ad4bbdea26efcede82177b2a2c43a07bbb` |
| base SHA | `a828023f537dfbfed4d7798066f3ca084d8072c9` (untouched ✅) |
| PR | https://github.com/carlkestrel/kestrel-repro/pull/1 (Draft ✅) |
| Orchestrator before | 14 failed / 4 passed (deterministic) |
| Orchestrator after | **18 passed / 0 failed** ✅ |
| Test commands | `pytest tests/test_r1_acceptance.py tests/test_r2_acceptance.py tests/test_r3_0_acceptance.py tests/test_r3f2_single_authority.py tests/test_orchestrator.py` |
| Tests collected | 85 |
| Tests passed | 85 |
| Tests failed | 0 |
| Raw evidence | `ci_reports/r3_repair/R3F_3_BASELINE.md`, `R3F_3_orchestrator_JUNIT.xml` |
| Defects fixed | set_process missing; event_type kwarg missing; claim_task too permissive; _read_exit_code defaulted 0; PROCESS_STARTED not emitted; status_summary alias; watchdog CLI missing; chaos back-compat |
| Rollback commit | `83f0c9ad4bbdea26efcede82177b2a2c43a07bbb` (single-commit phase; reset to `5cc1899` to roll back) |
| Pushed to `review/r3-20260718-a828023`? | ✅ yes (verified 2026-07-18 14:05; remote head = local head) |
| GitHub Actions URL | https://github.com/carlkestrel/kestrel-repro/pull/1 (still Draft) |
| `LATEST_REVIEW_REQUEST.json` updated | ✅ |
| Allow next phase? | yes |
| External review status | NOT_REQUESTED |

---

## R3F-4 — Plan / Mode / Authorization integration
_tbd_
