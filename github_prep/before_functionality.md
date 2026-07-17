# Functionality Inventory - Before Cleanup
Generated: 2026-07-17

## Source Code Entrypoints

### Python Entry Points
| File | Purpose | CLI Command |
|------|---------|------------|
| scripts/autopilot.py | Main autopilot loop | `python scripts/autopilot.py` |
| scripts/reproctl.py | Repro control | `python scripts/reproctl.py <cmd>` |
| scripts/startup/cli.py | Startup CLI | `python scripts/startup/cli.py` |
| scripts/ostar/cli.py | OSTAR CLI | `python scripts/ostar/cli.py` |
| scripts/cvo/audit_cli.py | CVO audit | `python scripts/cvo/audit_cli.py` |
| scripts/l0_l3_loop.py | L0-L3 verification | `python scripts/l0_l3_loop.py` |

### Cursor Commands
Located in `commands/` directory:
- repro-init, repro-start, repro-status, repro-plan
- repro-preflight, repro-short-loop, repro-verify
- repro-discover, repro-acquire, repro-audit
- repro-autopilot, repro-launch, repro-doctor
- repro-fit-hardware, repro-evidence-chain
- repro-contract, repro-report, repro-monitor
- repro-decision, repro-stop, repro-card
- repro-failure, repro-resume, repro-handoff
- repro-review, repro-contract, repro-benchmark
- geoai-discover, geoai-audit
- repro-soak-*, repro-open-morning-report

## Training Modes
| Mode | Description | Protocol |
|------|-------------|----------|
| strict | Full reproducibility | strict_performance.yaml |
| optimized | Performance optimized | optimized_performance.yaml |
| experimental | Fast experimental | experimental settings |

## Configuration Files
- automation_policy.yaml - NORA automation policy
- templates/repro_spec.yaml - Reproduction spec template
- templates/repo_adapter.yaml - Repository adapter template
- templates/search_plan.yaml - Search plan template
- performance/*.yaml - Performance configurations

## Test Fixtures
| Fixture | Purpose |
|---------|---------|
| fixtures/golden_torch_A/ | Basic PyTorch test |
| fixtures/golden_pointcloud_B/ | Point cloud test |
| fixtures/minimal_pytorch_repo/ | Minimal reproduction |

## Metric Formulas (DO NOT MODIFY)
See METRIC_COMPONENT_ARCHITECTURE.md for definitions:
- accuracy, precision, recall, f1
- iou, miou
- confmat (confusion matrix)
- numerical parity

## Checkpoint Paths
- Default: `artifacts/checkpoints/`
- Configurable via `checkpoint_root` in config

## Project Structure Summary
```
scripts/
├── orchestrator/          # Core orchestration
│   ├── controller.py      # Main controller
│   ├── policy_engine.py   # AUTO_PROCEED + gates
│   ├── approval_gate.py   # Human checkpoints
│   ├── watchdog.py        # GPU monitoring + MPS
│   ├── stop_hook.py       # NORA stop hook
│   ├── review_loop.py     # NORA review loop
│   └── agents/           # Specialist agents
├── autopilot.py           # Auto pilot
├── reproctl.py           # CLI
├── research_crawler.py    # Paper search
├── startup/              # Startup modules
├── ostar/               # OSTAR modules
├── cvo/                 # CVO modules
├── training_monitor.py
├── repro_perf_tuner.py
└── ...
```

## Known Dependencies
See requirements or pyproject.toml if exists.

## Status
All core functionality is operational. NORA enhancements have been integrated.
