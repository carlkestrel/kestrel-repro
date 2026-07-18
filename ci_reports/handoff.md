# HANDOFF: R1 → R2

**Date**: 2026-07-17
**R1 status**: COMPLETE ✅
**R2 status**: UNLOCKED

## What R1 accomplished

R1 closed the packaging, dependency, and path-resolution gaps that
prevented the test suite from being reproducibly runnable in isolation.

| Area | Before R1 | After R1 |
|---|---|---|
| `pip install -e .` | fragile | works in fresh venv |
| `reproctl` entry | missing | console script + module entry |
| Version source | scattered across 5 files | `scripts/_version.py` |
| Fixture location | absolute paths / cwd | `importlib.resources` |
| conftest.py | no path hooks needed | pure fixtures |
| Test suite | 174/198 (24 fail) | 197/210 (13 fail, all R3) |

## R2 scope

R2 may begin immediately. R2 inherits:

1. **R1 environment**: `/tmp/kestrel_r1_workspace/kestrel_r1_venv`
   with `kestrel-repro 0.2.0` editable-installed.
2. **R1 acceptance tests**: 12 passing — keep them green.
3. **R1 R3 leftovers**: 13 failures to defer to R3.
4. **R1 deliverables**: `ci_reports/R1_*`.

## R2 input conditions (must hold)

R2 may proceed because all R1 acceptance criteria pass:

- [x] `pip install -e .` in fresh venv
- [x] `reproctl version` works from any cwd
- [x] Fixtures resolve via `importlib.resources`
- [x] L0–L3 tests pass with `STUB_TEST_PASSED` state
- [x] R0 baseline preserved (174 → 197 passed, +12 R1 acceptance, +11 R1
      repair; net 0 regressions)
- [x] pytest exit code non-zero on failure
- [x] No forbidden-pattern leftovers in `conftest.py`

## R2 deliverables (expected)

Per the user's R2 plan: **real paper reproduction adapters** that
turn the toy L0–L3 stubs into a working `RepoAdapter` against an
actual paper repository.

## Risks R2 must address

1. The 13 R3 failures may surface as integration issues when R2 runs
   the orchestrator against real adapters. Do not assume they will
   stay isolated.
2. The `scripts.commands` / `scripts.agents` etc. marker packages
   are NEW. Cursor may need to be reloaded to see them.
3. The legacy `scripts/reproctl.py` is still the implementation
   file; the package `scripts.reproctl/__init__.py:main` is a
   thin dispatcher. Do not move logic into `__init__.py`.

## Open items deferred past R1

- Wheel install (non-editable) — not exercised in R1, defer to R3
- Cross-platform test (Windows / macOS) — not exercised in R1, defer
- `pyproject.toml` `dynamic = ["version"]` with setuptools-scm — defer
  until R3 lockstep is proven