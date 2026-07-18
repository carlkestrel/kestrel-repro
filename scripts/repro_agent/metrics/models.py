"""
Metric Protocol Auditor (MPA) - Core Data Models

This module defines the core data models for the metric protocol auditor:
- MetricDefinition: Definition of a metric
- MetricProtocolFingerprint: Protocol fingerprint for comparison
- MetricObservation: Observed metric value
- MetricSource: Source of metric information
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_hash(obj: Any) -> str:
    """Compute deterministic hash of any JSON-serializable object."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


class SourceRole(str, Enum):
    """Role of a metric source in the evidence chain."""
    TARGET_VALUE = "TARGET_VALUE"
    FORMULA_DEFINITION = "FORMULA_DEFINITION"
    DATASET_PROTOCOL = "DATASET_PROTOCOL"
    EVALUATION_PROTOCOL = "EVALUATION_PROTOCOL"
    RUN_OBSERVATION = "RUN_OBSERVATION"
    DERIVED_RESULT = "DERIVED_RESULT"
    UNVERIFIED_REPORT = "UNVERIFIED_REPORT"


class MetricStatus(str, Enum):
    """Status of a metric."""
    MISSING = "MISSING"
    DISCOVERED = "DISCOVERED"
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    RECOMPUTED = "RECOMPUTED"
    EXACT_MATCH = "EXACT_MATCH"
    COMPARABLE = "COMPARABLE"
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    CORRUPTED = "CORRUPTED"
    STALE = "STALE"
    SIMULATED = "SIMULATED"


class TaskType(str, Enum):
    """Type of ML task."""
    CLASSIFICATION = "classification"
    SEGMENTATION = "segmentation"
    OBJECT_DETECTION = "object_detection"
    SEMANTIC_SEGMENTATION = "semantic_segmentation"
    INSTANCE_SEGMENTATION = "instance_segmentation"
    CHANGE_DETECTION = "change_detection"
    POINT_CLOUD_SEGMENTATION = "point_cloud_segmentation"
    POINT_CLOUD_CHANGE_DETECTION = "point_cloud_change_detection"


class Direction(str, Enum):
    """Optimization direction."""
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class Unit(str, Enum):
    """Unit of measurement."""
    FRACTION = "fraction"  # 0-1
    PERCENT = "percent"   # 0-100
    SCALAR = "scalar"     # arbitrary


class ClassAggregation(str, Enum):
    """Class-level aggregation method."""
    MACRO = "macro"        # mean over classes
    MICRO = "micro"        # aggregate TP/FP/FN then compute
    WEIGHTED = "weighted" # weighted by class frequency
    NONE = "none"          # per-class only


class SampleAggregation(str, Enum):
    """Sample-level aggregation method."""
    GLOBAL = "global"       # accumulate all samples
    PER_BATCH = "per_batch" # average over batches
    PER_TILE = "per_tile"   # average over tiles
    PER_SCENE = "per_scene" # average over scenes
    PER_CLOUD_PAIR = "per_cloud_pair"  # average over cloud pairs


class AbsentClassPolicy(str, Enum):
    """Policy for handling absent classes."""
    IGNORE = "ignore"  # skip in aggregation
    ZERO = "zero"      # treat as IoU=0
    ERROR = "error"    # raise error


class PredictionLevel(str, Enum):
    """Level of prediction."""
    POINT = "point"
    VOXEL = "voxel"
    PIXEL = "pixel"
    OBJECT = "object"
    SCENE = "scene"
    CLOUD_PAIR = "cloud_pair"


class EvaluationScope(str, Enum):
    """Scope of evaluation."""
    BATCH = "batch"
    CROP = "crop"
    TILE = "tile"
    CYLINDER = "cylinder"
    SCENE = "scene"
    FULL_PC = "full_pc"
    FULL_DATASET = "full_dataset"


