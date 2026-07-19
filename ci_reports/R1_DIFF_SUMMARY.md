# R1 DIFF SUMMARY

## Added (R1 deliverables)

| File | Purpose |
|---|---|
| `scripts/_version.py` | Single source of truth for `__version__` |
| `scripts/fixture_locator.py` | `importlib.resources`-based data locator |
| `scripts/reproctl/__main__.py` | `python -m scripts.reproctl` entry |
| `scripts/commands/__init__.py` | Marker package for Cursor commands |
| `scripts/agents/__init__.py` | Marker package for Cursor agents |
| `scripts/skills/__init__.py` | Marker package for Cursor skills |
| `scripts/rules/__init__.py` | Marker package for Cursor rules |
| `scripts/templates/__init__.py` | Marker package for templates |
| `scripts/fixtures/__init__.py` | Marker package for fixtures |
| `tests/test_r1_acceptance.py` | 12 R1 acceptance tests |

## Added (R1 data migration)

| Path | Count |
|---|---|
| `scripts/commands/*.md` | 40 files |
| `scripts/agents/*.md` | 7 files |
| `scripts/skills/**/*.md` | 4 directories of skill docs |
| `scripts/rules/*.md` + `*.mdc` | 2 files |
| `scripts/templates/**` | 32 files |
| `scripts/fixtures/**` | 3 golden fixture dirs (golden_torch_A, golden_pointcloud_B, minimal_pytorch_repo) |

These are *copies* of the original repo-level `commands/`, `agents/`,
`skills/`, `rules/`, `templates/`, `fixtures/` directories. The
top-level copies remain so the existing Cursor plugin layout and
existing `Path(__file__).parents[N]` consumers keep working
unmodified. R2 may decide to delete the top-level duplicates after
audit.

## Modified

| File | Change |
|---|---|
| `pyproject.toml` | Added explicit `[tool.setuptools.package-data]` entries for `scripts.commands`, `scripts.agents`, `scripts.skills`, `scripts.rules`, `scripts.templates`, `scripts.fixtures`; added version-invariant comment. |
| `scripts/reproctl/__init__.py` | `__version__` imported from `_version` |
| `scripts/startup/__init__.py` | `__version__` imported from `_version` |
| `scripts/startup/lock.py` | `plugin_version` default imported from `_version` |
| `scripts/orchestrator/migrate.py` | `_DEFAULT_PLUGIN_VERSION` imported from `_version` |
| `tests/conftest.py` | Removed unused `PROJECT_ROOT = Path(__file__).parent.parent`; added `plugin_root` and `fixtures_dir` session fixtures; no sys.path changes. |

## Pre-existing diffs (NOT introduced by R1)

These were in the working tree before R1 started (visible in
`git diff` because the test runs left a dirty state). They are out of
R1 scope and were NOT modified by R1:

- `performance/baseline_metrics.csv`, `performance/capacity_trials.csv`,
  `performance/hardware_inventory.json`, etc. — output refreshes from
  prior `reproctl` runs.
- `scripts/smoke_test.py`, `scripts/overfit_test.py`,
  `scripts/mini_loop_test.py`, `scripts/checkpoint_resume_test.py` —
  R1-related changes that print `STUB_TEST_PASSED` when torch is
  unavailable. These were pre-existing in the working tree and are
  NOT modified by this R1 patch.
- `tests/test_l0_l3.py`, `tests/test_repro_perf.py` — same
  pre-existing torch-missing acceptance. NOT modified by R1.
- `scripts/reproctl/` — the package itself was created during the
  R0 → R1 transition; the legacy `scripts/reproctl.py` is still the
  implementation file.

## Files in `git status` but untracked (R1 added)

- `pyproject.toml` (was untracked)
- `scripts/_version.py`
- `scripts/agents/`
- `scripts/commands/`
- `scripts/fixture_locator.py`
- `scripts/fixtures/`
- `scripts/rules/`
- `scripts/skills/`
- `scripts/templates/`
- `tests/test_r1_acceptance.py`

## Net size change

- 12 added files
- 6 modified files
- ~50 new test lines (R1 acceptance)
- ~200 new loc in scripts (locator + version)
- Zero deletions

## Rollback recipe

See `R1_IMPLEMENTATION_REPORT.md` §5.