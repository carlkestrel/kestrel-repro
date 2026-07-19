# Changelog

All notable changes to dl-paper-repro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] — 2026-07-19

First production-ready release. The R3 consolidation and the full R3R
repair cycle (R3R-0 through R3R-9) are merged onto `main`, the test
suite reports **301 passed / 0 failed / 0 skipped** (verified in
`ci_reports/R3_BASELINE_2026-07-19.xml` and the post-merge re-run on
the `main` branch), and the project no longer touches host-dependent
performance artefacts.

### Added — R3: State consolidation

- Single canonical `StateStore` lives at `scripts/core/state_store.py`
  (~960 LOC). `scripts.startup.state_store` and
  `scripts.orchestrator.state_store` are now thin re-export shims.
- `PlanSchema` carries `schema_version` and `canonicalization_version`,
  which are folded into `authorization_bound_hash`. A schema upgrade
  invalidates prior approvals.
- `find_active_state_dbs()` /
  `assert_single_state_authority()` enforce one DB per project.
- `NEEDS_RECONFIRMATION` flag is set on schema upgrade; contracts must
  be re-issued when the schema version changes.
- ApprovalGate uses canonical `APPROVED / REJECTED / WAIVED` semantics
  across startup, orchestrator, and recovery code paths.
- Controller calls the canonical API: `initialize_plan`,
  `transition`, `claim_task`, `decide_approval`.
- `stop_hook` is now thread-safe so worker threads stop cleanly on
  `SIGTERM`.
- `ProcessManager` annotates unknown exit codes with a best-effort
  explanation (e.g. `137 → OOM kill`, `143 → SIGTERM`).
- `docs/adr/ADR-001-single-state-authority.md` documents the
  architectural decision.

### Added — R3R: Repair of the 21 R3-OPEN failures

The R3R (R3 Repair) phase systematically closes the 21 long-standing
orchestrator and chaos failures that R3 inherited.

- **R3R-0 — Trustworthy baseline.** Re-collected `pytest tests/` to a
  fresh JUnit XML (`ci_reports/R3_BASELINE_2026-07-19.xml`) and
  reconciled the result with `refactor_state.json`. Found 18 previously
  failing tests already pass on `main` (R3-1/2/3/5/7 wired up
  implicitly); remaining backlog shrank from 21 to 3 chaos tests.
- **R3R-1 — CI hygiene.** Lint (`ruff check .`) reports zero issues.
  `scripts/startup/plan_schema.py`, `scripts/orchestrator/state_store`,
  and `scripts/runtime` are compatible with Python 3.10. YAML
  exclusions added to `pyproject.toml`; pip index now points at a
  pinned mirror for reproducible installs.
- **R3R-2 — PlanSchema → Controller bridge.** Canonical
  `PlanSchema` objects can be passed straight to the Controller dict
  interface without manual conversion (`scripts/core/plan_bridge.py`).
  Covered by `tests/test_canonical_plan_controller_e2e.py` (5 tests).
- **R3R-4 — P0-5 / P0-6 fixes.**
  - **P0-5:** Non-evidentiary tasks (e.g. tasks that only assert
    internal state, no measurable metric) are no longer auto-PASSed
    by the verifier. They return
    `(True, "_NEEDS_WAIVER_")` and transition to
    `WAITING_APPROVAL`. A human must explicitly `WAIVE` them.
    `EXPIRED` added to `TASK_STATES` and `HUMAN_TRANSITIONS`.
    `VERIFYING → WAITING_APPROVAL` added to `TASK_TRANSITIONS`.
    Covered by `tests/test_non_evidentiary_waiver.py` (9 tests).
  - **P0-6:** `cleanup_expired()` now calls
    `decide_approval(REJECTED)` for expired approvals. Rejection is
    terminal — tasks can expire, but they are not silently waived
    past their approval deadline.
