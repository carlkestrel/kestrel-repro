# kestrel-repro Directory Structure Analysis

## 1. Current Structure

```
kestrel-repro/
├── agents/                     # Agent markdown definitions
│   ├── repo-scout.md
│   ├── evidence-verifier.md
│   ├── data-metric-auditor.md
│   ├── hardware-fit-auditor.md
│   ├── repro-lead.md
│   ├── runtime-optimizer.md
│   └── review-auditor.md
├── scripts/                    # All Python source code
│   ├── orchestrator/           # Core execution engine
│   │   ├── agents/             # NORA specialist agents
│   │   ├── __init__.py         # Re-exports public API
│   │   ├── controller.py      # Main run loop
│   │   ├── state_store.py     # SQLite-backed state
│   │   ├── task_executor.py   # Subprocess launcher
│   │   ├── process_manager.py # Process lifecycle
│   │   ├── scheduler.py       # Task scheduling
│   │   ├── policy_engine.py   # Approval gates
│   │   ├── approval_gate.py   # Approval queue
│   │   ├── verifier.py        # Acceptance test runner
│   │   ├── watchdog.py        # Timeout handling
│   │   ├── event_journal.py   # JSONL audit log
│   │   ├── recovery.py        # Crash recovery
│   │   ├── stop_hook.py       # Signal handling
│   │   ├── cli.py
│   │   ├── report_generator.py
│   │   ├── evidence_manager.py
│   │   ├── backup.py
│   │   ├── migrate.py
│   │   ├── event_journal.py
│   │   ├── state_store.py
│   │   └── verifier.py
│   ├── ostar/                  # Overnight Soak Test + Auto-Repair
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── soak_engine.py
│   │   ├── soak_state.py
│   │   ├── hardware_monitor.py
│   │   ├── guard.py
│   │   ├── test_suites.py
│   │   ├── repair_node.py
│   │   ├── reporter.py
│   │   ├── exit_validator.py
│   │   ├── config.py
│   │   └── constants.py
│   ├── cvo/                     # Checkpointed Validation Orchestrator
│   │   ├── __init__.py
│   │   ├── runner.py
│   │   ├── nodes.py
│   │   ├── state.py
│   │   ├── val_000.py
│   │   └── val_010.py
│   ├── repro_agent/             # Reproduction agent with metrics
│   │   ├── __init__.py
│   │   └── metrics/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       ├── registry.py
│   │       ├── schemas.py
│   │       ├── golden_test.py
│   │       ├── recompute.py
│   │       ├── conflict_detector.py
│   │       ├── hardcode_detector.py
│   │       └── takeover.py
│   ├── startup/                 # Bootstrap and init system
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── config.py
│   │   ├── state_machine.py
│   │   ├── plan_validate.py
│   │   ├── doctor.py
│   │   ├── lock.py
│   │   ├── log_setup.py
│   │   ├── secrets_redactor.py
│   │   ├── recovery.py
│   │   └── generate_artifacts.py
│   ├── research_crawler.py
│   ├── reproctl.py              # CLI entry point
│   ├── autopilot.py
│   ├── compare_runs.py
│   ├── benchmark_runtime.py
│   ├── overfit_test.py
│   ├── environment_check.py
│   ├── artifact_verify.py
│   ├── hardware_profile.py
│   ├── training_monitor.py
│   ├── repro_perf_tuner.py
│   ├── checkpoint_resume_test.py
│   ├── smoke_test.py
│   ├── mini_loop_test.py
│   └── l0_l3_loop.py
├── tests/                       # All pytest tests
│   ├── test_orchestrator.py     # Main orchestrator tests (17 tests)
│   ├── test_ostar.py            # OSTAr tests
│   ├── test_checkpoint_recovery.py
│   ├── test_handoff.py
│   ├── test_human_checkpoint.py
│   ├── test_l0_l3.py
│   ├── test_metrics_recompute.py
│   ├── test_minimal_e2e.py
│   ├── test_mode_switch.py
│   ├── test_parity.py
│   ├── test_plugin_discovery.py
│   ├── test_regression.py
│   ├── test_repro_perf.py
│   ├── test_startup.py
│   ├── test_state_machine.py
│   └── test_stabilization.py
├── fixtures/                    # Test fixtures and sample repos
│   ├── golden_torch_A/          # Sample PyTorch project fixture
│   │   ├── test_golden_torch_A.py
│   │   └── plan.yaml
│   ├── golden_pointcloud_B/     # Sample point cloud fixture
│   │   ├── test_golden_pointcloud_B.py
│   │   └── plan.yaml
│   └── minimal_pytorch_repo/
├── tooling/                     # External tooling dependencies
├── skills/                      # Cursor skill definitions
│   ├── paper-reproduction/
│   │   └── SKILL.md
│   ├── deep-learning-runtime/
│   │   └── SKILL.md
│   ├── point-cloud-reproduction/
│   │   └── SKILL.md
│   └── repository-selection/
│       └── SKILL.md
├── docs/                        # Documentation
│   ├── README.md
│   ├── STARTUP.md
│   ├── architecture.md
│   ├── complete_manual.md
│   ├── quickstart.md
│   ├── troubleshooting.md
│   ├── hardware_and_performance.md
│   ├── command_reference.md
│   ├── configuration_reference.md
│   ├── automation_workflow.md
│   ├── bug_repair.md
│   ├── takeover_workflow.md
│   ├── glossary.md
│   ├── faq.md
│   ├── security.md
│   ├── roadmap.md
│   ├── new_project_workflow.md
│   ├── testing_and_ci.md
│   ├── reproduction_protocol.md
│   ├── orchestrator/
│   │   ├── RUN_LOOP.md
│   │   └── PLAN_SCHEMA.md
│   ├── html/
│   │   └── reports/
│   └── generated/
├── commands/                    # Command documentation
│   ├── repro-start.md
│   ├── repro-launch.md
│   ├── repro-status.md
│   ├── repro-verify.md
│   ├── repro-audit.md
│   ├── repro-report.md
│   ├── repro-monitor.md
│   ├── repro-card.md
│   ├── repro-contract.md
│   ├── repro-decision.md
│   ├── repro-autopilot.md
│   ├── repro-short-loop.md
│   ├── repro-handoff.md
│   ├── repro-resume.md
│   ├── repro-failure.md
│   ├── repro-stop.md
│   ├── repro-preflight.md
│   ├── repro-plan.md
│   ├── repro-doctor.md
│   ├── repro-init.md
│   ├── repro-discover.md
│   ├── repro-fit-hardware.md
│   ├── repro-benchmark.md
│   ├── repro-crawl.md
│   ├── repro-evidence-chain.md
│   ├── repro-review.md
│   ├── repro-perf.md
│   ├── repro-acquire.md
│   ├── repro-evolution.md
│   ├── geoai-discover.md
│   ├── geoai-audit.md
│   ├── research-extend.md
│   ├── ostar/ (soak test commands)
│   └── repro-*.md (20+ additional)
├── templates/                   # Template files for new projects
│   ├── repro_spec.yaml
│   ├── search_plan.yaml
│   ├── repo_adapter.yaml
│   ├── data_card.md
│   ├── data_contract.md
│   ├── project_memory.md
│   ├── project_structure.md
│   ├── experiment_plan.md
│   ├── narrative_report.md
│   ├── failure_case_report.md
│   ├── claim_evidence_matrix.md
│   ├── metric_protocol_audit.md
│   ├── decision_log.md
│   ├── control_flags.md
│   ├── environment_card.md
│   ├── human_checkpoints.md
│   ├── research_contract.md
│   ├── dataset_registry.md
│   ├── sources.lock.yaml
│   ├── repository_security_audit.md
│   ├── repro_report_skeleton.md
│   ├── parameter_table.md
│   ├── hardware_fit_report.md
│   └── performance/
│       ├── health_report.md
│       ├── soak_test_report.md
│       ├── numerical_parity_report.md
│       ├── bottleneck_report.md
│       ├── recommendation.md
│       ├── strict_performance.yaml
│       ├── optimized_performance.yaml
│       └── safe_capacity.yaml
├── schemas/                     # JSON schemas
│   └── soak_config.schema.json
├── audits/                      # Audit reports
│   └── orchestrator_v0.1.0/
├── ci_reports/                  # CI output
├── primary/                     # (empty)
├── references/                  # (empty)
├── performance/                 # Performance reports (generated)
├── reports/                      # Generated reports (should not be in git)
├── artifacts/                   # Generated artifacts (should not be in git)
│   ├── smoke_check/
│   ├── statistical_reproduction/
│   ├── runs/
│   └── fast_exploration/
├── github_prep/                 # GitHub preparation work
├── .repro/                      # RUNTIME: Execution state (gitignore)
│   ├── audit/
│   └── execution/
├── .execution/                  # RUNTIME: Execution output (gitignore)
│   ├── commands/
│   ├── task_reports/
│   └── task_graph.yaml
├── .repair/                     # RUNTIME: Repair artifacts (gitignore)
│   ├── root_causes/
│   └── rollback/
├── .stabilization/              # RUNTIME: Stabilization data (gitignore)
├── .cache/                     # Python bytecode cache (gitignore)
├── .pytest_cache/              # Pytest cache (gitignore)
├── automation_policy.yaml       # Runtime policy config
├── AUTOMATION_ARCHITECTURE.md
├── AUTOPILOT_IMPLEMENTATION_PLAN.md
├── AUTOPILOT_IMPLEMENTATION_REPORT.md
├── CHANGELOG.md
├── FINAL_REPORT.md
├── METRIC_COMPONENT_ARCHITECTURE.md
├── NORA_ADAPTATION_NOTES.md
├── SELF_CHECK_REPORT.md
├── README.md
├── LICENSE
└── .gitignore
```

