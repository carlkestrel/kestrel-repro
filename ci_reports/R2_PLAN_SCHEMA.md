# R2 Plan Schema Specification

**Schema version**: 2.0
**Authority**: `.repro/plan.yaml`

## Schema Fields

### Identity

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | ✅ | Must be `"2.0"` |
| `plan_id` | string | ✅ | Unique plan identifier |
| `project_id` | string | ✅ | Parent project identifier |
| `project_root` | string | ✅ | Absolute path to project |
| `paper_identity` | string | | DOI or arXiv ID of target paper |
| `target_claims` | list[string] | | Claims to reproduce from the paper |
| `research_intent` | string | | Human-readable intent description |

### Mode (Three-Dimensional)

| Field | Values | Required | Description |
|---|---|---|---|
| `research_purpose` | `audit`, `reproduce`, `extend`, `takeover` | ✅ | Why are we doing this? |
| `execution_track` | `smoke`, `fast`, `strict`, `statistical` | ✅ | How much compute budget? |
| `automation_level` | `manual`, `gated-autopilot` | ✅ | Who controls task scheduling? |

### Mode Migration Table

Legacy single-string modes are migrated as follows:

| Legacy mode | research_purpose | execution_track | automation_level |
|---|---|---|---|
| `strict_repro` | reproduce | strict | gated-autopilot |
| `optimized_repro_safe` | reproduce | fast | gated-autopilot |
| `experimental_fast` | reproduce | fast | gated-autopilot |
| `strict` | reproduce | strict | manual |
| `optimized` | reproduce | fast | manual |
| `diagnose` | audit | strict | gated-autopilot |
| `evolve` / `extend` | extend | fast | gated-autopilot |
| `takeover` | takeover | strict | gated-autopilot |

**Ambiguous modes** (e.g., bare `"audit"`, `"strict"`, `"optimized"`) → `NEEDS_MODE_REVIEW`.
These require human review before use.

### Repository and Data

| Field | Type | Description |
|---|---|---|
| `repositories` | list[dict] | List of `{url, ref, path}` for clones |
| `dataset_contract` | dict | Data requirements spec |
| `metric_protocol` | dict | Metric definition and tolerance spec |

### Authorization

| Field | Type | Description |
|---|---|---|
| `authorization_contract_ref` | dict | `{contract_id, path}` reference |

### Budgets

| Field | Type | Description |
|---|---|---|
| `budgets.time_minutes` | int | Maximum wall-clock time |
| `budgets.disk_gb` | int | Disk budget in GB |
| `budgets.vram_gb` | int | VRAM budget in GB |
| `budgets.temperature_c` | int | Thermal limit °C |
| `budgets.max_retries` | int | Retry cap |

### Tasks

Each task must include:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | ✅ | Unique within plan |
| `name` | string | ✅ | Human-readable name |
| `gate` | string | ✅ | Gate this task belongs to |
| `deps` | list[string] | ✅ | Task IDs this depends on |
| `command` | string or list | ✅ | argv or shell command |
| `shell` | bool | | If true, run via `/bin/sh -c` |
| `timeout_min` | float | ✅ | Timeout in minutes |
| `acceptance_tests` | list[string] | ✅ | **Must not be empty** |
| `retry_policy` | dict | | `{max_attempts, backoff_seconds, retry_on_exit_codes}` |
| `resource_requirements` | dict | | gpu_ids, memory, disk, etc. |
| `writes` | list[string] | | Allowed write glob paths |
| `decision_point` | string | | Named decision point |

**Rule**: Tasks with empty or missing `acceptance_tests` fail schema validation.

### Constraints

| Field | Type | Description |
|---|---|---|
| `writes` | list[string] | Global allowed write roots |
| `rollback_strategy` | string | Strategy name |
| `mandatory_artifacts` | list[string] | Artifacts that must be produced |
| `decision_points` | list[string] | Named decision points in plan |

## Plan Hashes

Two hashes are maintained:

- `source_sha256`: SHA-256 of the raw YAML file bytes (proof of exact file)
- `canonical_plan_hash`: SHA-256 of the normalised content dict (ignores schema_version and source file metadata)

Plan hash changes trigger:
1. Project enters `WAITING_DECISION`
2. Existing authorization contract suspended
3. `plan_diff` output to `execution/reports/`

## Gate Data Constraint (Fail-Closed)

A task gate is `PASSED` only when:
- The task transitioned to `PASSED` via `evidence_verifier` or `acceptance`
- A valid acceptance test trace exists in `evidence_refs`

Human operators can only:
- `APPROVE` / `REJECT` / `WAIVE` from `WAITING_APPROVAL`
- Clear `BLOCKED` → `READY`

Humans **cannot** set `PASSED` directly.