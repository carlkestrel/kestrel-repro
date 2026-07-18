# Repository Selection Skill

Use this skill when evaluating candidate GitHub repositories for deep learning paper reproduction before cloning or installing anything.

## When to Use This Skill

Apply this skill whenever:
- A new paper is being prepared for reproduction and repositories need to be identified
- Multiple implementations of the same paper exist and need to be ranked
- The official paper-author repository needs to be distinguished from third-party implementations
- A candidate repository needs security and compatibility evaluation
- Deciding which repositories to clone, reference, or discard

## Evaluation Framework

### Three Repository Roles

Every repository found must be classified into one of three roles:

#### Primary (exactly one)
The paper-author official implementation. All paper results must come from this repository.

**Criteria for Primary:**
- Repository author matches paper author(s)
- README explicitly links to the paper
- Code matches the paper's exact model, dataset, and training protocol
- Contains training scripts that reproduce the paper's reported results
- Has a release or commit aligned with the paper's submission date

**If no Primary is found**, this is a CRITICAL finding that must be reported.

#### Reference (0–3)
Credible independent implementations that can help verify or debug the reproduction.

**Criteria for Reference:**
- Has complete training and evaluation code
- Has documentation or issues discussing the paper
- May have pretrained checkpoints or logs
- Is actively maintained or has recent commits
- Has a compatible license

**References cannot produce the final paper results.** They can only assist with understanding, debugging, or comparing.

#### Tooling (0–N)
Auxiliary projects for configuration, experiment tracking, data versioning, or profiling.

**Examples:**
- Hydra for configuration management
- MLflow for experiment tracking
- DVC for data versioning
- nvitop for GPU monitoring
- TorchBench for performance benchmarking
- AI Scientist or SWE-agent for orchestration patterns

**Tooling must remain optional.** The paper results must not depend on any tooling project.

## Ranking Criteria

Do NOT rank repositories primarily by GitHub stars. Stars are a maintenance signal, not a quality signal.

**Priority order:**

1. **Paper match** (weight: 50%)
   - Exact model architecture match
   - Exact dataset used in the paper
   - Exact training protocol (hyperparameters, augmentation, scheduler)
   - Exact evaluation protocol (checkpoint selection, voting, TTA)

2. **Official status** (weight: 25%)
   - Primary = paper author
   - Reference = independent but credible
   - Tooling = unrelated

3. **Protocol completeness** (weight: 15%)
   - Complete training script available
   - Evaluation script matches paper protocol
   - Data split is defined and reproducible
   - Metric computation matches paper definition

4. **Artifact availability** (weight: 10%)
   - Pretrained checkpoints available
   - Raw training logs available
   - Data download scripts (from legitimate sources)

5. **Hardware compatibility** (weight: 5%)
   - GPU memory requirements match available hardware
   - CUDA/PyTorch version compatibility
   - No custom CUDA extensions that are hard to build

6. **License compatibility** (weight: included in 1–5)
   - Commercial use allowed (MIT, Apache-2.0, BSD)
   - Academic use allowed (all permissive licenses)
   - Restrictions on modifications or derivatives

7. **Maintenance status** (weight: minor)
   - Recent commits (within 2 years)
   - Active issues and responses
   - Stars as a secondary signal only

## Discovery Process

### Step 1 — Paper-Based Search

Start from the paper itself:
- Read the paper for GitHub links in the abstract, introduction, or appendix
- Check arXiv page for GitHub links
- Search Semantic Scholar for the paper and check "Resources" or "Code" links

### Step 2 — Author Search

Search GitHub for the first author's username:
- `site:github.com <author-name>`
- Check if the author's organization has related repositories

### Step 3 — Keyword Search

Search GitHub with paper-relevant keywords:
- Model name (e.g., "KPConv", "PointNet++", "Swin Transformer")
- Dataset name (e.g., "S3DIS", "ScanNet", "SemanticKITTI")
- Task (e.g., "point cloud segmentation", "3D detection")

### Step 4 — Community Search

Check if the paper or method has been discussed in:
- Papers With Code (paperswithcode.com)
- Hugging Face model hub
- Reddit (r/MachineLearning, r/computervision)
- Discord communities

### Step 5 — Tooling Search

Identify relevant tooling projects:
- Configuration management: Hydra, OmegaConf
- Experiment tracking: MLflow, Weights & Biases, TensorBoard
- Data versioning: DVC, git-lfs
- GPU monitoring: nvitop, gpustat, nvtop
- Benchmarking: TorchBench, MLPerf

## Security Pre-Screening

Before any cloning or installation, screen each candidate for:

### Red Flags

| Red Flag | Risk Level | Action |
|---|---|---|
| `curl \| bash` installation | CRITICAL | Reject — do not execute |
| Unknown binaries or compiled executables | CRITICAL | Reject unless verified |
| Privileged Docker containers | CRITICAL | Reject unless verified |
| Root/sudo required for installation | HIGH | Flag and require user approval |
| Missing or non-standard license | HIGH | Flag and require user approval |
| Obfuscated or minified code | HIGH | Flag and require manual review |
| External data downloads from unknown sources | MEDIUM | Flag and require user approval |
| Post-install scripts that modify system | MEDIUM | Flag and require user approval |

