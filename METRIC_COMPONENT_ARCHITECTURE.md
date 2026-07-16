# Metric Protocol Auditor (MPA) - Architecture

**Component**: Metric Protocol Auditor  
**Version**: 1.0.0  
**Date**: 2026-07-16

---

## 1. Overview

The Metric Protocol Auditor (MPA) is a deterministic metric verification system that:

1. Discovers metrics from paper, code, configs, and logs
2. Builds protocol fingerprints for comparison
3. Recomputes metrics from raw evidence
4. Detects conflicts and protocol mismatches
5. Prevents false claims of paper reproduction

## 2. Module Structure

```
scripts/repro_agent/metrics/
├── __init__.py           # Package exports
├── models.py             # Core data models
├── schemas.py            # JSON schemas
├── registry.py           # Metric registry
├── recompute.py          # Deterministic metric computation
├── conflict_detector.py  # Conflict detection
├── hardcode_detector.py  # Hardcode detection
├── golden_test.py        # SiamKPConv golden test
├── takeover.py           # Project takeover
└── cli.py                # CLI interface
```

## 3. Core Data Models

### MetricDefinition
Defines a metric with its formula, aggregation, and scope.

### MetricProtocolFingerprint
Protocol fingerprint for comparing metrics across experiments.

### MetricObservation
Observed metric value with source and verification status.

### MetricSource
Source of metric information with role and confidence.

### MetricConflict
Detected conflict with severity and involved artifacts.

## 4. Pipeline

```
DISCOVER → EXTRACT → NORMALIZE → BUILD_METRIC_FINGERPRINT
    ↓
VALIDATE_PROTOCOL → RECOMPUTE → COMPARE → DETECT_CONFLICTS
    ↓
ISSUE_VERDICT → WRITE_REPORT
```

## 5. SiamKPConv Specific

### Paper Targets

| Class | IoU | Std |
|-------|-----|-----|
| Unchanged | 95.82 | 0.48 |
| New building | 86.67 | 0.47 |
| Demolition | 78.66 | 0.47 |
| New vegetation | 93.16 | 0.27 |
| Vegetation growth | 65.18 | 1.37 |
| Missing vegetation | 65.46 | 0.93 |
| Mobile objects | 91.55 | 0.60 |

### Key Metrics

- **mIoU_ch**: mean(IoU_1..IoU_6) = **80.12%** (excludes class 0 Unchanged)
- **mAcc**: 91.21 ± 0.68%
- **All-class mIoU**: NOT equal to 80.12% (includes class 0)

### Correct Paper Metadata

- **DOI**: 10.1016/j.isprsjprs.2023.02.001
- **Wrong DOI**: 10.1016/j.isprsjprs.2022.11.013 (must be rejected)

## 6. Usage

### CLI Commands

```bash
# Run golden test
python scripts/repro_agent/metrics/cli.py golden

# Discover metrics in project
python scripts/repro_agent/metrics/cli.py discover --project .

# Full project takeover
python scripts/repro_agent/metrics/cli.py takeover --project .

# Audit metric protocol
python scripts/repro_agent/metrics/cli.py audit --project .

# Recompute from confusion matrix
python scripts/repro_agent/metrics/cli.py recompute confusion_matrix.csv

# Detect conflicts
python scripts/repro_agent/metrics/cli.py conflicts --project .

# Verify protocol
python scripts/repro_agent/metrics/cli.py verify --project .

# Generate report
python scripts/repro_agent/metrics/cli.py report --project .

# Doctor checks
python scripts/repro_agent/metrics/cli.py doctor --project .
```

### Python API

```python
from repro_agent.metrics import (
    MetricRecomputer,
    ConflictDetector,
    HardcodeDetector,
    SiamKPConvGoldenTest,
)

# Recompute metrics
results = MetricRecomputer.recompute_from_confusion_matrix(cm, class_names=CLASS_NAMES)

# Detect conflicts
detector = ConflictDetector()
detector.detect_miou_vs_miou_ch(miou, miou_ch, class_0_iou)

# Run golden test
golden = SiamKPConvGoldenTest()
results = golden.run_all_tests()
```

## 7. Protocol Compatibility

### EXACT_MATCH
All critical fields match:
- Dataset, version, subset
- Split
- Label mapping
- Classes included/excluded
- Formula
- Full-PC/Full-resolution
- Checkpoint selector
- Run aggregation

### COMPARABLE_WITH_DECLARED_DEVIATION
Only minor differences (GPU, environment).

### PROTOCOL_MISMATCH
Critical differences:
- V1 vs V2 dataset
- mIoU vs mIoU_ch
- Batch vs full-PC
- Single vs multi-seed

## 8. Conflict Types

| Type | Severity | Description |
|------|----------|-------------|
| SAME_VALUE_DIFFERENT_NAMES | WARNING | Same value under different names |
| SAME_NAME_DIFFERENT_FORMULA | ERROR | Same name has different formulas |
| MIOU_VS_MIOU_CH | ERROR | mIoU includes Unchanged, mIoU_ch excludes |
| VALIDATION_VS_TEST | WARNING | Val and test confusion |
| SINGLE_VS_MULTI_SEED | WARNING | Single seed vs mean |
| HARDCODED_IN_PLOTTING | ERROR | Paper value in code |
| DATA_VERSION_CONFLICT | ERROR | V1 vs V2 mismatch |

## 9. Verdict States

| Verdict | Meaning |
|---------|---------|
| NO_METRIC_EVIDENCE | No metrics found |
| ENGINEERING_ONLY | Engineering works, no metrics |
| METRICS_UNVERIFIED | Metrics found but not verified |
| PROTOCOL_INCOMPLETE | Protocol incomplete |
| PROTOCOL_MISMATCH | Protocol mismatch |
| SINGLE_RUN_VERIFIED | Single seed verified |
| PARTIAL_REPRODUCTION | 1-2% from target |
| STATISTICAL_REPRODUCTION | 3+ seeds within 1% |
| BLOCKED | Cannot proceed |
| FAILED | Reproduction failed |

## 10. Integration Points

### With Orchestrator
- METRIC_PROTOCOL_LOCK gate before training
- METRIC_RECOMPUTE after evaluation
- METRIC_COMPARE before baseline table

### With Evidence Manager
- Uses artifacts/runs/ for evidence
- Links metric observations to runs

### With Report Generator
- Generates metric_protocol_audit.md
- Prevents false claims

---

*Generated: 2026-07-16*
