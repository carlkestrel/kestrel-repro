# Paper Reproduction Skill

Use this skill when the task involves reproducing a deep learning paper from a GitHub repository.

## When to Use This Skill

Apply this skill whenever:
- A new deep learning paper repository is being analyzed for reproduction
- The user wants to understand what a paper claims and how to verify it
- Setting up a structured reproduction workflow for any deep learning paper
- Auditing a paper's claims against its implementation
- Planning experiments to reproduce a paper's results

## Core Principles

### Evidence-First Reproduction

Every claim must be backed by traceable evidence. A paper reproduction is only valid if:

1. The **exact commit** used is recorded
2. The **exact config** (hyperparameters, model, dataset) is recorded
3. The **dataset version** and **split** are recorded
4. The **random seed(s)** are recorded and all random states are seeded
5. The **exact command** run is recorded
6. **Raw metrics** (not summaries) are preserved
7. **Checkpoints** are saved and can reload to reproduce metrics
8. **Failed runs** are preserved with their logs

### Never Skip Gates

The staged gate system exists to prevent wasted GPU time on broken setups. The gates are:

- **Gate 0 — Paper/Source Audit**: Verify paper claims, repository commit, config alignment
- **Gate 1 — Preflight**: Environment, dependencies, dataset, disk space
- **Gate 2 — Short Loop (L0–L3)**: Smoke, overfit, mini-dataset, checkpoint resume
- **Gate 3 — Hardware Parity**: Strict vs. optimized mode comparison
- **Gate 4 — Full Training**: Only after all previous gates pass
- **Gate 5 — Evidence Verification**: Verify metrics are reproducible

**Never start full training before Gates 0–3 pass.**

### What This Skill Covers

#### 1. Paper Analysis
- Identify the **primary claim** (model architecture, training protocol, dataset)
- Identify the **target metrics** (exact metric definitions, per-class vs. mean)
- Identify the **evaluation protocol** (checkpoint selection, voting, TTA)
- Identify the **data split** (train/val/test ratios or specific splits)
- Identify any **ambiguities** in the paper that need resolution from the repository

#### 2. Repository Analysis
- Locate the **paper-author official repository** (primary)
- Locate **credible independent implementations** (references, max 3)
- Locate **tooling projects** (Hydra, MLflow, DVC, nvitop, TorchBench — optional)
- Verify **commit/version** matches the paper submission
- Check for **pretrained checkpoints**, **logs**, and **raw metrics**

#### 3. Configuration Analysis
- Extract the **exact training configuration** from the repository
- Compare **paper hyperparameters** vs. **repository defaults**
- Identify **environment-specific settings** (paths, device IDs)
- Check for **custom CUDA extensions** and their compilation requirements

#### 4. Evidence Planning
- Define what **evidence artifacts** must be produced at each phase
- Define what **gate criteria** must be met before advancing
- Define **metric tolerance** for parity testing (typically ±0.5% for mIoU)
- Define **seed strategy** (single seed vs. multiple seeds with mean ± std)

## Evidence Chain Template

For every experiment run, record:

```yaml
run_id: "<uuid>"
timestamp: "<ISO 8601>"
commit: "<git hash>"
branch: "<branch or tag>"
config: "<path to config file or inline>"
dataset:
  name: "<dataset name>"
  version: "<version or git hash>"
  split: "<train/val/test split definition>"
  manifest: "<path to data manifest>"
seed: <integer or list>
command: "<exact command with all arguments>"
environment:
  python: "<version>"
  pytorch: "<version>"
  cuda: "<version>"
  gpu: "<model>"
  driver: "<driver version>"
mode: "<strict_repro | optimized_repro_safe | experimental_fast>"
checkpoints:
  - path: "<path>"
    epoch: <n>
    metric: <value>
raw_metrics:
  path: "<path to raw metrics file>"
  format: "<json | csv | tensorboard>"
final_metrics:
  metric_name: <value>
  metric_source: "<how this was computed>"
artifacts:
  logs: "<path>"
  predictions: "<path>"
  figures: "<path>"
status: "<success | failed | incomplete>"
failure_reason: "<if failed>"
```

## Common Failure Modes

| Failure Mode | Symptom | Resolution |
|---|---|---|
| Missing data split | Can't determine train/val split | Request clarification from paper authors or infer from code |
| Metric mismatch | Computed metric ≠ reported metric | Audit metric computation — per-class vs. mean, ignored labels |
| Checkpoint selection | Best checkpoint ≠ reported result | Try all checkpoints, verify eval protocol |
| Seed sensitivity | Results vary wildly across seeds | Run multiple seeds if paper reports mean ± std |
| Hardware difference | GPU architecture differences cause numerical divergence | Use FP32 strict mode, document GPU model |
| Dataset version | Newer dataset version has different classes | Pin to the exact dataset version used in the paper |
| Environment mismatch | Code runs but produces NaN/Inf | Check CUDA/cuDNN/PyTorch version compatibility |

## What This Skill Does NOT Cover

