# dl-paper-repro

Evidence-driven deep learning paper reproduction plugin for Cursor.

Reproduces PyTorch-based deep learning papers from GitHub repositories with staged gates, hardware-aware optimization, and complete evidence chains.

## What This Plugin Does

This plugin provides a structured workflow for reproducing deep learning papers from their official GitHub repositories. It enforces evidence-first principles — every claim is backed by traceable artifacts (commit, config, data manifest, seed, command, checkpoint, raw metrics).

It is designed to work with **any PyTorch-based paper repository**, not just specific models like KPConv.

## Features

- **9 specialized agents** — Orchestration, source auditing, data/metric auditing, runtime optimization, evidence verification, repository scouting, and hardware-fit auditing
- **4 skills** — Paper reproduction, deep learning runtime optimization, point cloud reproduction, repository selection
- **Stage gate enforcement** — 6 gates (paper audit → preflight → short loop → parity → full training → evidence) that must all pass before claiming results
- **Programmatic gate enforcement** — `reproctl.py` refuses to launch training if gates are not passed
- **GitHub repository discovery** — Finds and ranks candidate repositories by paper match, not stars
- **Hardware-fit assessment** — Matches repository requirements to local GPU/CPU/RAM/disk
- **Safe cloning** — Static security audit before executing any installation scripts
- **Multi-mode execution** — strict_repro, optimized_repro_safe, experimental_fast with parity requirements
- **Evidence chain verification** — Verifies every result is traceable from commit to reported metric
- **Machine-readable + human-readable reports** — JSON/CSV alongside Markdown for every phase

## Quick Start

### 1. Install

Clone to your Cursor plugins directory:

```bash
mkdir -p ~/.cursor/plugins/local
git clone https://github.com/YOUR_NAME/dl-paper-repro.git \
  ~/.cursor/plugins/local/dl-paper-repro
```

Then reload Cursor (`Cmd/Ctrl+Shift+P` → "Reload Window").

### 2. Initialize a reproduction

In Cursor Agent, tell it to use the plugin commands:

```
/repro-init paper=https://arxiv.org/abs/2103.14641 target="Table 2, mIoU on S3DIS"
```

This creates the `.repro/` directory with `repro_spec.yaml`, `repo_adapter.yaml`, and `state.json`.

### 3. Discover and acquire repositories

```
/repro-discover paper=https://arxiv.org/abs/2103.14641
/repro-acquire
/repro-fit-hardware
```

This finds the paper-author's official repository, clones it safely, and assesses hardware compatibility.

### 4. Run staged gates

```
/repro-audit         # Gate 0: Paper & source audit
/repro-preflight     # Gate 1: Environment & data checks
/repro-short-loop    # Gate 2: L0–L3 short-loop validation
/repro-benchmark     # Gate 3: Throughput & parity testing
```

### 5. Launch training and verify

```
/repro-launch mode=strict_repro seed=42 epochs=300
/repro-verify
/repro-decision
```

The `reproctl.py` tool enforces that full training cannot start until Gates 0, 1, and 2 all pass.

## Architecture

```
dl-paper-repro/
├── .cursor-plugin/
│   └── plugin.json          # Plugin manifest
├── agents/                   # 9 specialized agents
│   ├── repro-lead.md         # Orchestration
│   ├── data-metric-auditor.md
│   ├── runtime-optimizer.md
│   ├── evidence-verifier.md
│   ├── repo-scout.md         # GitHub discovery
│   └── hardware-fit-auditor.md
├── skills/                   # 4 skill guides
│   ├── paper-reproduction/
│   ├── deep-learning-runtime/
│   ├── point-cloud-reproduction/
│   └── repository-selection/
├── rules/
│   └── reproduction-gates.mdc  # Always-on gate rule
├── commands/                 # 11 commands
│   ├── repro-init.md
│   ├── repro-discover.md
│   ├── repro-acquire.md
│   ├── repro-fit-hardware.md
│   ├── repro-audit.md
│   ├── repro-preflight.md
│   ├── repro-short-loop.md
│   ├── repro-benchmark.md
│   ├── repro-launch.md
│   ├── repro-verify.md
│   └── repro-decision.md
├── scripts/                 # Python tooling
│   ├── reproctl.py          # Main CLI orchestrator
│   ├── environment_check.py
│   ├── hardware_profile.py
│   ├── benchmark_runtime.py
│   ├── compare_runs.py
│   └── artifact_verify.py
└── templates/               # YAML/CSV/Markdown templates
    ├── repro_spec.yaml
    ├── repo_adapter.yaml
    ├── sources.lock.yaml
    ├── data_contract.md
    ├── candidate_repositories.csv
    ├── hardware_fit_report.md
    ├── repository_security_audit.md
    └── metric_protocol_audit.md
```