- **R3R-5 — `metrics_recompute` verifier.** New branch in
  `_verify_impl` reads the per-class `confusion_matrix.json` emitted
  by training, validates it is square, non-negative, and that rows
  sum to the per-class counts, recomputes per-class IoU and mIoU
  independently, and compares with the `reported mIoU` in
  `predictions/miou_per_class.json` within a caller-supplied
  tolerance. Catches "incorrectly-optimized" tunings where the
  reported metric is hand-tweaked to look better than the artefacts
  actually support. 11 tests in
  `tests/test_metrics_recompute_verifier.py`.
- **R3R-6 — SQLite lock fixes.** Connect timeout and busy_timeout
  reduced from 30s to 5s. The chaos test `test_sqlite_locked_retries`
  now reliably fires the busy-retry path before the test deadline.
- **R3R-7 — `/repro-start` guided startup.** New command at
  `scripts/commands/repro-start.py` runs an auto-detect of the
  project mode and active plan, a doctor phase that validates Python
  / CUDA / disk, an authorisation contract check that refuses to
  start without an active contract, and a startup summary before
  handing off to `reproctl run`. No more guesswork for a fresh
  clone.
- **R3R-8 — Authorization enforcement E2E.** 6 new tests in
  `tests/test_authorization_enforcement_e2e.py` cover the four
  paths: no contract → no auth, active contract with matching hash
  → auth, stale `bound_hash` → auth refusal, denied action →
  blocked, rejected approval → blocked claim, task with no
  approval cannot complete.
- **R3R-9 (hotfix) — `test_09_rollback_capable` regression.** Discovered
  during the R3R → `main` merge smoke test. The test originally
  read `.execution/task_graph.yaml`, which is a `.gitignore`d
  runtime artefact — the regression check was environment-dependent
  rather than a true invariant. The new test imports `PlanSchema`
  from `scripts.startup.plan_schema`, instantiates it with a stub
  `plan_id`, and asserts the `rollback_strategy` field defaults to
  a non-empty value (`"safe-restart"`). This is the real invariant:
  every plan declared via the canonical schema must declare a
  rollback strategy. Result: 301/301 passed (was 300/301 at the
  merge moment).

### Changed — Multi-agent wiring

- 7 agents assigned model tiers (`17e3392`):
  - `repro-lead`, `orchestrator` → top-tier (Fable 5)
  - `evidence-verifier`, `data-metric-auditor` → top-tier
    (audit agents)
  - `repo-scout`, `runtime-optimizer`, `hardware-fit-auditor` →
    second-tier (Sol / Terra)
- Multi-agent mode is now available in this repo: the `Task` tool
  is enabled and the Cursor agent can spawn sub-agents (see
  `a34980c`).

### Removed — Host-dependent performance artefacts

- The 11 files under `performance/` (`baseline_metrics.csv`,
  `baseline_profile.json`, `capacity_trials.csv`,
  `hardware_inventory.json`, `health_report.md`,
  `numerical_parity_report.md`, `recommendation.md`,
  `rollback.yaml`, `safe_capacity.yaml`, `soak_test_report.md`,
  `strict_performance.yaml`) were tracked in error: they bind the
  repository to a specific host (timestamps, throughput, hardware
  profile) and have no meaning on a fresh clone. They are now
  `.gitignore`d. Run `python scripts/runtime/repro_perf_tuner.py
  --phase all` to regenerate them on your host.
- `performance/README.md` is added as a tracked pointer explaining
  what each file is and how to regenerate it.

### Verification

```text
$ pytest tests/ -q
============================= 301 passed in 41.70s =============================
```

CI reports and JUnit XML:

- `ci_reports/R3_PROGRESS_REPORT.md`
- `ci_reports/R3_BASELINE_2026-07-19.xml`
- `ci_reports/R3_BASELINE_2026-07-19_postfix.xml`
- `docs/adr/ADR-001-single-state-authority.md`

## [0.1.0] — 2026-07-15

### Added

#### Plugin Structure
- `.cursor-plugin/plugin.json` manifest with skills, rules, agents, and commands
- Complete directory structure following Cursor plugin conventions

