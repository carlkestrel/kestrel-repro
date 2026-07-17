# Test & CI Readiness Analysis

**Plugin:** `dl-paper-repro` (`/home/carlkestrel/.cursor/plugins/local/kestrel-repro`)
**Date:** 2026-07-17
**Author:** CI readiness analysis

---

## 1. Test File Inventory

### 1.1 `tests/` Directory (20 files)

| File | Lines | What It Tests |
|---|---|---|
| `test_ostar.py` | ~436 | OSTAR module: constants, config, SoakStateStore, HardwareMonitor, Guard, RepairNode, TestSuites, ExitValidator, CLI smoke |
| `test_stabilization.py` | ~216 | Migration (schema versioning, dry-run, backup, rollback), backup snapshot, integrity check (orphan running, missing evidence, empty acceptance), CLI dispatch |
| `test_handoff.py` | ~57 | Handoff JSON template (12 required fields), round-trip serialization |
| `test_orchestrator.py` | ~807 | Full task orchestrator: serial/parallel tasks, retry, blocked, approval gate, pause/resume/stop, recovery after kill, daemon lifecycle (D2/D3), policy changes |
| `test_checkpoint_recovery.py` | ~41 | Checkpoint metadata round-trip, resume continuity |
| `test_plugin_discovery.py` | ~70 | Cursor plugin manifest (valid JSON, commands dir, agents dir, YAML frontmatter) |
| `test_metrics_recompute.py` | ~43 | Per-class IoU recompute from confusion matrix, aggregate tolerance check |
| `test_regression.py` | ~103 | Plugin evolution regression guard (9 items: manifest, commands, agents, templates, mode defaults, loop subcommand, metrics file, traceability, rollback) |
| `test_human_checkpoint.py` | ~61 | Human checkpoint flag logic (check/override/approver), 12-item list |
| `test_parity.py` | ~27 | Strict vs optimized parity within tolerance, failure flagging |
| `test_chaos.py` | ~806 | 15 chaos tests (SIGKILL, SIGTERM, checkpoint interruption, SQLite lock, JSON half-write, disk full, missing data, checkpoint corruption, GPU unavailable, log stall, plan change during recovery, plugin upgrade, evidence deleted, max retry, false complete) |
| `test_repro_perf.py` | ~259 | ReproPerf AutoTuner acceptance (15 test cases: parse, templates, schemas, command, health/baseline/capacity/parity/soak/recommend phases, strict/optimized separation, 12 rules, CSV columns, rollback triggers) |
| `test_l0_l3.py` | ~64 | L0 smoke, L1 overfit, L2 mini-loop, L3 checkpoint_resume |
| `test_startup.py` | ~1184 | 20 startup test cases: modules load, secrets redactor, lock acquire/release/stale, config priority, plan validation, doctor checks, state machine, recovery, stop, + 11 integration tests via real `reproctl.py` CLI |
| `test_minimal_e2e.py` | ~58 | Minimal PyTorch fixture: artifact layout, determinism |
| `test_mode_switch.py` | ~49 | Mode switching: valid/invalid modes, decision logging |
| `test_state_machine.py` | ~76 | State machine: valid modes, default state (HUMAN_CHECKPOINT=true, WIP_LIMIT=1), round-trip |

### 1.2 `scripts/` Test Helpers (4 files)

| File | Purpose | Type |
|---|---|---|
| `scripts/smoke_test.py` | L0: forward+backward pass with PyTorch | Standalone script |
| `scripts/overfit_test.py` | L1: memorize single batch | Standalone script |
| `scripts/mini_loop_test.py` | L2: 2-3 epoch training on tiny data | Standalone script |
| `scripts/checkpoint_resume_test.py` | L3: save/load checkpoint, hash check | Standalone script |

### 1.3 Fixture-Level Tests (2 files)

