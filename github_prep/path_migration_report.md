# GHP-100 Path Migration Baseline Report

## Current Git State

**Commit:** `dd35c4c90cfd77d1bf3bd43a00493656c7d16e07`

**Branch:** `main`

## Uncommitted Changes (not staged)

### Modified files:
- `README.md`
- `agents/repo-scout.md`
- `automation_policy.yaml`
- `scripts/orchestrator/approval_gate.py`
- `scripts/orchestrator/controller.py`
- `scripts/orchestrator/policy_engine.py`
- `scripts/orchestrator/watchdog.py`
- `scripts/reproctl.py`
- `scripts/research_crawler.py`

### Deleted files:
- `.repro/execution/state.sqlite3`
- `.repro/reports/go_pivot_nogo.json`
- `.repro/reports/summary_report.csv`
- `.repro/reports/summary_report.json`
- `.repro/repro_audit/DECISION_LOG.md`
- `.repro/repro_audit/STATE.json`
- `.repro/state.json`

## Hardcoded Path Summary

Found 3 production-code instances of hardcoded `/home/carlkestrel` paths across 3 files:
- `scripts/orchestrator/task_executor.py` — line 30
- `scripts/orchestrator/verifier.py` — line 80
- `scripts/l0_l3_loop.py` — line 54

(1 test-code instance in `tests/test_startup.py` line 1152 is intentionally present as a detection token — left unchanged.)

## Fix Strategy

| Priority | Method | Rationale |
|----------|--------|-----------|
| 1 | `sys.executable` | Returns absolute path to the running Python interpreter; conda-aware |
| 2 | `shutil.which("python")` | Resolves `python` from current `PATH` |
| 3 | Env var fallback | For PATH injection, prepend `sys.executable`'s directory |

## Changes Applied (not committed)

- `scripts/orchestrator/task_executor.py` — line 30 fixed
- `scripts/orchestrator/verifier.py` — line 80 fixed
- `scripts/l0_l3_loop.py` — line 54 fixed