class ProjectVerdict(str, Enum):
    """Overall project verdict."""
    NO_METRIC_EVIDENCE = "NO_METRIC_EVIDENCE"
    ENGINEERING_ONLY = "ENGINEERING_ONLY"
    METRICS_UNVERIFIED = "METRICS_UNVERIFIED"
    PROTOCOL_INCOMPLETE = "PROTOCOL_INCOMPLETE"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
    SINGLE_RUN_VERIFIED = "SINGLE_RUN_VERIFIED"
    PARTIAL_REPRODUCTION = "PARTIAL_REPRODUCTION"
    STATISTICAL_REPRODUCTION = "STATISTICAL_REPRODUCTION"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ConflictType(str, Enum):
    """Type of metric conflict."""
    SAME_VALUE_DIFFERENT_NAMES = "SAME_VALUE_DIFFERENT_NAMES"
    SAME_NAME_DIFFERENT_FORMULA = "SAME_NAME_DIFFERENT_FORMULA"
    REPORT_INCONSISTENT_WITH_RAW = "REPORT_INCONSISTENT_WITH_RAW"
    CSV_INCONSISTENT_WITH_LOGS = "CSV_INCONSISTENT_WITH_LOGS"
    CHECKPOINT_MISMATCH = "CHECKPOINT_MISMATCH"
    UNIT_CONFUSION = "UNIT_CONFUSION"
    MIOU_VS_MIOU_CH = "MIOU_VS_MIOU_CH"
    VALIDATION_VS_TEST = "VALIDATION_VS_TEST"
    SINGLE_VS_MULTI_SEED = "SINGLE_VS_MULTI_SEED"
    HARDCODED_IN_PLOTTING = "HARDCODED_IN_PLOTTING"
    IMAGE_WITHOUT_DATA = "IMAGE_WITHOUT_DATA"
    STALE_RUN = "STALE_RUN"
    DATA_VERSION_CONFLICT = "DATA_VERSION_CONFLICT"
    CLASS_MAPPING_CONFLICT = "CLASS_MAPPING_CONFLICT"


class ProtocolCompatibility(str, Enum):
    """Protocol compatibility level."""
    EXACT_MATCH = "EXACT_MATCH"
    COMPARABLE_WITH_DECLARED_DEVIATION = "COMPARABLE_WITH_DECLARED_DEVIATION"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"


class DatasetVersion(str, Enum):
    """Dataset version."""
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    UNKNOWN = "UNKNOWN"


class DataSubset(str, Enum):
    """Data subset type."""
    LOW_DENSITY_LIDAR = "low_density_LiDAR"
    MULTI_SENSOR = "multi_sensor"
    FULL_DENSITY = "full_density"
    SYNTHETIC = "synthetic"
    MIXED = "mixed"
    UNKNOWN = "UNKNOWN"


class SplitName(str, Enum):
    """Standard split names."""
    TRAIN = "train"
    VAL = "val"
    VALIDATION = "validation"
    TEST = "test"
    TRAIN_VAL = "train_val"
    TRAIN_VAL_TEST = "train_val_test"


# ──────────────────────────────────────────────────────────────────────────────
# Core Data Models
# ──────────────────────────────────────────────────────────────────────────────

