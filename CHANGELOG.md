# Changelog

All notable changes to dl-paper-repro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
