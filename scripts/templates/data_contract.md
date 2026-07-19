# Data Contract Template
# Documents the expected data schema and format for the reproduction.

## Dataset Overview

- **Name**: 
- **Version**: 
- **Source**: 
- **License**: 
- **Requires Application**: 

## Data Schema

### Directory Structure

```
${DATA_ROOT}/
├── train/
│   ├── area_1/
│   │   ├── scene_001.ply
│   │   └── scene_001.ply.seg
│   └── ...
├── val/
│   └── ...
└── test/
    └── ...
```

### Point Cloud File Format (.ply)

| Field | Type | Description |
|---|---|---|
| x | float32 | X coordinate |
| y | float32 | Y coordinate |
| z | float32 | Z coordinate |
| red | uint8 | R channel (0-255) |
| green | uint8 | G channel (0-255) |
| blue | uint8 | B channel (0-255) |

### Label File Format (.seg)

| Field | Type | Description |
|---|---|---|
| label | int | Per-point label ID |

## Label Mapping

| Raw Label ID | Class Name | Remapped ID | Ignored |
|---|---|---|---|
| 1 | ceiling | 0 | No |
| 2 | floor | 1 | No |
| ... | ... | ... | ... |

## Data Split

- **Training**: 
- **Validation**: 
- **Test**: 

## Data Augmentation

| Augmentation | Parameters | Paper Reference |
|---|---|---|
| Random rotation | θ ∈ [-π, π] | Section 3.2 |
| Random scale | s ∈ [0.9, 1.1] | Section 3.2 |
| Random flip | axis ∈ {x, y} | Section 3.2 |
| Random color jitter | σ = 0.01 | - |

## Metric Definition

**mIoU** = (1/C) × Σ IoU_c for c ∈ classes

Where:
- C = number of classes (excluding ignored)
- IoU_c = |pred ∩ target|_c / |pred ∪ target|_c

## Evaluation Protocol

- **Checkpoint Selection**: 
- **Voting**: 
- **TTA**: 

## Data Integrity

- **MD5 Hash**: 
- **File Count (train)**: 
- **File Count (val)**: 
- **File Count (test)**: 
- **Total Points (train)**: 