class MetricDefinition:
    """Definition of a metric."""

    def __init__(
        self,
        metric_id: str,
        canonical_name: str,
        display_name: str,
        task_type: TaskType,
        direction: Direction,
        formula: str,
        unit: Unit = Unit.FRACTION,
        class_aggregation: ClassAggregation = ClassAggregation.MACRO,
        sample_aggregation: SampleAggregation = SampleAggregation.GLOBAL,
        ignored_labels: list[int] | None = None,
        included_classes: list[int] | None = None,
        absent_class_policy: AbsentClassPolicy = AbsentClassPolicy.ZERO,
        prediction_level: PredictionLevel = PredictionLevel.POINT,
        evaluation_scope: EvaluationScope = EvaluationScope.FULL_DATASET,
    ):
        self.metric_id = metric_id
        self.canonical_name = canonical_name
        self.display_name = display_name
        self.task_type = task_type
        self.direction = direction
        self.formula = formula
        self.formula_hash = compute_hash(formula)
        self.unit = unit
        self.class_aggregation = class_aggregation
        self.sample_aggregation = sample_aggregation
        self.ignored_labels = ignored_labels or []
        self.included_classes = included_classes or []
        self.absent_class_policy = absent_class_policy
        self.prediction_level = prediction_level
        self.evaluation_scope = evaluation_scope

    def to_dict(self) -> dict:
        return {
            "metric_id": self.metric_id,
            "canonical_name": self.canonical_name,
            "display_name": self.display_name,
            "task_type": self.task_type.value,
            "direction": self.direction.value,
            "formula": self.formula,
            "formula_hash": self.formula_hash,
            "unit": self.unit.value,
            "class_aggregation": self.class_aggregation.value,
            "sample_aggregation": self.sample_aggregation.value,
            "ignored_labels": self.ignored_labels,
            "included_classes": self.included_classes,
            "absent_class_policy": self.absent_class_policy.value,
            "prediction_level": self.prediction_level.value,
            "evaluation_scope": self.evaluation_scope.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MetricDefinition:
        return cls(
            metric_id=d["metric_id"],
            canonical_name=d["canonical_name"],
            display_name=d["display_name"],
            task_type=TaskType(d["task_type"]),
            direction=Direction(d["direction"]),
            formula=d["formula"],
            unit=Unit(d.get("unit", "fraction")),
            class_aggregation=ClassAggregation(d.get("class_aggregation", "macro")),
            sample_aggregation=SampleAggregation(d.get("sample_aggregation", "global")),
            ignored_labels=d.get("ignored_labels"),
            included_classes=d.get("included_classes"),
            absent_class_policy=AbsentClassPolicy(d.get("absent_class_policy", "zero")),
            prediction_level=PredictionLevel(d.get("prediction_level", "point")),
            evaluation_scope=EvaluationScope(d.get("evaluation_scope", "full_dataset")),
        )


class MetricProtocolFingerprint:
    """
    Protocol fingerprint for metric comparison.
    
    This is the canonical representation of a metric's protocol,
    used to determine if two metrics can be compared.
    """

    def __init__(
        self,
        paper_id: str | None = None,
        task_type: TaskType | None = None,
        dataset_name: str | None = None,
        dataset_version: DatasetVersion | None = None,
        dataset_subset: DataSubset | None = None,
        split_name: SplitName | None = None,
        split_manifest_hash: str | None = None,
        label_mapping_hash: str | None = None,
        num_classes: int | None = None,
        included_classes: list[int] | None = None,
        excluded_classes: list[int] | None = None,
        ignore_index: int | None = None,
        prediction_level: PredictionLevel | None = None,
        evaluation_scope: EvaluationScope | None = None,
        full_resolution: bool | None = None,
        full_pc: bool | None = None,
        voting_runs: int | None = None,
        interpolation_method: str | None = None,
        postprocessing: str | None = None,
        metric_id: str | None = None,
        formula_hash: str | None = None,
        class_aggregation: ClassAggregation | None = None,
        sample_aggregation: SampleAggregation | None = None,
        checkpoint_selector: str | None = None,  # best, latest, epoch_N
        checkpoint_epoch: int | None = None,
        seed_policy: str | None = None,  # single, mean, median
        run_aggregation: str | None = None,  # single, mean, std, median
        unit: Unit | None = None,
    ):
        self.paper_id = paper_id
        self.task_type = task_type
        self.dataset_name = dataset_name
        self.dataset_version = dataset_version
        self.dataset_subset = dataset_subset
        self.split_name = split_name
        self.split_manifest_hash = split_manifest_hash
        self.label_mapping_hash = label_mapping_hash
        self.num_classes = num_classes
        self.included_classes = included_classes or []
        self.excluded_classes = excluded_classes or []
        self.ignore_index = ignore_index
        self.prediction_level = prediction_level
        self.evaluation_scope = evaluation_scope
        self.full_resolution = full_resolution
        self.full_pc = full_pc
        self.voting_runs = voting_runs
        self.interpolation_method = interpolation_method
        self.postprocessing = postprocessing
        self.metric_id = metric_id
        self.formula_hash = formula_hash
        self.class_aggregation = class_aggregation
        self.sample_aggregation = sample_aggregation
        self.checkpoint_selector = checkpoint_selector
        self.checkpoint_epoch = checkpoint_epoch
        self.seed_policy = seed_policy
        self.run_aggregation = run_aggregation
        self.unit = unit

    @property
    def fingerprint_hash(self) -> str:
        """Compute hash of protocol fingerprint."""
        return compute_hash(self.to_dict())

    def is_compatible_with(self, other: MetricProtocolFingerprint) -> ProtocolCompatibility:
        """
        Check if this protocol is compatible with another.
        
        Returns EXACT_MATCH, COMPARABLE_WITH_DECLARED_DEVIATION, or PROTOCOL_MISMATCH.
        """
        mismatches = []

        # Critical fields that must match
        critical_fields = [
            ("dataset_name", "Dataset name"),
            ("dataset_version", "Dataset version"),
            ("dataset_subset", "Dataset subset"),
            ("split_name", "Split name"),
            ("label_mapping_hash", "Label mapping"),
            ("num_classes", "Number of classes"),
            ("included_classes", "Included classes"),
            ("excluded_classes", "Excluded classes"),
            ("prediction_level", "Prediction level"),
            ("evaluation_scope", "Evaluation scope"),
            ("full_resolution", "Full resolution"),
            ("full_pc", "Full point cloud"),
            ("metric_id", "Metric ID"),
            ("formula_hash", "Formula"),
            ("class_aggregation", "Class aggregation"),
            ("sample_aggregation", "Sample aggregation"),
            ("checkpoint_selector", "Checkpoint selector"),
            ("run_aggregation", "Run aggregation"),
        ]

        for field, name in critical_fields:
            self_val = getattr(self, field)
            other_val = getattr(other, field)
            if self_val != other_val and self_val is not None and other_val is not None:
                mismatches.append(f"{name}: {self_val} vs {other_val}")

        if not mismatches:
            return ProtocolCompatibility.EXACT_MATCH

        # Check if mismatches are minor (comparable)
        minor_fields = [
            "voting_runs",
            "interpolation_method",
            "postprocessing",
            "checkpoint_epoch",
        ]

        for field in minor_fields:
            if field in mismatches:
                return ProtocolCompatibility.COMPARABLE_WITH_DECLARED_DEVIATION

        return ProtocolCompatibility.PROTOCOL_MISMATCH

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "task_type": self.task_type.value if self.task_type else None,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version.value if self.dataset_version else None,
            "dataset_subset": self.dataset_subset.value if self.dataset_subset else None,
            "split_name": self.split_name.value if self.split_name else None,
            "split_manifest_hash": self.split_manifest_hash,
            "label_mapping_hash": self.label_mapping_hash,
            "num_classes": self.num_classes,
            "included_classes": self.included_classes,
            "excluded_classes": self.excluded_classes,
            "ignore_index": self.ignore_index,
            "prediction_level": self.prediction_level.value if self.prediction_level else None,
            "evaluation_scope": self.evaluation_scope.value if self.evaluation_scope else None,
            "full_resolution": self.full_resolution,
            "full_pc": self.full_pc,
            "voting_runs": self.voting_runs,
            "interpolation_method": self.interpolation_method,
            "postprocessing": self.postprocessing,
            "metric_id": self.metric_id,
            "formula_hash": self.formula_hash,
            "class_aggregation": self.class_aggregation.value if self.class_aggregation else None,
            "sample_aggregation": self.sample_aggregation.value if self.sample_aggregation else None,
            "checkpoint_selector": self.checkpoint_selector,
            "checkpoint_epoch": self.checkpoint_epoch,
            "seed_policy": self.seed_policy,
            "run_aggregation": self.run_aggregation,
            "unit": self.unit.value if self.unit else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MetricProtocolFingerprint:
        return cls(
            paper_id=d.get("paper_id"),
            task_type=TaskType(d["task_type"]) if d.get("task_type") else None,
            dataset_name=d.get("dataset_name"),
            dataset_version=DatasetVersion(d["dataset_version"]) if d.get("dataset_version") else None,
            dataset_subset=DataSubset(d["dataset_subset"]) if d.get("dataset_subset") else None,
            split_name=SplitName(d["split_name"]) if d.get("split_name") else None,
            split_manifest_hash=d.get("split_manifest_hash"),
            label_mapping_hash=d.get("label_mapping_hash"),
            num_classes=d.get("num_classes"),
            included_classes=d.get("included_classes"),
            excluded_classes=d.get("excluded_classes"),
            ignore_index=d.get("ignore_index"),
            prediction_level=PredictionLevel(d["prediction_level"]) if d.get("prediction_level") else None,
            evaluation_scope=EvaluationScope(d["evaluation_scope"]) if d.get("evaluation_scope") else None,
            full_resolution=d.get("full_resolution"),
            full_pc=d.get("full_pc"),
            voting_runs=d.get("voting_runs"),
            interpolation_method=d.get("interpolation_method"),
            postprocessing=d.get("postprocessing"),
            metric_id=d.get("metric_id"),
            formula_hash=d.get("formula_hash"),
            class_aggregation=ClassAggregation(d["class_aggregation"]) if d.get("class_aggregation") else None,
            sample_aggregation=SampleAggregation(d["sample_aggregation"]) if d.get("sample_aggregation") else None,
            checkpoint_selector=d.get("checkpoint_selector"),
            checkpoint_epoch=d.get("checkpoint_epoch"),
            seed_policy=d.get("seed_policy"),
            run_aggregation=d.get("run_aggregation"),
            unit=Unit(d["unit"]) if d.get("unit") else None,
        )


class MetricSource:
    """Source of metric information."""

    def __init__(
        self,
        source_id: str,
        source_type: str,
        source_role: SourceRole,
        path_or_url: str | None = None,
        file_hash: str | None = None,
        paper_page: int | None = None,
        paper_table: str | None = None,
        table_row: str | None = None,
        table_column: str | None = None,
        code_symbol: str | None = None,
        config_key: str | None = None,
        extractor: str | None = None,
        extraction_confidence: float = 0.0,
    ):
        self.source_id = source_id
        self.source_type = source_type
        self.source_role = source_role
        self.path_or_url = path_or_url
        self.file_hash = file_hash
        self.paper_page = paper_page
        self.paper_table = paper_table
        self.table_row = table_row
        self.table_column = table_column
        self.code_symbol = code_symbol
        self.config_key = config_key
        self.extractor = extractor
        self.extraction_confidence = extraction_confidence
        self.created_at = utc_now()

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_role": self.source_role.value,
            "path_or_url": self.path_or_url,
            "file_hash": self.file_hash,
            "paper_page": self.paper_page,
            "paper_table": self.paper_table,
            "table_row": self.table_row,
            "table_column": self.table_column,
            "code_symbol": self.code_symbol,
            "config_key": self.config_key,
            "extractor": self.extractor,
            "extraction_confidence": self.extraction_confidence,
            "created_at": self.created_at,
        }