---

## 2. What Should NOT Be in Git

### Runtime Directories (Already Hidden with Dot-Prefix)

| Directory | Purpose | Should Be Gitignored |
|-----------|---------|---------------------|
| `.repro/` | Execution state: SQLite DB, event journals, task heartbeats | YES - not in git |
| `.repro/audit/` | Audit reports generated during runs | YES - not in git |
| `.execution/` | Task command scripts, task reports, task graph | YES - not in git |
| `.repair/` | Bug root cause analysis, rollback snapshots | YES - not in git |
| `.stabilization/` | Stabilization tracking data | YES - not in git |

### Generated Output Directories

| Directory | Purpose | Should Be Gitignored |
|-----------|---------|---------------------|
| `artifacts/` | Execution artifacts: run outputs, checkpoints, reports | YES - not in git |
| `reports/` | Generated reports | YES - not in git |
| `audits/` | Audit reports from execution | YES - not in git |
| `ci_reports/` | CI pipeline outputs | YES - not in git |
| `performance/` | Performance report outputs | YES - not in git |
| `.repro/audit/reports/` | Audit stage reports | YES - not in git |
| `artifacts/runs/run_*` | Timestamped run outputs | YES - not in git |

### Cache Directories

| Directory | Should Be Gitignored |
|-----------|---------------------|
| `__pycache__/` | YES - via `*.py[cod]` |
| `.cache/` | YES |
| `.pytest_cache/` | YES |
| `.mypy_cache/` | YES |
| `.tox/` | YES |

