# R2 Code Change Summary

## Files Added (New)

| File | Lines | Purpose |
|---|---|---|
| `scripts/startup/plan_schema.py` | ~350 | Versioned Plan schema, validator, canonical hash |
| `scripts/startup/mode.py` | ~130 | Three-dimensional mode model + legacy migration |
| `scripts/startup/authorization.py` | ~280 | Authorization contract data model + enforcement |
| `scripts/startup/state_store.py` | ~450 | R2 SQLite authoritative state store |
| `scripts/startup/migration.py` | ~280 | Legacy state JSON → SQLite migration engine |
| `scripts/startup/plan_schema.py` | — | Replaces `scripts/startup/plan_validate.py` (R2 schema) |
| `tests/test_r2_acceptance.py` | ~280 | 31 R2 acceptance tests |

## Files Modified

| File | Change | Reason |
|---|---|---|
| `scripts/startup/__init__.py` | Added R2 module exports | Make R2 modules discoverable |
| `scripts/startup/lock.py` | Added `check_plan_hash()` | Enforce plan hash consistency for authorization |
| `scripts/startup/state_machine.py` | No changes needed | Existing code already uses plan hashes |

## Files Not Modified (R2 Scope)

The following were explicitly excluded from R2 scope per spec:
- `scripts/orchestrator/controller.py` — R3
- `scripts/orchestrator/approval_gate.py` — R3
- `scripts/orchestrator/recovery.py` — R3
- `scripts/l0_l3_loop.py` — R3
- `scripts/repro_perf_tuner.py` — R3
- `scripts/orchestrator/state_store.py` — R2 has new startup-layer store; orchestrator keeps its own

## CI Reports Added

| File | Purpose |
|---|---|
| `ci_reports/R2_PLAN_SCHEMA.md` | Plan schema specification |
| `ci_reports/R2_MODE_MIGRATION_MATRIX.csv` | Legacy mode → canonical mapping |
| `ci_reports/R2_STATE_MODEL.md` | State machine specification |
| `ci_reports/R2_STATE_TRANSITION_MATRIX.csv` | State transition matrix |
| `ci_reports/R2_AUTHORIZATION_SCHEMA.md` | Authorization contract schema |
| `ci_reports/R2_MIGRATION_REPORT.md` | Migration process documentation |
| `ci_reports/R2_TEST_REPORT.md` | Test results |
| `ci_reports/R2_JUNIT.xml` | Authoritative JUnit XML |

## New Test Coverage

- **31 new R2 acceptance tests** covering all acceptance criteria
- **0 regressions** in existing test suites (R1 43/43 still passing)

## Key Design Decisions

1. **Parallel to orchestrator state_store**: R2 introduces a startup-layer `state_store.py`. The orchestrator's own `scripts/orchestrator/state_store.py` is NOT modified. This ensures R2 is additive and does not disrupt running orchestration.

2. **Plan schema via YAML frontmatter**: Matches the existing `plan_validate.py` convention (--- ... ---). The new `plan_schema.py` supersedes it with R2-compliant validation.

3. **Deny-by-default authorization**: Every action not in `granted_actions` is denied, even if the contract has no `denied_actions` list.

4. **Canonical hash excludes schema_version**: Changing schema_version does not change the canonical plan identity. This allows schema upgrades without invalidating contracts.

5. **LEGACY_UNVERIFIED for migrated PASS states**: Past PASS states from legacy state are not blindly migrated to PASSED. They must be re-verified.

6. **NEEDS_MODE_REVIEW for ambiguous legacy modes**: Modes that could mean multiple things require human review. This prevents silent wrong migrations.
