# Point Cloud Reproduction Skill

Use this skill when the task involves reproducing a 3D point cloud deep learning paper from a GitHub repository.

## When to Use This Skill

Apply this skill whenever:
- The paper involves 3D point cloud processing (segmentation, classification, detection)
- The model uses KPConv, PointNet++, DGCNN, or similar point cloud architectures
- The evaluation uses full-point-cloud voting (FPV) or stratified sampling
- The dataset involves ScanNet, S3DIS, SemanticKITTI, Semantic3D, or NPM3D
- Custom CUDA kernels are used for neighborhood search or convolution

## Point Cloud Specifics

### File Formats
- **PLY** files: Most common point cloud format. May use `plyfile` or `open3d` for reading.
- **OFF** files: Simple mesh/point format.
- **LAS/LAZ**: Lidar formats, may need `laspy`.
- **BIN** files: Raw binary arrays (commonly used for KITTI).

### Dataset Characteristics

| Dataset | Classes | Points/Scene | Files | Special Notes |
|---|---|---|---|---|
| S3DIS | 13 | ~150K–300K | HDF5/Raw | 6 areas, in-door |
| ScanNet | 20 | ~100K–200K | Raw BIN + CHIRP | Colored, need NYU40 mapping |
| SemanticKITTI | 19–25 | ~100K–1M | KITTI format | Mobile laser scanning, sequences |
| Semantic3D | 8 | Millions | Raw TXT/BIN | Terrestrial laser scanning |
| NPM3D | 10 | Millions | NPZ/HDF5 | Large-scale airborne |

### Label Mapping

Point cloud datasets often have **raw label IDs** and **remapped label IDs**. Always verify:

1. What is the raw label ID in the dataset files?
2. What is the remapped label ID used in the model's loss/evaluation?
3. Are ignored/void labels properly handled?

Example (ScanNet):
```
Raw: 1, 2, 3, ... 39, 40  (NYU40 IDs)
Remapped: 0, 1, 2, ... 18, 19  (0-indexed, 20 classes)
Ignored: 0  (unannotated)
```

### Data Splits

Point cloud datasets may use area-based or scene-based splits:
- **S3DIS**: Area 1-5 for training, Area 6 for testing (standard)
- **ScanNet**: Scenes 00xx for training, 04xx for validation, 08xx for testing
- **SemanticKITTI**: Sequences 00–07 for training, 08 for validation, 09–10 for testing

Always verify the exact split used in the paper, as different splits exist.

## Model Architectures

### KPConv (Kernel Point Convolution)

KPConv (Point Cloud Processing with Kernel Point Convolution) uses:
- **Kernel points**: Learnable point sets in 3D space
- **Deformable convolution**: Kernel points are displaced based on input
- **Flexible radius**: Can use different ball query radii

Key considerations:
- **Minimum points per ball**: Need enough neighbors for stable convolution
- **Radius**: Too small → sparse neighborhoods; too large → diluted features
- **Deformable vs. rigid**: Deformable is more expressive but harder to optimize

### Full-Point-Cloud (FPV) Voting

Point cloud segmentation models typically operate on **sub-points** (randomly sampled or strided) during training, but must evaluate on the **full point cloud** during inference.

FPV process:
1. Load full point cloud
2. Run model on overlapping sub-clouds (with overlap for boundary coverage)
3. Aggregate predictions (majority vote or weighted average)
4. Map back to original point indices

Memory considerations:
- FPV can require 10–50x more memory than sub-cloud inference
- May need to batch sub-clouds or use reduced precision
- Verify that FPV matches the paper's exact protocol

### Neighborhood Search

Most point cloud models use **ball query** neighborhood search:
```python
def ball_query(points, centers, radius, max_neighbors):
    # Find all points within radius of each center
    # Return indices of up to max_neighbors nearest neighbors
```

Custom CUDA implementations (e.g., pointnet2_ops from PointNet++) are often faster but:
- Require compilation against the correct CUDA version
- May not work on different GPU architectures
- Need to be compiled before running any training/evaluation

## Evaluation Protocol

### mIoU Computation

For point cloud segmentation, mIoU is typically computed per-class:

```python
def compute_miou(pred, target, num_classes, ignore_label=-100):
    ious = []
    for cls in range(num_classes):
        if cls == ignore_label:
            continue
        pred_cls = pred == cls
        target_cls = target == cls
        intersection = (pred_cls & target_cls).sum()
        union = (pred_cls | target_cls).sum()
        if union > 0:
            ious.append(intersection / union)
    return sum(ious) / len(ious)
```

