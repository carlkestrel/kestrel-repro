# R2 Authorization Contract Schema

**File**: `.repro/authorization_contract.yaml`
**Schema**: Structured YAML
**Deny-by-default**: Any action not explicitly listed in `granted_actions` is denied.

## Required Fields

| Field | Type | Description |
|---|---|---|
| `contract_id` | string | Unique contract identifier |
| `project_root` | string | Absolute path to project |
| `project_id` | string | Project identifier |
| `canonical_plan_hash` | string | Hash of the plan this contract governs |
| `git_commit` | string | Git commit this contract is valid for |
| `created_at` | ISO-8601 | Contract creation timestamp |
| `expires_at` | ISO-8601 | Expiration timestamp (optional) |

## Action Grants

| Field | Type | Description |
|---|---|---|
| `granted_actions` | list[string] | Explicitly allowed actions |
| `denied_actions` | list[string] | Explicitly denied actions (for auditing) |
| `*` (wildcard) | — | If `*` is in `granted_actions`, all actions are allowed |

## Write Constraints

| Field | Type | Description |
|---|---|---|
| `allowed_write_roots` | list[string] | Paths relative to `project_root` where writes are permitted |

### Write Path Rules

1. **No absolute paths bypass**: Absolute paths are resolved relative to `project_root`
2. **`..` traversal**: Resolved paths are normalised; traversal outside `allowed_write_roots` is denied
3. **Symlink exits**: Real-path resolution is applied; symlink traversal is blocked

## Network and Dependency Policies

| Field | Values | Description |
|---|---|---|
| `network_policy` | `allow`, `deny`, `read-only` | Internet access |
| `clone_policy` | `allow`, `deny` | Git clone / download |
| `download_policy` | `allow`, `deny` | Data download |
| `dependency_install_policy` | `allow`, `deny` | pip / conda install |
| `source_modification_policy` | `allow`, `deny` | Modifying repo source |
| `gpu_execution_policy` | `allow`, `deny` | GPU training |

## Execution Policies

| Field | Type | Description |
|---|---|---|
| `training_stages` | list[string] | Allowed training stage names |
| `local_commit_permission` | bool | May create local commits |
| `push_pr_permission` | bool | May push or create PRs |
| `release_permission` | bool | May create releases |

## Budgets

| Field | Type | Description |
|---|---|---|
| `time_budget_minutes` | int | Max wall-clock minutes |
| `disk_budget_gb` | int | Max disk used (GB) |
| `vram_budget_gb` | int | Max VRAM used (GB) |
| `temperature_limit_c` | int | Thermal limit (°C) |
| `retry_limit` | int | Max retries per task |

## Revocation

| Field | Values | Description |
|---|---|---|
| `revocation_state` | `active`, `revoked`, `expired` | Current revocation state |

## Automatic Revocation Triggers

The following conditions automatically invalidate a contract:

1. `canonical_plan_hash` changes
2. `project_root` path changes
3. Write to a path outside `allowed_write_roots`
4. Any budget exceeded (`time_budget_minutes`, `disk_budget_gb`, `vram_budget_gb`)
5. `expires_at` timestamp passed
6. `revocation_state` changed to `revoked` or `expired`
7. Git commit diverges from `git_commit` (if enforced)