### Local Experiments (Should Not Be in Git)

| Pattern | Should Be Gitignored |
|---------|---------------------|
| `*.pt`, `*.pth`, `*.ckpt` | YES |
| `*.zip`, `*.tar.gz` | YES |
| `*.log` | YES |

---

## 3. Proposed Clean Repository Structure

### Recommended Layout

```
kestrel-repro/
├── src/                         # Core library code
│   ├── __init__.py
│   ├── orchestrator/            # (moved from scripts/orchestrator)
│   │   ├── __init__.py
│   │   ├── controller.py
│   │   ├── state_store.py
│   │   ├── task_executor.py
│   │   ├── process_manager.py
│   │   ├── scheduler.py
│   │   ├── policy_engine.py
│   │   ├── approval_gate.py
│   │   ├── verifier.py
│   │   ├── watchdog.py
│   │   ├── event_journal.py
│   │   ├── recovery.py
│   │   ├── stop_hook.py
│   │   ├── cli.py
│   │   ├── report_generator.py
│   │   ├── evidence_manager.py
│   │   ├── backup.py
│   │   └── agents/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── repo_scout.py
│   │       ├── paper_auditor.py
│   │       ├── metric_auditor.py
│   │       ├── hardware_fit.py
│   │       ├── evidence_verifier.py
│   │       └── review_auditor.py
│   ├── ostar/                   # (moved from scripts/ostar)
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── soak_engine.py
│   │   ├── soak_state.py
│   │   ├── hardware_monitor.py
│   │   ├── guard.py
│   │   ├── test_suites.py
│   │   ├── repair_node.py
│   │   ├── reporter.py
│   │   ├── exit_validator.py
│   │   ├── config.py
│   │   └── constants.py
│   ├── cvo/                     # (moved from scripts/cvo)
│   │   ├── __init__.py
│   │   ├── runner.py
│   │   ├── nodes.py
│   │   ├── state.py
│   │   ├── val_000.py
│   │   └── val_010.py
│   ├── repro_agent/             # (moved from scripts/repro_agent)
│   │   ├── __init__.py
│   │   └── metrics/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       ├── registry.py
│   │       ├── schemas.py
│   │       ├── golden_test.py
│   │       ├── recompute.py
│   │       ├── conflict_detector.py
│   │       ├── hardcode_detector.py
│   │       └── takeover.py
│   └── startup/                 # (moved from scripts/startup)
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── state_machine.py
│       ├── plan_validate.py
│       ├── doctor.py
│       ├── lock.py
│       ├── log_setup.py
│       ├── secrets_redactor.py
│       ├── recovery.py
│       └── generate_artifacts.py
├── scripts/                     # Executable entry points (CLI tools)
│   ├── reproctl.py              # Main CLI (renamed from scripts/reproctl.py)
│   ├── autopilot.py
│   ├── compare_runs.py
│   ├── benchmark_runtime.py
│   ├── overfit_test.py
│   ├── environment_check.py
│   ├── artifact_verify.py
│   ├── hardware_profile.py
│   ├── training_monitor.py
│   ├── repro_perf_tuner.py
│   ├── checkpoint_resume_test.py
│   ├── smoke_test.py
│   ├── mini_loop_test.py
│   ├── l0_l3_loop.py
│   └── research_crawler.py
├── tests/                       # All pytest tests
│   ├── __init__.py
│   ├── conftest.py             # Shared pytest fixtures
│   ├── test_orchestrator.py
│   ├── test_ostar.py
│   ├── test_checkpoint_recovery.py
│   ├── test_handoff.py
│   ├── test_human_checkpoint.py
│   ├── test_l0_l3.py
│   ├── test_metrics_recompute.py
│   ├── test_minimal_e2e.py
│   ├── test_mode_switch.py
│   ├── test_parity.py
│   ├── test_plugin_discovery.py
│   ├── test_regression.py
│   ├── test_repro_perf.py
│   ├── test_startup.py
│   ├── test_state_machine.py
│   └── test_stabilization.py
├── fixtures/                   # Test fixtures (minimal sample repos)
│   ├── __init__.py
│   ├── golden_torch_A/
│   │   ├── test_golden_torch_A.py
│   │   └── plan.yaml
│   ├── golden_pointcloud_B/
│   │   ├── test_golden_pointcloud_B.py
│   │   └── plan.yaml
│   └── minimal_pytorch_repo/
├── agents/                      # Agent markdown definitions
├── docs/                        # Documentation
├── commands/                    # Command reference docs
├── templates/                   # Project templates
├── schemas/                     # JSON schemas
├── skills/                      # Cursor skill definitions
├── tooling/                     # Tooling configs
├── automation_policy.yaml       # Default policy (runtime, but small)
├── README.md
├── LICENSE
├── CHANGELOG.md
└── .gitignore
```

