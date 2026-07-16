# /repro-discover

Discover and evaluate candidate GitHub repositories for deep learning paper reproduction.

## Usage

```
/repro-discover paper=<paper-url-or-arxiv-id> [keywords=<additional-keywords>]
```

## What This Command Does

### Step 1 — Paper-Based Search

Start from the paper itself:
- Read the paper for GitHub links in abstract, introduction, appendix
- Check arXiv page for GitHub links
- Search Semantic Scholar for the paper and check "Resources" or "Code" links

### Step 2 — Author Search

Search GitHub for the first author's username:
- Query: `site:github.com <author-name>`
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

### Step 5 — Evaluation and Ranking

For each candidate, evaluate:
- **Official status**: Is this the paper author's official implementation?
- **Paper match**: Does it match the exact model, dataset, and training protocol?
- **Target metric match**: Does it include the metrics from the paper's target table?
- **Last commit**: When was the last commit? Is it actively maintained?
- **Release tag**: Is there a stable release tagged for the paper version?
- **License**: Is the license compatible?
- **Framework**: PyTorch, JAX, TensorFlow, or other?
- **CUDA extensions**: Does it use custom CUDA kernels?
- **Dataset available**: Is the dataset publicly available?
- **Checkpoint available**: Are there pretrained checkpoints or logs?
- **Eval protocol**: Is the evaluation protocol clearly documented?
- **Estimated VRAM**: What is the expected GPU memory requirement?
- **Multi-GPU**: Does it support distributed training?
- **Security risk**: Are there any installation scripts that pose risks?

### Step 6 — Ranking

Rank by this priority (NOT by stars):
1. Paper match (exact architecture, dataset, training protocol)
2. Official status (paper author = repository author)
3. Protocol completeness (training, evaluation, data split)
4. Artifact availability (checkpoints, logs, pretrained weights)
5. Hardware compatibility (CUDA, memory, multi-GPU)
6. License compatibility
7. Maintenance status
8. Stars (only as a timestamped maintenance signal)

### Step 7 — Security Pre-Screening

Flag repositories with:
- `curl | bash` installation scripts
- Unknown binaries or compiled executables
- Privileged Docker containers
- Root/sudo required for installation
- Obfuscated or minified code
- External data downloads from unknown sources

## Output Artifacts

```
repro_audit/
├── repository_discovery/
│   ├── candidate_repositories.csv
│   ├── candidate_repositories.json
│   ├── discovery_summary.md
│   └── repository_reports/
│       ├── <repo-name-1>.md
│       ├── <repo-name-2>.md
│       └── ...
```

### candidate_repositories.csv

```csv
repository,role,stars_snapshot,official,paper_match,target_metric_match,last_commit,release_tag,license,framework,cuda_extensions,dataset_available,checkpoint_available,eval_protocol,estimated_vram_gb,multi_gpu,security_risk,decision,reason
https://github.com/author/official,primary,1200,yes,exact,yes,2024-03-15,v1.0,MIT,pytorch,no,yes,yes,complete,8,yes,low,clone,Paper author official implementation
https://github.com/other/impl-a,reference,450,no,high,yes,2024-01-20,no,Apache-2.0,pytorch,no,yes,no,partial,8,yes,low,reference,Complete training code, helpful for debugging
```

## What This Command Does NOT Do

- Does NOT clone any repositories (use `/repro-acquire` for that)
- Does NOT execute any installation scripts
- Does NOT run any code
- Does NOT modify any files
- Does NOT rank primarily by GitHub stars

## Three Repository Roles

### Primary (exactly one)
The paper-author official implementation. All paper results must come from here.

### Reference (0–3)
Credible independent implementations. Can help verify or debug the reproduction, but cannot produce the final paper results.

### Tooling (0–N)
Auxiliary projects (Hydra, MLflow, DVC, nvitop, TorchBench). Must remain optional. Paper results must not depend on tooling.

## Next Steps

After `/repro-discover` completes:

1. Review `candidate_repositories.csv` and the discovery summary
2. Confirm the primary repository selection
3. Run `/repro-acquire` to clone the repositories
4. Then proceed with `/repro-fit-hardware` and `/repro-audit`

## Example

```
/repro-discover paper=https://arxiv.org/abs/2103.14641 keywords="S3DIS point cloud segmentation"
```

---

## Enhanced 6-step Flow (P10_T08)

The P10-hardened `/repro-discover` runs a more structured pipeline than
the original 4-step flow above.

| Step | Reads | Writes |
|---|---|---|
| **1. Generate search_plan** | paper metadata | `templates/search_plan.yaml` + `templates/search_plan.json` |
| **2. Four-phase search** | search_plan.yaml | `query_results/<backend>_<hash>.json` |
| **3. Score candidates (14 factors)** | query_results | `candidate_sources.csv`, `ranked_repositories.csv`, `paper_code_links.json`, `dataset_checkpoint_links.json` |
| **4. Verify (4 new checks)** | ranked candidates | `evidence_graph.json` |
| **5. Document gaps** | what was not found | `search_gaps.md` |
| **6. Append lessons** | this round's results | one row appended to `templates/search_lessons.jsonl` |

### Output

```
[repro-discover] step 1/6 generate search_plan ............. OK
[repro-discover] step 2/6 four-phase search ................ 47 candidates (P1: paper, P2: repos, P3: data, P4: failures)
[repro-discover] step 3/6 score candidates ................. 12 Tier-A, 37 Tier-B, 104 Tier-C
[repro-discover] step 4/6 verify ........................... 11/12 Tier-A pass
[repro-discover] step 5/6 document gaps .................... search_gaps.md (3 gaps)
[repro-discover] step 6/6 append lessons ................... OK (10 fields)
[repro-discover] decision = D__ → DECISION_LOG.md
```