## The 6 Gates

| Gate | Name | Required Before |
|---|---|---|
| Gate 0 | Paper & Source Audit | Environment setup |
| Gate 1 | Preflight | Any code execution |
| Gate 2 | Short Loop (L0–L3) | Full training |
| Gate 3 | Parity Testing | optimized_repro_safe mode |
| Gate 4 | Full Training | Evaluation |
| Gate 5 | Evidence Verification | Final report |

## reproctl.py

The main CLI tool for gate enforcement:

```bash
python reproctl.py status          # Show gate status
python reproctl.py can-launch     # Check if training can start
python reproctl.py launch --mode=strict_repro --seed=42 --epochs=300
python reproctl.py run-short-loop --level=L0
python reproctl.py verify --run-id=<uuid>
python reproctl.py report
```

## Execution Modes

| Mode | Description | For Paper Results |
|---|---|---|
| `strict_repro` | FP32, single GPU, paper batch size | ✅ Yes |
| `optimized_repro_safe` | AMP, DDP, batch changes (after parity) | ✅ Yes, with evidence |
| `experimental_fast` | torch.compile, aggressive changes | ❌ Never |

## Point Cloud Papers

This plugin includes specialized support for point cloud papers:

- S3DIS, ScanNet, SemanticKITTI dataset handling
- PLY file reading and label mapping
- KPConv, PointNet++, DGCNN architecture awareness
- Full-point-cloud (FPV) voting memory estimation
- Custom CUDA extension compatibility

## Example Workflow

```text
/repro-init paper=https://arxiv.org/abs/2103.14641 target="Table 2, mIoU"
→ Creates .repro/repro_spec.yaml and .repro/state.json

/repro-discover paper=https://arxiv.org/abs/2103.14641
→ Produces candidate_repositories.csv and discovery_summary.md

/repro-acquire
→ Clones primary and reference repositories
→ Creates sources.lock.yaml
→ Performs static security audit

/repro-fit-hardware
→ Generates hardware_profile.md
→ Recommends strict_repro mode

/repro-audit
→ Produces source_audit.md, data_audit.md, metric_audit.md

/repro-preflight
→ Runs environment_check.py, hardware_profile.py
→ Verifies dataset availability

/repro-short-loop
→ L0: Smoke test (forward + backward)
→ L1: Overfit random labels
→ L2: Mini-dataset end-to-end loop
→ L3: Checkpoint resume comparison

/repro-benchmark
→ Profiles strict vs. optimized throughput
→ Runs parity tests for AMP

/repro-launch --mode=strict_repro --seed=42 --epochs=300
→ [BLOCKED if any gate failed]
→ Records exact command, config, seed, commit
→ Saves checkpoints and raw metrics

/repro-verify
→ Verifies metrics from checkpoints
→ Checks evidence chain completeness

/repro-decision
→ Produces GO / PIVOT / NO-GO report
```

## Supported Papers

This plugin works with any PyTorch-based deep learning paper, including:

- Image classification (ResNet, ViT, EfficientNet)
- Object detection (YOLO, Faster R-CNN, DETR)
- Semantic segmentation (DeepLabV3, UNet, SegFormer)
- Point cloud processing (PointNet++, KPConv, PointNeXt)
- Object detection in point clouds (PointPillars, CenterPoint)
- 3D detection (PV-RCNN, VoxelNet)

## Limitations

This plugin cannot automatically solve:

- Papers without publicly available data
- Papers requiring data agreements or applications
- Papers with incomplete evaluation protocols
- Papers with GPU-architecture-dependent numerical differences
- Papers with bugs in the original implementation

Its value is making failures **locatable and documented**, not guaranteeing success.

## Requirements

- Cursor IDE (latest version)
- Python 3.8+
- PyTorch 1.10+
- NVIDIA GPU with CUDA 11.0+ (for GPU training)
- Git

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.

## License

MIT