| File | Fixture | Purpose |
|---|---|---|
| `fixtures/golden_torch_A/test_golden_torch_A.py` | `golden_torch_A` | Fixture-specific test |
| `fixtures/golden_pointcloud_B/test_golden_pointcloud_B.py` | `golden_pointcloud_B` | Fixture-specific test |
| `scripts/repro_agent/metrics/golden_test.py` | Metrics | Metric golden test |
| `scripts/overfit_test.py` | (standalone) | Overfit harness |
| `scripts/mini_loop_test.py` | (standalone) | Mini-loop harness |
| `scripts/checkpoint_resume_test.py` | (standalone) | Checkpoint harness |
| `scripts/smoke_test.py` | (standalone) | Smoke harness |

### 1.4 `conftest.py`

- **Location:** `tests/conftest.py`
- **Purpose:** Sets up `sys.path` to include `scripts/` before any test imports, enabling relative imports of `orchestrator`, `startup`, `ostar`, etc.

---

## 2. Per-Test Requirements Analysis

### Resource Dependency Matrix

| Test File | GPU Required | Network Required | Data Download | Can Run Offline | Notes |
|---|---|---|---|---|---|
| `test_ostar.py` | No | No | No | **Yes** | Pure unit tests + CLI smoke |
| `test_stabilization.py` | No | No | No | **Yes** | Migration, backup, integrity checks |
| `test_handoff.py` | No | No | No | **Yes** | JSON round-trip only |
| `test_orchestrator.py` | No | No | No | **Yes** | Subprocess task simulation |
| `test_checkpoint_recovery.py` | No | No | No | **Yes** | JSON-only round-trips |
| `test_plugin_discovery.py` | No | No | No | **Yes** | File existence + YAML parsing |
| `test_metrics_recompute.py` | No | No | No | **Yes** | Pure math on confusion matrices |
| `test_regression.py` | No | No | No | **Yes** | File content + subprocess check |
| `test_human_checkpoint.py` | No | No | No | **Yes** | State file read/write |
| `test_parity.py` | No | No | No | **Yes** | Numeric tolerance checks |
| `test_chaos.py` | **May need** | No | No | **Partial** | Uses `fixtures/golden_torch_A`; some tests use `CUDA_VISIBLE_DEVICES=""` to simulate no GPU; fixture may not be present in all envs |
| `test_repro_perf.py` | **May need** | No | No | **Partial** | Runs `repro_perf_tuner.py` scripts; health/baseline/capacity phases spawn subprocesses that may need torch |
| `test_l0_l3.py` | **Yes** | No | No | **Conditional** | Runs L0-L3 scripts which spawn `python -c` with `torch.*` — needs torch installed but not a real GPU |
| `test_startup.py` | **Partial** | **Partial** | No | **Partial** | Unit tests are offline; integration tests run real CLI (git init, file I/O); `fake_cuda` monkeypatches torch; GPU tests pass through REPRO_FAKE_GPU=0 |
| `test_minimal_e2e.py` | **Yes** | No | No | **Conditional** | Runs `fixtures/minimal_pytorch_repo/train.py`; needs torch installed |
| `test_mode_switch.py` | No | No | No | **Yes** | State file operations only |
| `test_state_machine.py` | No | No | No | **Yes** | State file round-trip only |

### Key Findings

- **Majority of tests are offline-capable**: 13 of 17 test files require no network, no GPU, no downloads.
- **GPU is NOT universally required**: Even "GPU tests" like `test_l0_l3.py` and `test_minimal_e2e.py` run CPU-only PyTorch operations. `test_chaos.py` explicitly handles missing GPU via `CUDA_VISIBLE_DEVICES=""`.
- **`fixtures/` are optional**: Several tests conditionally skip if fixtures are absent (e.g., `golden_torch_A`, `minimal_pytorch_repo`).
- **`git` is required** for `test_startup.py` integration tests and `test_ostar.py`'s `test_guard_run()` — but these can be satisfied with `git init` in temp directories.

---

## 3. Test Categorization

### Category A: Unit Tests (No External Dependencies)

Pure logic tests, no I/O except `tmp_path`, no network, no GPU.

- `test_handoff.py` — JSON serialization
- `test_checkpoint_recovery.py` — metadata math
- `test_plugin_discovery.py` — file existence + YAML parsing
- `test_metrics_recompute.py` — IoU/confusion matrix math
- `test_parity.py` — numeric tolerance
- `test_mode_switch.py` — state machine transitions
- `test_state_machine.py` — state defaults and round-trip
- `test_human_checkpoint.py` — flag logic
- `test_ostar.py` (unit subset) — constants, config, SoakStateStore, RepairNode fingerprinting