### What Goes in `src/` vs `scripts/`

| `src/` | `scripts/` |
|--------|-----------|
| All Python packages with `__init__.py` | Standalone executable scripts (CLI entry points) |
| `orchestrator/` - library core | `reproctl.py` - CLI dispatcher |
| `ostar/` - library module | `autopilot.py` - standalone runner |
| `cvo/` - library module | `benchmark_runtime.py` - one-shot tool |
| `repro_agent/` - library module | `compare_runs.py` - analysis script |
| `startup/` - library module | `smoke_test.py` - diagnostic script |

The key principle: **packages with internal imports go in `src/`, standalone executable scripts go in `scripts/`**.

### What Goes in `tests/` vs `fixtures/`

| `tests/` | `fixtures/` |
|----------|-------------|
| All `test_*.py` test modules | Minimal sample repos for testing |
| `conftest.py` shared fixtures | `golden_torch_A/` - sample PyTorch project |
| Pytest configuration | `golden_pointcloud_B/` - sample point cloud project |
| | `minimal_pytorch_repo/` - minimal test repo |

### Documentation Location

- `README.md` - Root project overview
- `CHANGELOG.md` - Version history
- `docs/` - Detailed documentation
  - `docs/architecture.md` - System design
  - `docs/command_reference.md` - CLI reference
  - `docs/STARTUP.md` - Getting started
  - `docs/complete_manual.md` - Full manual
  - `docs/troubleshooting.md` - Debug guide
  - `docs/automation_workflow.md` - Workflow docs
  - `docs/reproduction_protocol.md` - Protocol docs
  - `docs/testing_and_ci.md` - CI guide
  - `docs/security.md` - Security notes
  - `docs/orchestrator/` - Orchestrator-specific docs