#### Agents (9 total)
- `repro-lead.md` — Orchestration agent driving the full reproduction lifecycle
- `data-metric-auditor.md` — Read-only data and metric protocol auditing
- `runtime-optimizer.md` — Read-only runtime optimization auditing
- `evidence-verifier.md` — Read-only evidence chain verification
- `repo-scout.md` — Read-only GitHub repository discovery and ranking
- `hardware-fit-auditor.md` — Read-only hardware compatibility assessment
- `data-metric-auditor.md` — Read-only data/metric auditing (duplicate, to be merged)

#### Skills (4 total)
- `paper-reproduction/SKILL.md` — General paper reproduction methodology
- `deep-learning-runtime/SKILL.md` — DataLoader, AMP, DDP, hardware profiling
- `point-cloud-reproduction/SKILL.md` — PLY, KPConv, full-PC voting specifics
- `repository-selection/SKILL.md` — GitHub repository evaluation and ranking

#### Rules
- `reproduction-gates.mdc` — Always-on rule enforcing 6 staged gates

#### Commands (11 total)
- `/repro-init` — Initialize reproduction project
- `/repro-discover` — Discover and rank candidate GitHub repositories
- `/repro-acquire` — Safe cloning with static security audit
- `/repro-fit-hardware` — Hardware compatibility assessment
- `/repro-audit` — Paper, source, data, and metric auditing
- `/repro-preflight` — Environment, dataset, and disk checks
- `/repro-short-loop` — L0–L3 short-loop validation (smoke, overfit, mini-loop, checkpoint)
- `/repro-benchmark` — Throughput profiling and parity testing
- `/repro-launch` — Full training launch with gate enforcement
- `/repro-verify` — Evidence chain and metric reproducibility verification
- `/repro-decision` — GO/PIVOT/NO-GO decision report

#### Scripts (6 total)
- `reproctl.py` — Main CLI orchestrator with gate enforcement (2500+ lines)
- `environment_check.py` — Python, CUDA, PyTorch, packages, disk space checking
- `hardware_profile.py` — GPU, CPU, RAM, disk profiling with recommendations
- `benchmark_runtime.py` — Throughput and memory profiling across modes
- `compare_runs.py` — Strict vs. optimized mode comparison and parity reporting
- `artifact_verify.py` — Evidence chain completeness verification

#### Templates (9 total)
- `repro_spec.yaml` — Paper and repository metadata template
- `repo_adapter.yaml` — Repository-specific commands and entrypoints template
- `sources.lock.yaml` — Pinned repository URLs and commits template
- `runs_manifest.csv` — Experiment runs tracking template
- `data_contract.md` — Dataset schema and metric definition template
- `candidate_repositories.csv` — Repository evaluation table template
- `hardware_fit_report.md` — Hardware compatibility report template
- `repository_security_audit.md` — Security audit template
- `metric_protocol_audit.md` — Metric protocol comparison template

#### Documentation
- `README.md` — Installation, usage, architecture, and workflow documentation
- `CHANGELOG.md` — This file
- `LICENSE` — MIT license

### Design Decisions

- **Evidence-first**: Every result must be traceable to commit, config, data, seed, command, checkpoint, and raw metrics
- **Gate enforcement**: `reproctl.py` programmatically blocks training if gates are not passed
- **Repository-agnostic**: Works with any PyTorch-based paper, not just specific models
- **Security-first**: Static analysis before any cloning; no `curl | bash` execution
- **Three-mode execution**: strict_repro, optimized_repro_safe, experimental_fast with parity requirements
- **Rank by paper match, not stars**: Repository ranking prioritizes paper match over GitHub popularity
- **Preserve failed runs**: No deletion of failed experiments; evidence includes failures

### Known Limitations

- Smoke test scripts (L0–L3) are scaffolded but require per-repository adapter configuration
- Benchmark train script requires repository-specific integration
- No automatic Docker/container support (manual configuration required)
- GitHub MCP integration is optional and not yet wired up