### Category B: Integration Tests (Some System Dependencies)

Test internal integrations with real files, SQLite, subprocesses, but no network.

- `test_orchestrator.py` — full scheduler/controller with real subprocess tasks
- `test_stabilization.py` — migration, backup, SQLite integrity
- `test_startup.py` (integration subset) — CLI via `reproctl.py`, git init, lock files
- `test_regression.py` — plugin evolution guard (file reads + subprocess)
- `test_ostar.py` (CLI smoke subset) — `reproctl soak --help`

### Category C: Smoke Tests (Basic Sanity)

Fast sanity checks to verify the system is operational.

- `scripts/smoke_test.py` (L0) — forward/backward pass
- `scripts/overfit_test.py` (L1) — single-batch memorization
- `test_l0_l3.py` — wrapper that runs L0-L3 scripts

### Category D: Full Tests (Require GPU / Real Fixtures / Data)

Tests that need actual training scripts, GPU, or large fixtures.

- `test_chaos.py` — 15 chaos scenarios; most need `golden_torch_A` fixture
- `test_repro_perf.py` — ReproPerf AutoTuner phases (health, baseline, capacity); some phases spawn real training
- `test_minimal_e2e.py` — runs `minimal_pytorch_repo/train.py`; needs torch installed
- `test_l0_l3.py` — runs actual L0-L3 scripts with torch
- `test_chaos.py::TestGpuUnavailable` — explicitly tests GPU unavailability path

### Recommended Category Labels for CI

| CI Level | Tests | Runtime Estimate |
|---|---|---|
| **Level 1** (fast, always) | Unit tests: `test_handoff`, `test_checkpoint_recovery`, `test_plugin_discovery`, `test_metrics_recompute`, `test_parity`, `test_mode_switch`, `test_state_machine`, `test_human_checkpoint`, plus `test_ostar.py` unit subset | ~30s |
| **Level 2** (moderate, on PR) | Integration: `test_orchestrator`, `test_stabilization`, `test_regression`, `test_startup` (unit portion), `test_ostar.py` (CLI smoke) | ~2–5 min |
| **Level 3** (slow, GPU/manual) | Full: `test_chaos.py`, `test_repro_perf.py`, `test_minimal_e2e.py`, `test_l0_l3.py`, `test_startup.py` (integration) | ~10–30 min |

---

## 4. CI Configuration Audit

### Existing CI Files

| Path | Status |
|---|---|
| `.github/workflows/` | **DOES NOT EXIST** |
| `.gitlab-ci.yml` | **DOES NOT EXIST** |
| `*ci*.yml` / `*ci*.yaml` | **NONE FOUND** |
| `setup.py` | **DOES NOT EXIST** |
| `requirements.txt` (root) | **DOES NOT EXIST** |
| `pyproject.toml` | **DOES NOT EXIST** |

**Conclusion:** No CI configuration exists. The repository is not yet CI-ready.

### Fixture Requirements (Only for Full Tests)

| Fixture | Requirements | Notes |
|---|---|---|
| `fixtures/golden_torch_A/` | `torch>=2.0.0` | Minimal PyTorch fixture |
| `fixtures/golden_pointcloud_B/` | `torch>=2.0.0` | Point cloud fixture |
| `fixtures/minimal_pytorch_repo/` | None specified (built-in torch) | Train script for e2e tests |

No root-level `requirements.txt` exists. All dependencies are implicit (PyTorch, standard library, pytest).

---

## 5. Proposed CI Levels

### CI Level 1: Quality Gates (Fast, Every PR + Push)

**Goal:** Catch regressions in < 2 minutes. No GPU, no network, no downloads.

**Run:**
```
pytest tests/ -v -x
  --ignore=tests/test_chaos.py
  --ignore=tests/test_repro_perf.py
  --ignore=tests/test_minimal_e2e.py
  --ignore=tests/test_l0_l3.py
  --ignore=tests/test_startup.py
```

