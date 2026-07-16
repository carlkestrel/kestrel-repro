# CI Workflow Architecture

This directory contains the layered CI system for the `dl-paper-repro` plugin.

## Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     CI Layer Architecture                      │
│                                                               │
│  PR opened/updated ──► ci-fast (< 5 min, every PR)          │
│         │                      │                             │
│         │                        ▼                            │
│         │            lint + type check + unit tests           │
│         │            (3 Python versions, no GPU)              │
│         │                                                      │
│  push to main ────► ci-integration (10–15 min)              │
│  PR merged             │                                     │
│  manual dispatch        ▼                                     │
│                 T1→T6 full chain (real subprocesses)          │
│                 kill -9 + resume validation                   │
│                 no GPU, no paper data downloads              │
│                                                               │
│  schedule (Tue/Sat) ─► ci-gpu (~30 min)                      │
│  push to main          │                                     │
│  manual dispatch        ▼                                     │
│                 self-hosted GPU runner ONLY                   │
│                 PyTorch CUDA smoke + DDP                     │
│                 NO external PR code on GPU runner             │
│                                                               │
│  tag v* ─────────────► ci-release (release gate)            │
│                            │                                  │
│                            ▼                                  │
│               100% mandatory pass + 100% coverage            │
│               no unexplained flaky tests                     │
│               generate mandatory_checks.md                    │
└──────────────────────────────────────────────────────────────┘
```

## Workflows

### ci-fast.yml
- **Trigger**: Every PR (opened/synchronize/reopened), push to `dev/*`
- **Duration**: < 5 minutes
- **Hardware**: GitHub-hosted `ubuntu-latest`
- **Python**: 3.11, 3.12, 3.13 (matrix)
- **Tests**: Plugin discovery, config schema, CLI parsing, state machine, orchestrator unit tests
- **Outputs**: `coverage.xml`, JUnit XML test reports
- **Security**: No GPU, no real data, fixture mocks, `contents: read` only

### ci-integration.yml
- **Trigger**: Push to `main`/`master`, PR closed (merged), manual `workflow_dispatch`
- **Duration**: 10–15 minutes
- **Hardware**: GitHub-hosted `ubuntu-latest`
- **Python**: 3.13
- **Tests**: Full T1→T6 task chain, interrupt/resume with `kill -9`, idle exit validation
- **Outputs**: Integration logs, event log analysis
- **Security**: No GPU, no paper data downloads, real subprocess orchestration

### ci-gpu.yml
- **Trigger**: Schedule (every Tuesday and Saturday at 00:00 UTC), push to `main`, manual `workflow_dispatch`
- **Duration**: ~30 minutes
- **Hardware**: **Self-hosted runner with `gpu` label only**
- **Python**: 3.13
- **Tests**: CUDA tensor, DataLoader, forward pass, backward+optimizer, AMP, torch.compile fallback, checkpoint save/restore, OOM recovery, DDP (2+ GPUs)
- **Outputs**: `nvidia-smi` log, PyTorch/CUDA version info
- **Security**:
  - `if: github.event.pull_request.head.repo.full_name == github.repository` blocks external PRs
  - `contents: read` only
  - No external code execution on GPU runner
  - Concurrent runs deduped via `concurrency` group

### ci-release.yml
- **Trigger**: Push tag `v*` (release creation)
- **Prerequisite**: ci-fast + ci-integration must have passed
- **Gates**:
  - 100% mandatory test pass rate
  - 100% critical/high fault detection
  - 100% state transition code coverage
  - Zero unexplained flaky tests
- **Outputs**: `mandatory_checks.md`, version file, release notes

## CI Reports

All reports live in `ci_reports/`:

| File | Purpose |
|---|---|
| `pass_rate.json` | Per-workflow pass rate, updated post-run |
| `flaky_tests.csv` | Flaky test tracking (30-day window) |
| `fault_detection.csv` | Fault detection rates per workflow |
| `coverage.xml` | pytest-cov XML output |
| `mandatory_checks.md` | Release gate status |
| `ci_summary.md` | Human-readable dashboard |

## Safety Constraints

All workflows comply with the 13 mandatory safety constraints:

1. `ci-fast` uses fixture mocks — no GPU, no paper downloads
2. All third-party actions pinned to full commit SHA
3. `GITHUB_TOKEN` permissions: `contents: read` only
4. No secrets in CI logs (no tokens, no paths with secrets)
5. No `continue-on-error` on mandatory jobs
6. GPU jobs only on trusted branches or manual dispatch
7. External PR code blocked from GPU runner (`if:` safety gate)
8. `concurrency` groups prevent duplicate GPU runs
9. Post-GPU subprocess cleanup step included
10. No deletion of user data or co-located processes
11. Test failure → upload logs and JUnit XML
12. Cache only for dependencies; never cache experiment results
13. No secrets printed to logs

## Self-Hosted GPU Runner Setup

The `ci-gpu.yml` workflow requires a self-hosted runner with the `gpu` label.

**To register the runner in the GitHub repository:**

1. Go to **Settings → Actions → Runners**
2. Click **New self-hosted runner**
3. Select **Linux** + architecture matching your GPU machine
4. Download and extract the runner
5. Configure with `--labels gpu`
6. Run `./run.sh`

Example:
```bash
./config.sh --url <repo-url> --token <runner-token> --labels gpu
./run.sh
```

The runner must have:
- NVIDIA GPU with driver installed
- `nvidia-smi` accessible
- Python 3.13
- Network access to GitHub

## Dependabot

`.github/dependabot.yml` auto-updates pip dependencies weekly (Mondays at 09:00 UTC).

Torch/torchvision major version bumps are ignored (require manual review).
