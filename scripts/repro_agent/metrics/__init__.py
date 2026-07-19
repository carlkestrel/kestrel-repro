"""
Metric Protocol Auditor (MPA) - Package Initialization
"""

from .conflict_detector import ConflictDetector
from .golden_test import SiamKPConvGoldenTest, run_golden_test
from .hardcode_detector import HardcodeDetector
from .models import (
    WRONG_DOIS,
    AbsentClassPolicy,
    ClassAggregation,
    ConflictType,
    DatasetVersion,
    DataSubset,
    Direction,
    EvaluationScope,
    MetricConflict,
    MetricDefinition,
    MetricObservation,
    MetricProtocolFingerprint,
    MetricSource,
    MetricStatus,
    PredictionLevel,
    ProjectVerdict,
    ProtocolCompatibility,
    RunManifest,
    SampleAggregation,
    SiamKPConv_CHANGE_CLASSES,
    SiamKPConv_CLASS_NAMES,
    SiamKPConv_MACC_STD,
    SiamKPConv_MACC_TARGET,
    SiamKPConv_MIOU_CH_STD,
    SiamKPConv_MIOU_CH_TARGET,
    SiamKPConv_NUM_CLASSES,
    SiamKPConv_PAPER_METADATA,
    SiamKPConv_PAPER_TARGET_STD,
    SiamKPConv_PAPER_TARGETS,
    SourceRole,
    SplitName,
    TaskType,
    Unit,
)
from .recompute import MetricRecomputer
from .registry import MetricRegistry, create_miou_ch_definition, get_standard_metrics
from .schemas import load_schema, save_schemas, validate_schema

__all__ = [
    # Models
    "MetricDefinition",
    "MetricObservation",
    "MetricProtocolFingerprint",
    "MetricSource",
    "MetricConflict",
    "RunManifest",
    # Enums
    "MetricStatus",
    "SourceRole",
    "TaskType",
    "Direction",
    "Unit",
    "ClassAggregation",
    "SampleAggregation",
    "AbsentClassPolicy",
    "PredictionLevel",
    "EvaluationScope",
    "ProjectVerdict",
    "ConflictType",
    "ProtocolCompatibility",
    "DatasetVersion",
    "DataSubset",
    "SplitName",
    # SiamKPConv Constants
    "SiamKPConv_CLASS_NAMES",
    "SiamKPConv_NUM_CLASSES",
    "SiamKPConv_CHANGE_CLASSES",
    "SiamKPConv_PAPER_TARGETS",
    "SiamKPConv_PAPER_TARGET_STD",
    "SiamKPConv_MIOU_CH_TARGET",
    "SiamKPConv_MIOU_CH_STD",
    "SiamKPConv_MACC_TARGET",
    "SiamKPConv_MACC_STD",
    "SiamKPConv_PAPER_METADATA",
    "WRONG_DOIS",
    # Functions
    "validate_schema",
    "load_schema",
    "save_schemas",
    "MetricRegistry",
    "get_standard_metrics",
    "create_miou_ch_definition",
    "MetricRecomputer",
    "ConflictDetector",
    "HardcodeDetector",
    "SiamKPConvGoldenTest",
    "run_golden_test",
]