**Tests included:**
- `test_ostar.py` (constants, config, SoakStateStore, RepairNode, CLI smoke)
- `test_stabilization.py` (migration, backup, integrity)
- `test_handoff.py`
- `test_orchestrator.py` (task scheduler)
- `test_checkpoint_recovery.py`
- `test_plugin_discovery.py`
- `test_metrics_recompute.py`
- `test_regression.py`
- `test_human_checkpoint.py`
- `test_parity.py`
- `test_mode_switch.py`
- `test_state_machine.py`

**Also include:**
- Python syntax check on all `.py` files
- YAML syntax validation on all `.yaml` files in `templates/`
- JSON syntax validation on all `.json` files in `templates/`

**Tool suggestions:** `black --check`, `ruff check`, `mypy --ignore-missing-imports`

### CI Level 2: Integration & CLI (Moderate, On PR)

**Goal:** Verify CLI dispatch, startup, plugin discovery in ~5 minutes.

**Run:**
```
pytest tests/test_startup.py -v -x
pytest tests/test_regression.py -v
pytest tests/test_orchestrator.py -v -x
pytest tests/test_stabilization.py -v -x
```

**Also run:**
- `python scripts/reproctl.py --help` smoke
- `python scripts/reproctl.py version`
- `python -m pytest tests/test_ostar.py::test_cli_help -v`

**Requirements:**
- Python 3.10+ with pytest
- `git` available (used for `git init` in temp directories)
- No GPU required; CPU-only mode

### CI Level 3: Full Suite (Slow, Manual Trigger + GPU Runners)

**Goal:** Validate full training pipeline, chaos resilience, performance tuning.

**Run (with GPU):**
```
pytest tests/test_chaos.py -v -x
pytest tests/test_repro_perf.py -v -x
pytest tests/test_minimal_e2e.py -v -x
pytest tests/test_l0_l3.py -v -x
```

**Requirements:**
- NVIDIA GPU with CUDA 11.8+
- PyTorch with CUDA support (`torch>=2.0.0`)
- Fixtures present (`fixtures/golden_torch_A/`, `fixtures/minimal_pytorch_repo/`)
- 30–60 minute timeout

**Trigger options:**
- Manual `workflow_dispatch`
- Tag-based: `workflow_run` on tag push
- Nightly scheduled run

---

## 6. Proposed GitHub Actions Workflow File Content

> **Note:** These are proposed contents only. Do NOT create the actual workflow files yet. This section documents what should be created when CI is implemented.

### File: `.github/workflows/ci-l1.yml`

```yaml
name: CI Level 1 — Quality Gates

on:
  push:
    branches: [main, repro/**]
  pull_request:
    branches: [main]

jobs:
  quality-gates:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest ruff black mypy pyyaml

      - name: Python syntax check
        run: python -m py_compile $(find . -name "*.py" | grep -v __pycache__)

      - name: YAML validation
        run: |
          pip install yamllint
          yamllint templates/ .cursor-plugin/ commands/ --strict

      - name: JSON validation
        run: |
          find templates/ -name "*.json" -exec python -c "import json,sys; json.load(open(sys.argv[1]))" {} \;

      - name: Run Level 1 tests
        run: |
          pytest tests/ -v -x \
            --ignore=tests/test_chaos.py \
            --ignore=tests/test_repro_perf.py \
            --ignore=tests/test_minimal_e2e.py \
            --ignore=tests/test_l0_l3.py \
            --ignore=tests/test_startup.py

      - name: Code style check
        run: |
          ruff check . --fix || true
          black --check .

      - name: Type check (minimal)
        run: mypy scripts/ostar/ scripts/startup/ scripts/orchestrator/ \
            --ignore-missing-imports --follow-imports=skip 2>&1 || true
```

### File: `.github/workflows/ci-l2.yml`

```yaml
name: CI Level 2 — Integration

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  integration:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pyyaml

      - name: CLI smoke
        run: |
          python scripts/reproctl.py --help
          python scripts/reproctl.py version

      - name: Run startup tests (unit + integration)
        run: pytest tests/test_startup.py -v -x

      - name: Run regression and orchestrator tests
        run: |
          pytest tests/test_regression.py -v
          pytest tests/test_orchestrator.py -v -x
          pytest tests/test_stabilization.py -v -x
```

