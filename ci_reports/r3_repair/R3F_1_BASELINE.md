# R3F-1 Report — Fix CI YAML syntax + actionlint

**Date**: 2026-07-18
**Phase**: R3F-1
**Branch**: `review/r3-20260718-a828023`
**Start SHA**: `f28f0eb6832450355a5f5077b36bcfa394152cbb`
**End SHA (local)**: _filled after commit_

---

## 1. Starting state

All three GitHub Actions workflows failed at YAML parse time → **0 Jobs created**.
`actionlint` reported `could not parse as YAML: yaml: line N: could not find expected ':' [syntax-check]` for each.

| File | Line | Root cause |
|---|---|---|
| ci-l1.yml | 54 | `python3 -c "..."` block with content starting at column 0 — YAML's quoted-scalar rules reject bare-newline continuation; intent was multi-line Python |
| ci-l2.yml | 156 | same pattern (orchestrator import smoke) |
| ci-l3.yml | 184 | same pattern (torch CUDA check); also `sys.exit(0)` after WARNING line masked missing GPU |

## 2. Fixes applied

### 2.1 ci-l1.yml — 3 blocks converted to heredocs

- `Import smoke` (line 49–66): `python3 -c "..."` → `python3 - <<'PYEOF' ... PYEOF`
- `Validate schemas` (line 115–128): same conversion
- `Orchestrator import tests` (line 205–216): same conversion

### 2.2 ci-l2.yml — 3 blocks converted to heredocs

- `Orchestrator package import` (line 152–164)
- `CVO import tests` (line 170–184)
- `Audit CLI import smoke` (line 190–204)

### 2.3 ci-l3.yml — 1 block converted, env-context misuse fixed

- `Verify GPU detected` (line 181–196): heredoc + removed `sys.exit(0)` that masked missing GPU.
- `golden-fixtures` job (line 132): replaced `env.TORCH_INDEX_URL` (job-level env cannot reference workflow env context) with `inputs.torch_index_url || ...` mirror.
- `gpu-tests` job (line 163): replaced `env.GPU_ENABLED == 'true' || inputs.gpu_enabled == true` with just `inputs.gpu_enabled == true`.
- `gpu-tests` job runs-on (line 162): replaced opaque `github.run_id == 0 && '...' || '...'` with `ubuntu-latest`; the job's `if:` gate is now the single source of truth for whether it runs.

### 2.4 Removed test exit-code swallowing

`remaining-tests` job had `pytest ... || echo "Some tests may have been skipped"`. Replaced with `set +e` + explicit `rc=$?` + `exit "$rc"` so failures produce non-zero exit and surface as Job failure.

### 2.5 New manifest job in ci-l1

Added a `manifest` job (runs first) that emits `ci_reports/ci_l1_manifest.json` declaring exactly what CI-L1 covers and explicitly lists what it does NOT cover (GPU parity, real paper reproduction, long training, network).

## 3. Verification

| Check | Command | Result |
|---|---|---|
| actionlint | `/tmp/actionlint -no-color .github/workflows/*.yml` | exit 0, no errors |
| YAML parser | `yaml.safe_load` on each workflow | 5+4+7 jobs |
| Job count | ci-l1: 5, ci-l2: 4, ci-l3: 7 | total **16** jobs declared |
| Heredoc indentation | re-read each block | content at col ≥ 10, EOF on its own line |

## 4. Jobs declared per workflow

### ci-l1.yml (CPU, fast)
1. `manifest` — emit level-1 manifest
2. `syntax` — py_compile all .py files
3. `validate-configs` — YAML / JSON / schema validation
4. `ruff-lint` — ruff check + format check
5. `pytest-unit` — plugin_discovery, startup, state_machine, orchestrator import

### ci-l2.yml (integration)
1. `cli-smoke` — reproctl CLI smoke
2. `startup-integration` — config / plan / doctor / state_machine / lock manager
3. `config-parsing` — JSON / YAML config parsing
4. `orchestrator-import` — orchestrator & CVO import smoke

### ci-l3.yml (full, GPU conditional)
1. `l0-l3-verification` — short-loop L0–L3
2. `orchestrator-full` — full orchestrator suite (incl. test_orchestrator.py)
3. `startup-full` — full test_startup.py
4. `golden-fixtures` — golden torch_A & golden pointcloud_B
5. `gpu-tests` — gated by `inputs.gpu_enabled == true`; runs on `ubuntu-latest` when dispatched, otherwise Job is skipped
6. `cvo-full` — audit validate / init / plan / status
7. `remaining-tests` — handoff, stabilization, human_checkpoint, metrics_recompute, parity, checkpoint_recovery, ostar, regression, chaos, repro_perf, mode_switch (with explicit exit-code handling)

## 5. Acceptance verdict

- [x] All 3 workflows pass `actionlint`
- [x] All 3 workflows pass `yaml.safe_load`
- [x] 16 Jobs declared, 0 opaque `runs-on` trick
- [x] No `pytest ... || echo` swallow
- [x] CPU CI has manifest declaring it does not claim GPU parity
- [x] GPU Job uses `if: ${{ inputs.gpu_enabled == true }}` and reports `NO_GPU` / `NO_TORCH` honestly

**Local verification PASS. Ready to commit and push.**

Remote GitHub Actions verification requires the push to be authorized under C-mode and is performed after this commit lands on `review/r3-20260718-a828023`.
