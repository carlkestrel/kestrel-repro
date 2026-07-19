# R2 Rollback Plan

## What R2 Adds

R2 adds 5 new modules and 31 new tests to the `scripts/startup/` directory.
It does NOT modify any existing orchestrator logic.

## Rollback Command

To revert R2 to pre-R2 state (emergency):

```bash
# Remove R2-specific files
rm scripts/startup/plan_schema.py
rm scripts/startup/mode.py
rm scripts/startup/authorization.py
rm scripts/startup/state_store.py
rm scripts/startup/migration.py
rm tests/test_r2_acceptance.py

# Remove CI reports
rm -rf ci_reports/R2_*

# Restore __init__.py to pre-R2 state
# (revert the R2 exports section)
```

## Effect on Each Module

### plan_schema.py
- Only used by new R2 entry points
- Existing `plan_validate.py` still works for the old frontmatter format
- Rollback: remove file, `startup/__init__.py` reverts cleanly

### mode.py
- Only used by new plan schema validator
- Legacy system continues with string-mode modes
- Rollback: no impact on existing mode handling

### authorization.py
- Only invoked by new R2 startup flow
- Existing orchestrator has its own permission checks
- Rollback: authorization contract enforcement disabled, falls back to orchestrator checks

### state_store.py (startup layer)
- **Does NOT** replace `scripts/orchestrator/state_store.py`
- Runs in parallel; orchestrator continues using its own SQLite store
- Rollback: new store simply not instantiated; existing orchestrator state unaffected

### migration.py
- One-shot: reads legacy JSON, writes to new SQLite store
- If migration runs and is then rolled back, legacy JSON files are still backed up
- Original legacy files are NOT deleted (per R2 safety rules)
- Rollback: old JSON files can be restored from backup at `.repro/migrations/legacy_<id>/`

## State Migration Impact

If migration has run:
1. Legacy files are backed up to `.repro/migrations/legacy_<id>/`
2. SQLite store at `.repro/execution/state.sqlite3` is populated
3. Migration records are in the `migrations` table

**To undo**: Copy backed-up files back, delete the SQLite store:
```bash
cp -r .repro/migrations/legacy_<id>/* .repro/
rm .repro/execution/state.sqlite3
```

## Recovery Path

If R2 code is deployed and causes issues:
1. `startup/__init__.py` can be reverted to remove R2 module imports
2. The orchestrator continues using its existing state store
3. New R2 state store at `.repro/execution/state.sqlite3` is independent
4. Legacy JSON files at `.repro/state.json` etc. are untouched

## No Changes to R1 Acceptance

R1 acceptance tests (43 tests) are unaffected by R2 rollback, as R2 does not modify the code they test.

## Git Revert

```bash
git revert <R2-commit-hash>
# or
git checkout <pre-R2-tag>
```

This will revert all R2 files cleanly.