class MetricObservation:
    """Observed metric value."""

    def __init__(
        self,
        observation_id: str,
        metric_id: str,
        run_id: str | None = None,
        value: float | None = None,
        unit: Unit = Unit.FRACTION,
        protocol_fingerprint: MetricProtocolFingerprint | None = None,
        source_id: str | None = None,
        raw_evidence_paths: list[str] | None = None,
        verification_status: MetricStatus = MetricStatus.UNVERIFIED,
        warnings: list[str] | None = None,
        per_class_values: dict[int, float] | None = None,
        std: float | None = None,
        n_samples: int | None = None,
    ):
        self.observation_id = observation_id
        self.run_id = run_id
        self.metric_id = metric_id
        self.value = value
        self.unit = unit
        self.protocol_fingerprint = protocol_fingerprint
        self.source_id = source_id
        self.raw_evidence_paths = raw_evidence_paths or []
        self.computed_at = utc_now()
        self.computation_version = "1.0.0"
        self.verification_status = verification_status
        self.warnings = warnings or []
        self.per_class_values = per_class_values
        self.std = std
        self.n_samples = n_samples

    def to_dict(self) -> dict:
        return {
            "observation_id": self.observation_id,
            "run_id": self.run_id,
            "metric_id": self.metric_id,
            "value": self.value,
            "unit": self.unit.value,
            "protocol_fingerprint": self.protocol_fingerprint.to_dict() if self.protocol_fingerprint else None,
            "source_id": self.source_id,
            "raw_evidence_paths": self.raw_evidence_paths,
            "computed_at": self.computed_at,
            "computation_version": self.computation_version,
            "verification_status": self.verification_status.value,
            "warnings": self.warnings,
            "per_class_values": self.per_class_values,
            "std": self.std,
            "n_samples": self.n_samples,
        }