- `commands/` - Per-command documentation
- `agents/` - Agent system definitions

### Config Location

- `automation_policy.yaml` - Root config (keep at root)
- `schemas/` - JSON schemas for validation
- `templates/` - Template files for new projects

---

## 4. Import Path Analysis

### Current Import Pattern

The codebase uses **relative imports within `scripts/` packages** and **absolute `scripts.X` imports** across packages:

```python
# Within same package (scripts/orchestrator/controller.py)
from .approval_gate import ApprovalGate
from .event_journal import EventJournal
from .state_store import StateStore

# Cross-package (scripts/ostar/cli.py)
from scripts.ostar import constants as _C
from scripts.ostar import config as _cfg

# Cross-package (scripts/autopilot.py)
from scripts.orchestrator.controller import Controller
from scripts.orchestrator.policy_engine import PolicyEngine

# Tests (tests/test_orchestrator.py)
sys.path.insert(0, str(SCRIPTS_DIR))
from orchestrator import Controller, PolicyEngine
```

### Critical Import Paths

| Pattern | Example | Files Affected |
|---------|---------|---------------|
| `from scripts.X import Y` | `scripts/autopilot.py` | 3 files |
| `from scripts.ostar import X` | `scripts/ostar/cli.py`, `scripts/reproctl.py` | 3 files |
| `from scripts.orchestrator.agents.X import Y` | `agents/__init__.py` | 1 file |
| `from scripts.repro_agent.metrics import X` | `repro_agent/__init__.py` | 1 file |
| `from .X import Y` (relative) | All internal package files | 50+ files |

### What Would Break If Files Are Moved

**Moving to `src/` requires these changes:**

1. **`scripts/autopilot.py`** (line 43-49):
   ```python
   # CURRENT
   from scripts.orchestrator.controller import Controller
   from scripts.orchestrator.policy_engine import PolicyEngine
   # BECOMES
   from src.orchestrator.controller import Controller
   from src.orchestrator.policy_engine import PolicyEngine
   ```

2. **`scripts/ostar/cli.py`** (line 45-51):
   ```python
   # CURRENT
   from scripts.ostar import constants as _C
   from scripts.ostar import config as _cfg
   # BECOMES
   from src.ostar import constants as _C
   from src.ostar import config as _cfg
   ```

