# Dataset Registry

> Canonical schema for documenting a dataset used (or referenced) in a
> reproduction project. Tier-A datasets **must** have all 12 field groups
> filled. Tier-B/C datasets are recommended to have a full entry; Tier-D/E
> entries are optional.

## Tier (one of: A Core Benchmark | B Pretraining | C Cross-domain | D Auxiliary | E Reference)

| Field | Value |
|---|---|
| **dataset_id** | short slug, e.g., `s3dis` |
| **dataset_name** | full name, e.g., `Stanford 3D Indoor Scene Dataset (S3DIS)` |
| **tier** | A / B / C / D / E |
| **direction** | one of the 20 GeoAI directions from `skills/paper-reproduction/SKILL.md` |
| **version** | e.g., `1.0`, or commit hash if from a GitHub repo |
| **license** | e.g., `Research-only (Stanford)` |
| **restricted** | true / false (true if access requires application) |
| **size_gb** | total disk footprint |
| **paper_url** | primary paper / dataset paper |
| **download_url** | where to obtain it (or "available on request") |
| **local_root_env** | env var that points to the local copy, e.g., `DATA_ROOT` |

---

## 12 Field Groups (each section is a sub-table)

### 1. Basic info (基本信息)

| Field | Value |
|---|---|
| **name** |  |
| **acronym** |  |
| **year** |  |
| **authors / maintainers** |  |

### 2. Task & modality (任务模态)

| Field | Value |
|---|---|
| **primary task** | segmentation / classification / detection / ... |
| **secondary tasks** |  |
| **input modality** | LiDAR / RGB / RGB-D / SAR / multispectral / ... |
| **output type** | per-point / per-voxel / per-scene / per-object |

### 3. Platform & scene (平台场景)

| Field | Value |
|---|---|
| **acquisition platform** | drone / handheld / vehicle / satellite / ... |
| **scene type** | indoor / outdoor / aerial / underwater / mixed |
| **geographic scope** | one region / multi-region / global |
| **spatial extent (km²)** |  |

### 4. Spatiotemporal properties (时空属性)

| Field | Value |
|---|---|
| **temporal coverage** | static / single-epoch / multi-epoch (with timestamps) |
| **temporal resolution** |  |
| **CRS / projection** | EPSG code or "local" |
| **geo-referenced** | true / false |

### 5. Scale (规模)

| Field | Value |
|---|---|
| **scenes / tiles** |  |
| **points (total)** |  |
| **classes** |  |
| **annotated instances** |  |
| **train / val / test split** |  |

### 6. Coordinates & labels (坐标标签)

| Field | Value |
|---|---|
| **label format** | per-point / per-object / per-scene |
| **label cardinality** | number of class IDs |
| **ignore label(s)** | list of raw IDs to ignore |
| **class mapping** | raw → remapped ID table (link to file) |

### 7. Class distribution (分布)

| Field | Value |
|---|---|
| **per-class point count** | link to CSV / plot |
| **imbalance ratio (max/min)** |  |
| **long-tail severity** | low / medium / high |

### 8. Evaluation protocol (评估)

| Field | Value |
|---|---|
| **default metric** | mIoU / OA / F1 / ... |
| **per-class breakdown** | required / optional |
| **voting / TTA** | none / vote-3 / flip / ... |
| **checkpoint selection** | best val / last / paper-specified |

### 9. Acquisition (获取)

| Field | Value |
|---|---|
| **download method** | direct / script / application form |
| **script path (in this repo)** |  |
| **expected md5 / sha256** |  |
| **size on disk (GB)** |  |
| **disk-i/o profile** | sequential / random / mixed |

### 10. Integrity (完整性)

| Field | Value |
|---|---|
| **md5 verified** | true / false |
| **file count (train)** |  |
| **file count (val)** |  |
| **file count (test)** |  |
| **missing / corrupted files** | list (or "none") |

### 11. Application fit (应用适配)

| Field | Value |
|---|---|
| **fits the paper's task** | yes / partial / no |
| **license permits reproduction** | yes / no / conditional |
| **hardware requirement** | fits / requires upgrade |
| **commonly used by** | list of papers using this dataset |

### 12. Verification status (验证状态)

| Field | Value |
|---|---|
| **local copy present** | true / false |
| **md5 matches** | true / false |
| **loader smoke test passed** | true / false / not run |
| **last verified** | ISO-8601 |
| **verified by** | human / agent |

---

## Example entry (Tier-A)

```markdown
# s3dis

| dataset_id | tier | direction | license | size_gb |
|---|---|---|---|---|
| s3dis | A | indoor scene understanding | research-only | 32 |
```

(All 12 field groups would be filled with the S3DIS-specific values:
6 areas × 272 rooms, 13 classes, mIoU protocol, etc.)