class MetricConflict:
    """Conflict between metric definitions or observations."""

    def __init__(
        self,
        conflict_id: str,
        conflict_type: ConflictType,
        description: str,
        involved_observations: list[str] | None = None,
        involved_sources: list[str] | None = None,
        severity: str = "ERROR",
    ):
        self.conflict_id = conflict_id
        self.conflict_type = conflict_type
        self.description = description
        self.involved_observations = involved_observations or []
        self.involved_sources = involved_sources or []
        self.severity = severity
        self.detected_at = utc_now()

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "description": self.description,
            "involved_observations": self.involved_observations,
            "involved_sources": self.involved_sources,
            "severity": self.severity,
            "detected_at": self.detected_at,
        }


class RunManifest:
    """Manifest for a training run."""

    def __init__(
        self,
        run_id: str,
        seed: int,
        git_commit: str | None = None,
        code_diff_hash: str | None = None,
        config: dict | None = None,
        environment: dict | None = None,
        gpu_info: dict | None = None,
        start_command: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        best_checkpoint: str | None = None,
        best_epoch: int | None = None,
        status: str = "UNKNOWN",
    ):
        self.run_id = run_id
        self.seed = seed
        self.git_commit = git_commit
        self.code_diff_hash = code_diff_hash
        self.config = config or {}
        self.environment = environment or {}
        self.gpu_info = gpu_info or {}
        self.start_command = start_command
        self.start_time = start_time or utc_now()
        self.end_time = end_time
        self.best_checkpoint = best_checkpoint
        self.best_epoch = best_epoch
        self.status = status

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "git_commit": self.git_commit,
            "code_diff_hash": self.code_diff_hash,
            "config": self.config,
            "environment": self.environment,
            "gpu_info": self.gpu_info,
            "start_command": self.start_command,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "best_checkpoint": self.best_checkpoint,
            "best_epoch": self.best_epoch,
            "status": self.status,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Siamese KPConv Specific Constants