- **Point-cloud-specific** operations (use `point-cloud-reproduction` skill)
- **Hardware optimization** details (use `deep-learning-runtime` skill)
- **Repository selection** (use `repo-scout` agent or `repository-selection` skill)
- **Automatic hyperparameter tuning** (Optuna, etc. are forbidden until baseline passes)
- **Architecture modifications** (never change model architecture during reproduction)
- **Loss function changes** (never substitute loss functions)
- **Data augmentation modifications** (never skip or change augmentation during baseline)

## Integration with Other Skills

- Use `paper-reproduction` as the foundation for all deep learning paper reproductions
- Use `deep-learning-runtime` when optimizing DataLoader, AMP, DDP, or batch size
- Use `point-cloud-reproduction` when the paper involves 3D point clouds, KPConv, or full-PC voting
- Use the `repository-selection` skill when evaluating candidate repositories before cloning
- Consult `reproduction-gates.mdc` rule before starting any training

---

## Topic Search Space (P9_T01) — 20 GeoAI directions

The dl-paper-repro skill searches across **20 directions** in GeoAI / spatial
data science. A reproduction project may span more than one direction; the
"primary direction" drives the candidate-search query expansion.

| # | Direction | Canonical query terms (ArXiv / SemanticScholar / GitHub) |
|---|---|---|
| 1 | 摄影测量与遥感 / Photogrammetry & Remote Sensing | `photogrammetry, remote sensing, aerial imagery, multispectral, hyperspectral` |
| 2 | LiDAR 点云处理 / LiDAR Point Cloud Processing | `LiDAR, point cloud, ALS, TLS, airborne laser scanning` |
| 3 | 视觉 3D 重建 / Visual 3D Reconstruction | `visual 3D, NeRF, Gaussian Splatting, MVS, structure from motion` |
| 4 | 城市与建筑信息学 / Urban & Building Informatics | `urban modeling, BIM, city-scale, voxelization, urban analytics` |
| 5 | 道路与交通 / Road & Transportation | `lane detection, traffic, autonomous driving, road extraction, BEV` |
| 6 | 室内场景理解 / Indoor Scene Understanding | `indoor segmentation, S3DIS, ScanNet, indoor reconstruction, RGB-D` |
| 7 | 室外场景理解 / Outdoor Scene Understanding | `semantic segmentation, outdoor scene, urban scene, point cloud segmentation` |
| 8 | 点云变化检测 / Point Cloud Change Detection | `change detection, point cloud change, temporal point cloud, bi-temporal` |
| 9 | 多模态融合 / Multimodal Fusion | `multimodal fusion, cross-modal, image-LiDAR fusion, sensor fusion` |
| 10 | 自监督/弱监督点云 / Self-/Weakly-supervised Point Cloud | `self-supervised point cloud, weakly supervised, contrastive 3D, masked point` |
| 11 | 少样本点云 / Few-shot Point Cloud | `few-shot, low-shot, scarce annotation 3D` |
| 12 | 点云配准与定位 / Point Cloud Registration & Localization | `point cloud registration, ICP, SLAM, LiDAR odometry` |
| 13 | 点云生成与扩散 / Point Cloud Generation & Diffusion | `point cloud generation, diffusion 3D, point VAE, point GAN` |
| 14 | 环境空间信息学 / Environmental Spatial Intelligence | `environmental monitoring, ecology remote sensing, habitat mapping, carbon` |
| 15 | 灾害评估与应急 / Disaster Assessment & Response | `disaster response, damage assessment, flood mapping, earthquake damage` |
| 16 | 农业与植被 / Agriculture & Vegetation | `crop classification, phenology, yield estimation, vegetation index` |
| 17 | 水文气象 / Hydrology & Meteorology | `precipitation nowcasting, weather forecasting, river segmentation, hydrology` |
| 18 | 冰川/极地 / Cryosphere & Polar | `glacier, sea ice, ice sheet, polar remote sensing, ICESat` |
| 19 | 海洋与海岸 / Ocean & Coastal | `ocean remote sensing, bathymetry, coastal monitoring, SAR ocean` |
| 20 | 数字孪生与可视化 / Digital Twin & Visualization | `digital twin, geospatial visualization, 3DGS, urban digital twin, Cesium` |

### Search-breadth rule

A single search query must combine **at least 3** of the following axes:

- **Task**: segmentation, classification, detection, reconstruction, generation, change detection
- **Sensor / modality**: LiDAR, optical, SAR, multispectral, RGB-D, hyperspectral
- **Application**: autonomous driving, urban analytics, environmental monitoring, …
- **Method family**: transformer, GNN, diffusion, contrastive, Mamba, …
- **Dataset**: S3DIS, ScanNet, nuScenes, ModelNet40, ShapeNet, …
- **Year range**: ≤2-year window unless the topic has <50 papers/year

### Direction-relevance scoring (A–E)

For each candidate paper / repo / dataset, assign a relevance tier:

| Tier | Criteria |
|---|---|
| **A — Core** | Matches primary direction + uses target dataset + cites paper of interest |
| **B — Adjacent** | Matches primary direction OR uses target dataset, not both |
| **C — Tangential** | Different direction but transferable method (e.g., transformer × 2D → 3D) |
| **D — Background** | General DL baseline (ResNet, ViT) cited by many GeoAI papers |
| **E — Off-topic** | None of the above; keep only if < 30 candidates exist |

Cumulative tier counts are written to `templates/topic_graph.json` per
direction.
