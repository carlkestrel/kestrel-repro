# R3-0 Rollback Plan

## Goal

Allow reverting R3-0 if the canonical StateStore consolidation causes
unforeseen regressions, while preserving R2 functionality.

## What R3-0 Changes

| Change | File | Revert By |
|---|---|---|
| New `scripts/core/state_store.py` | NEW (~960 LOC) | Delete |
| Startup StateStore → shim | `scripts/startup/state_store.py` | Restore 899-LOC version (was R2 implementation) |
| Orchestrator StateStore → shim | `scripts/orchestrator/state_store.py` | Restore 480-LOC version (was orchestrator's own implementation) |
| `compute_authorization_bound_hash` / `upgrade_schema_with_hash_reset` | `scripts/core/state_store.py` | Delete |
| `find_active_state_dbs` / `assert_single_state_authority` | `scripts/core/state_store.py` | Delete |
| Migration uses bound hash | `scripts/startup/migration.py` | Revert to canonical_hash-only |
| Plan canonical hash includes schema_version | `scripts/startup/plan_schema.py` | Restore exclusion list |
| New R3-0 test suite | `tests/test_r3_0_acceptance.py` | Delete |

## Rollback Procedure

### Option A: Git revert R3-0 commit

```bash
git log --oneline | grep "R3-0"  # find commit hash
git revert <R3-0-commit-hash>
git push
```

### Option B: Manual revert

1. **Delete** `scripts/core/__init__.py` and `scripts/core/state_store.py`.
2. **Restore** `scripts/startup/state_store.py` from git history (pre-R3-0).
3. **Restore** `scripts/orchestrator/state_store.py` from git history.
4. **Revert** `scripts/startup/migration.py` to remove `authorization_bound_hash` parameter.
5. **Revert** `scripts/startup/plan_schema.py` to exclude schema_version from canonical hash.
6. **Delete** `tests/test_r3_0_acceptance.py`.

```bash
# Example for restoring one file:
git checkout HEAD~1 -- scripts/startup/state_store.py
```

## Data Migration on Rollback

If a project was used with R3-0:

- **Plan hash format changed**: old R3-0 plans had schema_version in hash;
  old R2 plans didn't. On rollback, plans created under R3-0 will have
  hashes that don't match pre-R3-0 expectations.
- **Authorization contract marked NEEDS_RECONFIRMATION**: old auth contracts
  may have `needs_reconfirmation=1` set. Rollback should reset this.
- **Database path is unchanged** (still `.repro/execution/state.sqlite3`),
  so the SQLite file is compatible.

The simplest path is:
1. Rollback code
2. Run `reproctl reset-state --hard` (if implemented; otherwise
   archive `.repro/` and re-initialize)

## Re-Applying R3-0

If rollback reveals R3-0 is needed, simply re-apply the R3-0 commit.
The hash format reset is intentional and will not break existing data.

## R2 Functionality After Rollback

R2's plan_schema, mode, authorization, migration modules remain
unchanged by R3-0. After rollback, R2 status returns to
IMPLEMENTED_ISOLATED (it never reached COMPLETE because R3-0 was the
gate).
