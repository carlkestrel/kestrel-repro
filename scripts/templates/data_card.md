# Data Card

> Canonical data card. Filled in by `/repro-card`. Every "source:" link
> MUST resolve to a real file on disk.

## Top overview (总览)

| Field | Value |
|---|---|
| Dataset name |  |
| Version |  |
| License (SPDX) |  |
| Paper reference |  |
| Used split (train/val/test) |  |
| Total file count |  |
| Total size (GB) |  |
| Checksum (MD5/SHA256) |  |
| **source:** | `templates/research_contract.md` §3 |

---

## §1  Provenance (来源)

- Original URL (with date accessed)
- Mirror URL (if used)
- Citation (BibTeX)
- Contact / maintainer
- **source:**

## §2  Format (格式)

- File format (`.bin`, `.ply`, `.npz`, custom)
- On-disk structure (directory layout)
- Encoding (binary layout, endianness)
- **source:**

## §3  Schema (Schema)

- Per-sample fields (with type and shape)
- Annotation schema (class labels, instance ids, attributes)
- Coordinate convention (axis order, units)
- **source:**

## §4  Splits (划分)

- Train files (count + size + checksum)
- Val files (count + size + checksum)
- Test files (count + size + checksum)
- Cross-validation policy (if any)
- **source:**

## §5  Class mapping (类别映射)

| Class id | Label | Train count | Val count | Test count |
|---|---|---|---|---|
| 0 |  |  |  |  |
| 1 |  |  |  |  |
| ... |  |  |  |  |
| ignore |  |  |  |  |
- **source:**

## §6  Preprocessing (预处理)

- Voxelization (size + algorithm)
- Crop / sample (count per file)
- Augmentation (rotation, jitter, color)
- Normalization (per-channel stats)
- **source:**

## §7  Quality checks (质量检查)

- Missing files (count)
- Empty scenes (count)
- Out-of-range coordinates (count)
- Class distribution skew (max class / min class)
- **source:**

## §8  License & redistribution (许可与再分发)

- License (SPDX)
- Redistribution allowed?
- Attribution requirement
- Embargo (if any)
- **source:**

## §9  Known issues (已知问题)

- (e.g., "Area 5 of S3DIS has 12 scenes with broken labels, excluded by `ignore_label=-1`.")
- **source:**

## §10  Provenance chain (链路追溯)

- Download command (verbatim)
- Verification command (`md5sum` / `sha256sum`)
- Storage path (canonical)
- **source:**

---

## Appendix A — Per-sample inspection

| File | Size | Class histogram hash | OK? | Notes |
|---|---|---|---|---|
|  |  |  |  |  |
- **source:** inspection script + path

## Appendix B — Download log

```
# 2026-07-15 22:31 — wget https://.../dataset.zip
# 2026-07-15 22:35 — md5sum dataset.zip → <hash>
# 2026-07-15 22:36 — unzip → /data/dataset/v1/
```
- **source:** `download.log`

## Appendix C — Class confusion detail

- Top 10 confused class pairs (with counts)
- **source:** `confusion_matrix.json`

## Appendix D — Reproducibility hashes

- Train split MD5
- Val split MD5
- Test split MD5
- **source:** `data_hashes.json`

## Appendix E — Source citations

- Paper, official website, mirror URL, license text
- **source:** `templates/research_contract.md` §3