### File: `.github/workflows/ci-l3.yml`

```yaml
name: CI Level 3 — Full Suite (GPU)

on:
  workflow_dispatch:
    inputs:
      test_target:
        description: "Test target"
        required: false
        default: "all"
  schedule:
    # Nightly at 2 AM UTC
    - cron: "0 2 * * *"
  push:
    tags:
      - 'v*'

jobs:
  full-suite:
    runs-on: ["self-hosted", "gpu"]
    timeout-minutes: 60
    container:
      image: pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime
      options: --gpus all

    steps:
      - uses: actions/checkout@v4

      - name: Install test dependencies
        run: pip install pytest pyyaml

      - name: Verify fixtures
        run: |
          ls fixtures/golden_torch_A/
          ls fixtures/minimal_pytorch_repo/

      - name: Run chaos tests
        run: pytest tests/test_chaos.py -v --timeout=600

      - name: Run ReproPerf acceptance
        run: pytest tests/test_repro_perf.py -v --timeout=300

      - name: Run L0-L3 scripts
        run: pytest tests/test_l0_l3.py -v --timeout=300

      - name: Run minimal e2e
        run: pytest tests/test_minimal_e2e.py -v --timeout=120
```

---

## 7. Test Dependencies Summary

### Required for CI Level 1 & 2

```
pytest>=7.0.0
pyyaml>=6.0
```

### Optional (for linting/type-checking L1)

```
ruff>=0.1.0
black>=23.0.0
mypy>=1.0.0
yamllint>=1.28.0
```

### Required for CI Level 3

```
torch>=2.0.0          # CUDA-enabled for GPU tests
pytest>=7.0.0
```

### Test Framework

- **Primary:** `pytest` — used by 15 of 17 test files
- **No `unittest`/`nose`:** Tests use pure `assert` + pytest conventions
- **`conftest.py`:** Present at `tests/conftest.py`; sets up `sys.path` for `scripts/` imports

### Implicit Dependencies (Not in requirements.txt)

These are imported by tests but not listed in any requirements file:

| Module | Source | Used By |
|---|---|---|
| `torch` | system-installed | `test_l0_l3.py`, `test_minimal_e2e.py`, `test_chaos.py` |
| `sqlite3` | stdlib | `test_chaos.py`, `test_stabilization.py` |
| `git` | system binary | `test_startup.py`, `test_ostar.py` |
| `json`, `pathlib`, `subprocess`, `tempfile` | stdlib | All tests |
| `shutil`, `threading`, `signal`, `socket` | stdlib | Various |

---

## 8. Recommendations

1. **Create a root `requirements-dev.txt`** listing at minimum: `pytest`, `pyyaml`. This makes CI dependency installation explicit.

2. **Create a `pyproject.toml`** with pytest configuration to avoid `--ignore` complexity. Example:

   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   ignore = [
       "tests/test_chaos.py",
       "tests/test_repro_perf.py",
       "tests/test_minimal_e2e.py",
       "tests/test_l0_l3.py",
   ]
   ```

3. **Add `.github/workflows/`** directory with the three workflow files described above. Level 1 should run on every push/PR. Level 3 should be manual/scheduled.

4. **Document fixture setup** in CI: Level 3 tests depend on `fixtures/golden_torch_A/` and `fixtures/minimal_pytorch_repo/`. These should be checked into the repo or cloned as part of CI setup.

5. **Consider adding `pytest-timeout`** to prevent hung tests in CI (e.g., `test_chaos.py::TestExecutorKilled` runs long tasks).

6. **`test_startup.py`** integration tests create git repositories with `git init` in temp directories — this requires `git` to be available in the CI environment. Standard Ubuntu/Windows runners have `git` pre-installed.

7. **Chaos tests** (`test_chaos.py`) are the most realistic but also the most fragile. They should be quarantined to Level 3 and reviewed periodically for flakiness.

---

*End of analysis.*