3. **`scripts/reproctl.py`** (line 226):
   ```python
   # CURRENT
   from scripts.ostar.cli import main as soak_main
   # BECOMES
   from src.ostar.cli import main as soak_main
   ```

4. **`scripts/orchestrator/agents/__init__.py`** (line 13):
   ```python
   # CURRENT
   from scripts.orchestrator.agents.base import AgentOrchestrator
   # BECOMES
   from src.orchestrator.agents.base import AgentOrchestrator
   ```

5. **All test files** that use `from scripts.ostar import` or `from scripts.orchestrator import`:
   - `tests/test_ostar.py` - 20+ imports
   - `tests/test_orchestrator.py` - 5 imports
   - Tests need `sys.path` adjustment to include `src/` instead of `scripts/`

6. **Internal relative imports are safe** - files within `src/orchestrator/`, `src/ostar/`, etc. use `from .X import Y` which works regardless of package name as long as the directory is a package.

---

## 5. Circular Import and Coupling Analysis

### No Circular Imports Found

The import graph is clean:

```
orchestrator/agents/__init__.py
  └── agents/base.py
  └── agents/repo_scout.py (lazy)
  └── agents/paper_auditor.py (lazy)

orchestrator/controller.py
  ├── orchestrator/approval_gate.py
  ├── orchestrator/event_journal.py
  ├── orchestrator/policy_engine.py
  ├── orchestrator/process_manager.py
  ├── orchestrator/recovery.py
  ├── orchestrator/scheduler.py
  ├── orchestrator/state_store.py
  ├── orchestrator/stop_hook.py
  ├── orchestrator/task_executor.py
  ├── orchestrator/verifier.py
  └── orchestrator/watchdog.py

ostar/soak_engine.py
  ├── ostar/constants.py
  ├── ostar/config.py
  ├── ostar/exit_validator.py
  ├── ostar/guard.py
  ├── ostar/hardware_monitor.py
  ├── ostar/repair_node.py
  ├── ostar/soak_state.py
  └── ostar/test_suites.py

cvo/runner.py
  ├── cvo/nodes.py
  └── cvo/state.py

autopilot.py
  ├── scripts.orchestrator.controller
  ├── scripts.orchestrator.policy_engine
  ├── scripts.orchestrator.process_manager
  └── scripts.orchestrator.state_store

startup/state_machine.py
  ├── startup/lock.py
  ├── startup/plan_validate.py
  ├── startup/doctor.py
  └── startup/config.py
```

### Coupling Analysis

| Module | Coupling | Notes |
|--------|----------|-------|
| `orchestrator/controller.py` | HIGH | Central hub, imports 10+ modules |
| `orchestrator/state_store.py` | HIGH | SQLite core, no external deps |
| `orchestrator/scheduler.py` | MEDIUM | Depends on state_store |
| `orchestrator/task_executor.py` | LOW | Thin wrapper around process_manager |
| `orchestrator/agents/` | MEDIUM | Each agent is self-contained |
| `ostar/soak_engine.py` | MEDIUM | Imports 8 modules but all within package |
| `cvo/` | LOW | Simple runner + state |
| `startup/` | LOW | Utilities, simple dependencies |

### Key Design Pattern

The codebase uses **lazy imports in `__init__.py`** files to avoid circular dependencies:

```python
# scripts/orchestrator/agents/__init__.py
from .base import (AgentOrchestrator, AgentRegistry, ...)

# Import all agents to register them (lazy, via # noqa comments)
from . import repo_scout  # noqa: F401, E402
from . import paper_auditor  # noqa: F401, E402
```

---

## 6. Minimal Restructuring Plan

### Option A: Minimal Change (Recommended)

**Keep everything in `scripts/` but reorganize within it.**