### Static Analysis Before Execution

After cloning (but before running any installation), perform static analysis:

1. Read `setup.py`, `setup.cfg`, `pyproject.toml` — check for system modifications
2. Read all shell scripts — flag any privileged operations
3. Read `requirements.txt` — check for unusual packages
4. Read `Dockerfile` — check for base image and privileged flags
5. Check for compiled binaries (`.so`, `.cu`, `.pyx`) — verify they are from trusted sources

## Output Format

### candidate_repositories.csv

```csv
repository,role,stars_snapshot,official,paper_match,target_metric_match,last_commit,release_tag,license,framework,cuda_extensions,dataset_available,checkpoint_available,eval_protocol,estimated_vram_gb,multi_gpu,security_risk,decision,reason
https://github.com/author/official,primary,1200,yes,exact,yes,2024-03-15,v1.0,MIT,pytorch,no,yes,yes,complete,8,yes,low,clone,Paper author official implementation
https://github.com/other/impl-a,reference,450,no,high,yes,2024-01-20,no,Apache-2.0,pytorch,no,yes,no,partial,8,yes,low,reference,Complete training code, helpful for debugging
https://github.com/other/impl-b,reference,200,no,medium,partial,2023-11-05,no,MIT,pytorch,yes,yes,no,incomplete,10,no,medium,reference,CUDA extension may be hard to build
https://github.com/tooling/hydra,tooling,30000,no,na,na,2024-06-01,v1.1,MIT,pytorch,no,na,na,na,na,na,low,tooling,Optional config management
```

### discovery_summary.md

```markdown
# Repository Discovery Summary

## Paper
- Title: <paper title>
- arXiv: <link>
- Target metrics: <Table X, Column Y>

## Primary Repository
- URL: <official repo>
- Reason: <why this is primary>
- Commit: <recommended commit>

## Reference Repositories
- <reference 1>: <reason for inclusion>
- <reference 2>: <reason for inclusion>

## Tooling Recommendations
- <tool>: <why useful>

## Recommended Workflow
1. Clone primary repository
2. Audit source, config, and data
3. Run preflight checks
4. Complete short-loop validation
5. Optimize runtime if needed
6. Run full training

## Security Notes
- <any flagged repositories and their risks>
```

## Integration with Other Skills

- `paper-reproduction` skill uses this skill to identify the primary repository
- `repro-lead` agent orchestrates the discovery → acquire → audit workflow
- `hardware-fit-auditor` agent uses this skill's output to assess hardware fit
- `source-auditor` (deprecated; merged into `data-metric-auditor`)

---

## Dataset Tier System (P9_T03) — A to E

Every dataset considered for a reproduction is classified into one of
**5 tiers**. The tier determines how the dataset interacts with the
candidate-repository decision and with the claim-evidence matrix.

| Tier | Name | Definition | Use case |
|---|---|---|---|
| **A — Core Benchmark** | The dataset on which the paper reports its **headline result** (e.g., S3DIS for KPConv, ScanNet for PointNet++). The reproduction **must** match on this dataset to claim a successful reproduction. | mandatory baseline target |
| **B — Pretraining** | Datasets the upstream model was pretrained on (e.g., ShapeNet for many 3D models, ImageNet for 2D backbones). The reproduction **must** document the pretrained source and pin it. | controls the starting point |
| **C — Cross-domain** | Datasets that test domain transfer (e.g., S3DIS-trained model → SemanticKITTI inference). The paper may report transfer results; the reproduction records them as **secondary** claims. | secondary claims, optional |
| **D — Auxiliary** | Datasets used for ablations, sanity checks, or unit tests (e.g., a small toy dataset for overfit test L1). Not part of the headline result. | supporting evidence only |
| **E — Reference Only** | Datasets mentioned in the paper but not used for any reported number (cited as related work, future work, or context). Recorded for completeness; no reproduction needed. | context only |

### Selection rule

A reproduction project MUST have **at least 1 Tier-A dataset**. Tier-B
datasets are required when the upstream model is pretrained; Tier-C
datasets are optional but, if used, become **secondary claims** in the
claim-evidence matrix. Tier-D datasets are encouraged for L1 overfit
tests; Tier-E datasets are tracked but never evaluated.

### Conflict resolution

If two repositories disagree on the Tier-A dataset (e.g., one claims
S3DIS, the other claims ScanNet for the same paper), pick the dataset
that the **paper itself** uses in its headline table; document the
disagreement in `candidate_repositories.csv:reason` and resolve via
human decision if both are reported.

### Dataset registry

Each Tier-A dataset **must** have an entry in `templates/dataset_registry.md`
with all 12 field groups filled. Tier-B/C datasets are recommended to
have a registry entry. Tier-D/E entries are optional.
