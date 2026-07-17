# .gitignore Validation Report
Generated: 2026-07-17

## .gitignore Changes

### Added Sections

```gitignore
# ============================================
# Project-specific runtime and output
# ============================================

# Reproduction state (DO NOT COMMIT)
.repro/
.execution/
.repair/
.stabilization/

# Audit and reports
audits/
reports/
ci_reports/
coverage/

# Experiment outputs
runs/
checkpoints/
predictions/
datasets/
soak/

# Performance
performance/

# Malformed filename (created by erroneous shell expansion)
**Audit

# Node (if using any JS tooling)
node_modules/
```

## Coverage Check

| Pattern | Type | Status |
|---------|------|--------|
| `__pycache__/` | Python cache | ✅ Existing |
| `*.py[cod]` | Python bytecode | ✅ Existing |
| `.pytest_cache/` | Test cache | ✅ Existing |
| `.cache/` | General cache | ✅ Existing |
| `*.log` | Logs | ✅ Existing |
| `artifacts/` | Local artifacts | ✅ Existing |
| `venv/` | Virtual env | ✅ Existing |
| `.repro/` | Runtime state | ✅ Added |
| `.execution/` | Execution state | ✅ Added |
| `.repair/` | Repair artifacts | ✅ Added |
| `audits/` | Audit reports | ✅ Added |
| `reports/` | Generated reports | ✅ Added |
| `runs/` | Experiment runs | ✅ Added |
| `checkpoints/` | Model checkpoints | ✅ Added |
| `predictions/` | Predictions | ✅ Added |
| `datasets/` | Datasets | ✅ Added |
| `soak/` | Soak test output | ✅ Added |
| `coverage/` | Coverage reports | ✅ Added |
| `**Audit` | Malformed file | ✅ Added |

## Protected from Ignorance

These are intentionally NOT ignored:

| Pattern | Reason |
|---------|--------|
| `scripts/` | Source code - KEEP_SOURCE |
| `tests/` | Test suite - KEEP_TEST |
| `templates/` | Config templates - KEEP_CONFIG |
| `commands/` | Cursor commands - KEEP_CONFIG |
| `agents/` | Agent definitions - KEEP_SOURCE |
| `skills/` | Cursor skills - KEEP_ASSET |
| `docs/` | Documentation - KEEP_DOCS |
| `fixtures/` | Test fixtures - KEEP_ASSET |
| `schemas/` | JSON schemas - KEEP_CONFIG |

## .repro Tracking Removal

Files to be removed from git index (will remain in working directory):

```
.repro/execution/state.sqlite3
.repro/reports/go_pivot_nogo.json
.repro/reports/summary_report.csv
.repro/reports/summary_report.json
.repro/repro_audit/DECISION_LOG.md
.repro/repro_audit/STATE.json
.repro/state.json
```

Command to execute:
```bash
git rm --cached -r .repro/
```

This will:
- Remove `.repro/` from git index
- Keep local `.repro/` files intact
- Update `.gitignore` to prevent future tracking