# ──────────────────────────────────────────────────────────────────────────────

SiamKPConv_CLASS_NAMES = [
    "Unchanged",
    "New building",
    "Demolition",
    "New vegetation",
    "Vegetation growth",
    "Missing vegetation",
    "Mobile objects",
]

SiamKPConv_NUM_CLASSES = 7

SiamKPConv_LABEL_RANGE = (0, 6)

SiamKPConv_CHANGE_CLASSES = [1, 2, 3, 4, 5, 6]  # Excludes Unchanged

SiamKPConv_PAPER_TARGETS = {
    "Unchanged": 95.82,
    "New building": 86.67,
    "Demolition": 78.66,
    "New vegetation": 93.16,
    "Vegetation growth": 65.18,
    "Missing vegetation": 65.46,
    "Mobile objects": 91.55,
}

SiamKPConv_PAPER_TARGET_STD = {
    "Unchanged": 0.48,
    "New building": 0.47,
    "Demolition": 0.47,
    "New vegetation": 0.27,
    "Vegetation growth": 1.37,
    "Missing vegetation": 0.93,
    "Mobile objects": 0.60,
}

# mIoU_ch = mean of classes 1-6 (excluding Unchanged)
SiamKPConv_MIOU_CH_TARGET = 80.12
SiamKPConv_MIOU_CH_STD = 0.02

SiamKPConv_MACC_TARGET = 91.21
SiamKPConv_MACC_STD = 0.68

SiamKPConv_PAPER_METADATA = {
    "title": "Siamese KPConv: 3D multiple change detection from raw point clouds using deep learning",
    "authors": ["Iris de Gélis", "Sébastien Lefèvre", "Thomas Corpetti"],
    "journal": "ISPRS Journal of Photogrammetry and Remote Sensing",
    "volume": 197,
    "pages": "274–291",
    "year": 2023,
    "doi": "10.1016/j.isprsjprs.2023.02.001",
    "code_url": "https://github.com/IdeGelis/torch-points3d-SiameseKPConv",
}

# Known incorrect DOI that should be rejected
WRONG_DOIS = [
    "10.1016/j.isprsjprs.2022.11.013",  # Belongs to a different paper
]