### Full-Point-Cloud (FPV) Evaluation

FPV evaluation steps:
1. **Sub-cloud inference**: Run model on overlapping sub-clouds
2. **Aggregation**: Combine predictions (majority vote or softmax averaging)
3. **Label mapping**: Convert predicted labels back to original label space
4. **Metric computation**: Compute IoU per class on full point cloud

Common pitfalls:
- **Overlap handling**: Sub-clouds overlap at boundaries. How is this handled?
- **Label consistency**: Are all points labeled, or are some points void/ignored?
- **Batch effects**: Does aggregating from multiple sub-clouds introduce artifacts?

### Stratified Sampling (Alternative to FPV)

Some papers use stratified sampling instead of full FPV:
- Sample points stratified by class frequency
- Reduces memory but may miss rare class boundaries
- Must verify that sampling strategy matches the paper

## Memory Optimization for Point Clouds

### Checkpointing Strategies

```python
# Gradient checkpointing for memory savings
from torch.utils.checkpoint import checkpoint_sequential

model = nn.Sequential(*layers)
model = checkpoint_sequential(model, segments=4)
```

### Subsampling for Memory

```python
# Subsample points during training
n_points = 8192  # Paper default
idx = np.random.choice(pts.shape[0], n_points, replace=False)
points_sub = points[idx]
```

### Mixed Precision for Point Clouds

Point cloud operations are often memory-bound — mixed precision is especially beneficial:
- Use AMP/BF16 for the feature extraction stages
- Keep neighborhood indices as int32 (not FP16)
- Use `torch.cuda.amp.autocast(..., dtype=torch.bfloat16)` for KPConv forward

### FPV Memory Estimation

```
FPV memory ≈ (full_points / sub_points) × sub_cloud_memory × overlap_factor
```

Typical factors:
- Full points: 100K–300K per scene
- Sub points: 4K–16K per sub-cloud
- Overlap: 1.2–2.0x

A scene with 200K points, 8K sub-points, and 1.5x overlap needs ~38x the memory of single sub-cloud inference.

## CUDA Extensions for Point Clouds

Common CUDA extensions used in point cloud papers:

| Extension | Source | Use Case |
|---|---|---|
| pointnet2_ops | PointNet++ | FPS sampling, ball query, grouping |
| pointops | KPConv | Efficient point operations |
| spconv | Sparse convolution | 3D detection (PointPillars, etc.) |
| minkowski_engine | Sparse convolution | 4D spacetime convolutions |

### Checking CUDA Extension Compatibility

```python
import torch
print(f"CUDA: {torch.version.cuda}")
print(f"cuDNN: {torch.backends.cudnn.version()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"Compute capability: {torch.cuda.get_device_capability(0)}")
```

- Extensions must be compiled for the exact CUDA version
- Some extensions require specific GPU compute capabilities
- Binary wheels may not be available — may need to compile from source

## Common Point Cloud Pitfalls

| Pitfall | Symptom | Resolution |
|---|---|---|
| Label mapping mismatch | mIoU = 0 for some classes | Verify raw-to-remapped label mapping |
| FPV memory OOM | CUDA OOM during evaluation | Reduce sub-cloud size, batch FPV, use half precision |
| Neighborhood size | NaN in loss or unstable training | Check ball query radius and min neighbors |
| Custom CUDA fails | ImportError or compilation error | Verify CUDA version, try compiling from source |
| Sub-sampling inconsistency | Different results than reported | Verify exact sub-sampling strategy (random, FPS, stratified) |
| ScanNet color | Gray instead of RGB | Verify color channel order (RGB vs BGR) |
| SemanticKITTI label | Classes 20–23 missing | Verify that KITTI uses 19 classes (0–18) in main split |

## Integration with Other Skills

- `paper-reproduction` skill defines the general paper reproduction framework
- `deep-learning-runtime` skill provides DataLoader, AMP, and DDP optimization
- `reproduction-gates.mdc` rule enforces staged gates for point cloud reproductions
- Use `hardware-fit-auditor` agent to assess FPV memory requirements for your GPU
- Use `evidence-verifier` agent to audit checkpoint and FPV aggregation correctness