```
Current:                    Proposed:
scripts/                   scripts/
├── orchestrator/     →    src/  (rename dir)
│   └── agents/       →    src/agents/
├── ostar/            →    src/ostar/
├── cvo/              →    src/cvo/
├── repro_agent/      →    src/repro_agent/
├── startup/          →    src/startup/
├── reproctl.py       →    scripts/reproctl.py (entry point stays)
├── autopilot.py       →    scripts/autopilot.py
└── other *.py        →    scripts/*.py
tests/                 →    tests/
fixtures/              →    fixtures/
```

**Pros:**
- Minimal import changes
- Clear separation between library code (`src/`) and CLI tools (`scripts/`)
- Tests remain in place

**Cons:**
- `src/` is a non-standard name (usually `kestrel_repro/` or the package name)

### Option B: Standard Python Layout

```
kestrel_repro/               # Root package name
├── __init__.py
├── orchestrator/      →    orchestrator/
├── ostar/              →    ostar/
├── cvo/                →    cvo/
├── repro_agent/        →    repro_agent/
├── startup/            →    startup/
├── cli.py              →    scripts/reproctl.py
├── autopilot.py        →    scripts/autopilot.py
└── ...other scripts... →    scripts/*.py
tests/                  →    tests/
fixtures/               →    fixtures/
```

**Pros:**
- Standard Python package layout
- Installable via `pip install -e .`

**Cons:**
- Requires renaming `scripts/` to something else (e.g., `bin/` or `tools/`)
- More import path changes

### Recommended: Option A with `src/` Renamed

Use a hybrid that minimizes disruption while following conventions:

```
kestrel_repro/               # Root (rename from kestrel-repro)
├── src/
│   ├── __init__.py
│   ├── orchestrator/        # Core execution engine
│   ├── ostar/               # Soak testing
│   ├── cvo/                 # Validation orchestrator
│   ├── repro_agent/          # Metrics and agents
│   └── startup/             # Bootstrap system
├── scripts/                 # CLI entry points (stays as-is)
│   ├── reproctl.py
│   ├── autopilot.py
│   └── ...
├── tests/
├── fixtures/
├── agents/
├── docs/
├── commands/
├── templates/
├── schemas/
├── skills/
├── tooling/
└── pyproject.toml            # ADD: package config
```

### Import Migration Steps (Option A)

1. **Create `src/` directory**
2. **Move package directories** into `src/`:
   ```bash
   mkdir -p src
   mv scripts/orchestrator src/
   mv scripts/ostar src/
   mv scripts/cvo src/
   mv scripts/repro_agent src/
   mv scripts/startup src/
   ```
3. **Create `src/__init__.py`** with re-exports for backward compatibility
4. **Update 3 files** that use `from scripts.X import`:
   - `scripts/autopilot.py`
   - `scripts/ostar/cli.py`
   - `scripts/reproctl.py`
5. **Update test imports** in `tests/test_ostar.py` and `tests/test_orchestrator.py`
6. **Update `.gitignore`** to cover new paths
7. **Add `pyproject.toml`** for proper package installation

### Gitignore Updates Needed

```gitignore
# Add to existing .gitignore
src/
scripts/*.py          # Keep but note: reproctl.py, autopilot.py are entry points
!scripts/reproctl.py  # Explicitly include entry points
!scripts/autopilot.py
```

---

## 7. Summary

| Category | Status | Action |
|----------|--------|--------|
| Runtime dirs (`.repro/`, `.execution/`, `.repair/`, `.stabilization/`) | Already gitignored via `.gitignore` | None needed |
| Cache (`__pycache__`, `.cache`, `.pytest_cache`) | Already gitignored | None needed |
| Generated output (`artifacts/`, `reports/`, `audits/`) | Missing from `.gitignore` | Add |
| Test fixtures | Keep in `fixtures/` | Good |
| Source packages | Currently in `scripts/` | Move to `src/` for clarity |
| Tests | In `tests/` | Keep, update imports after move |
| CLI entry points | In `scripts/` root | Keep here (standard) |
| Internal package imports | All relative or `scripts.X` | Update 3 files after move |
| Circular imports | None found | Clean |
| Package coupling | Low, well-structured | No changes needed |

**Total import changes needed:** ~5 files across the entire codebase.
