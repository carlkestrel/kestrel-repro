# R2 Migration Report

## Legacy State Files Covered

The migration system handles the following legacy state files:

| Legacy path | Format | Notes |
|---|---|---|
| `.repro/state.json` | JSON | Old project-level state |
| `.repro/execution/execution_state.json` | JSON | Old execution state |
| `.execution/execution_state.json` | JSON | Alt location |
| `.execution/state.json` | JSON | Alt location |
| `.repro/execution/state.json` | JSON | Alt location |

## Migration Process

### Phase 1: Discovery
```
find_legacy_files(project_root) → list[Path]
```
Finds all legacy files in standard locations.

### Phase 2: Hash and Backup
```
sha256_of(legacy_file) → str  (recorded)
shutil.copy2(legacy_file, .repro/migrations/legacy_<id>/)
```

### Phase 3: Parse and Merge
Each legacy file is parsed as JSON or YAML. States are merged:
- Task states merged by task ID (last-wins deduplication)
- Gate states merged by gate name
- Project state: last non-null wins
- Plan hashes: preserved from first source

### Phase 4: State Migration

#### Task State Mapping

| Legacy state | R2 state | Reason |
|---|---|---|
| `PASS` | `LEGACY_UNVERIFIED` | Unconfirmable without evidence; cannot be trusted |
| `FAIL` | `FAILED` | Clear failure |
| `READY` | `READY` | Ready to run |
| `PENDING` | `PENDING` | Not yet eligible |
| `BLOCKED` | `BLOCKED` | Blocked |
| `WAITING_APPROVAL` | `WAITING_APPROVAL` | Pending human |
| `APPROVED` | `APPROVED` | Approved |
| `RUNNING` | `BLOCKED` | Treat interrupted runs as blocked |

#### Gate State Mapping

| Legacy state | R2 state | Notes |
|---|---|---|
| `PASS` / `COMPLETED` | `UNLOCKED` | Gate was passed |
| `FAILED` | `LOCKED` | Gate not passed |

### Phase 5: Record Migration

After writing to SQLite:
```
record_migration(
    legacy_path=...,
    sha256=...,
    tasks=tasks_migrated,
    gates=gates_migrated
)
```
Also inserts `legacy_state.source_path` as `legacy_readonly`.

## Safety Rules

1. **Never delete** original legacy files
2. **Always back up** before migration
3. **Never modify** user run artifacts
4. **LEGACY_UNVERIFIED** tasks are not promoted to PASSED
5. **BLOCKED_STATE_CONFLICT** is raised if SQLite already has data that conflicts with legacy state

## Migration Report Output

Written to: `.repro/reports/migration_<id>.json`

```json
{
  "migration_id": "abc123",
  "started_at": "2026-07-18T...",
  "finished_at": "2026-07-18T...",
  "legacy_files": [".repro/state.json"],
  "legacy_hashes": {".repro/state.json": "sha256:..."},
  "tasks_migrated": 5,
  "gates_migrated": 2,
  "tasks_skipped": 0,
  "errors": [],
  "status": "done",
  "output_path": ".repro/reports/migration_abc123.json"
}
```

## BLOCKED_STATE_CONFLICT Handling

When SQLite and legacy state conflict:
1. Migration is aborted
2. StateConflict exception is raised
3. `execution/reports/state_conflict_<ts>.json` is written
4. Project enters `BLOCKED_STATE_CONFLICT`
5. Human review is required to proceed