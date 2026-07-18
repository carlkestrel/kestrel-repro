"""
Metric Registry - Central registry for all metric definitions.
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import (
    AbsentClassPolicy,
    ClassAggregation,
    Direction,
    EvaluationScope,
    MetricConflict,
    MetricDefinition,
    MetricObservation,
    MetricProtocolFingerprint,
    MetricSource,
    PredictionLevel,
    RunManifest,
    SampleAggregation,
    TaskType,
    Unit,
)


class MetricRegistry:
    """Central registry for all metric definitions and observations."""

    def __init__(self, registry_path: Path | None = None):
        self.registry_path = registry_path or Path(".repro/metrics/metric_registry.yaml")
        self.metrics: dict[str, MetricDefinition] = {}
        self.observations: dict[str, MetricObservation] = {}
        self.sources: dict[str, MetricSource] = {}
        self.fingerprints: dict[str, MetricProtocolFingerprint] = {}
        self.conflicts: dict[str, MetricConflict] = {}
        self.runs: dict[str, RunManifest] = {}

        # Load existing registry
        if self.registry_path.exists():
            self.load()

    def register_metric(self, metric: MetricDefinition) -> None:
        """Register a metric definition."""
        self.metrics[metric.metric_id] = metric

    def add_observation(self, observation: MetricObservation) -> None:
        """Add a metric observation."""
        self.observations[observation.observation_id] = observation

    def add_source(self, source: MetricSource) -> None:
        """Add a metric source."""
        self.sources[source.source_id] = source

    def add_fingerprint(self, fingerprint: MetricProtocolFingerprint) -> str:
        """Add a protocol fingerprint and return its hash."""
        fp_hash = fingerprint.fingerprint_hash
        self.fingerprints[fp_hash] = fingerprint
        return fp_hash

    def add_conflict(self, conflict: MetricConflict) -> None:
        """Add a metric conflict."""
        self.conflicts[conflict.conflict_id] = conflict

    def add_run(self, run: RunManifest) -> None:
        """Add a run manifest."""
        self.runs[run.run_id] = run

    def get_metric(self, metric_id: str) -> MetricDefinition | None:
        """Get a metric definition by ID."""
        return self.metrics.get(metric_id)

    def get_observations_for_run(self, run_id: str) -> list[MetricObservation]:
        """Get all observations for a run."""
        return [o for o in self.observations.values() if o.run_id == run_id]

    def get_observations_for_metric(self, metric_id: str) -> list[MetricObservation]:
        """Get all observations for a metric."""
        return [o for o in self.observations.values() if o.metric_id == metric_id]

    def to_dict(self) -> dict:
        """Convert registry to dictionary."""
        return {
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "observations": {k: v.to_dict() for k, v in self.observations.items()},
            "sources": {k: v.to_dict() for k, v in self.sources.items()},
            "fingerprints": {k: v.to_dict() for k, v in self.fingerprints.items()},
            "conflicts": {k: v.to_dict() for k, v in self.conflicts.items()},
            "runs": {k: v.to_dict() for k, v in self.runs.items()},
        }

    def save(self, path: Path | None = None) -> None:
        """Save registry to file."""
        path = path or self.registry_path
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    def load(self, path: Path | None = None) -> None:
        """Load registry from file."""
        path = path or self.registry_path
        if not path.exists():
            return

        with path.open() as f:
            data = json.load(f)

        self.metrics = {
            k: MetricDefinition.from_dict(v) for k, v in data.get("metrics", {}).items()
        }
        self.observations = {
            k: MetricObservation(**v) for k, v in data.get("observations", {}).items()
        }
        self.sources = {
            k: MetricSource(**v) for k, v in data.get("sources", {}).items()
        }
        self.fingerprints = {
            k: MetricProtocolFingerprint.from_dict(v) for k, v in data.get("fingerprints", {}).items()
        }
        self.conflicts = {
            k: MetricConflict(**v) for k, v in data.get("conflicts", {}).items()
        }
        self.runs = {
            k: RunManifest(**v) for k, v in data.get("runs", {}).items()
        }

    def summary(self) -> dict:
        """Get summary of registry contents."""
        return {
            "num_metrics": len(self.metrics),
            "num_observations": len(self.observations),
            "num_sources": len(self.sources),
            "num_fingerprints": len(self.fingerprints),
            "num_conflicts": len(self.conflicts),
            "num_runs": len(self.runs),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Standard Metric Definitions
# ──────────────────────────────────────────────────────────────────────────────

def get_standard_metrics() -> dict[str, MetricDefinition]:
    """Get all standard metric definitions."""
    return {
        # Accuracy metrics
        "overall_accuracy": MetricDefinition(
            metric_id="overall_accuracy",
            canonical_name="Overall Accuracy",
            display_name="OA",
            task_type=TaskType.CLASSIFICATION,
            direction=Direction.MAXIMIZE,
            formula="(TP + TN) / (TP + TN + FP + FN)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.NONE,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        "mean_accuracy": MetricDefinition(
            metric_id="mean_accuracy",
            canonical_name="Mean Accuracy",
            display_name="mAcc",
            task_type=TaskType.CLASSIFICATION,
            direction=Direction.MAXIMIZE,
            formula="mean(per_class_accuracy)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.MACRO,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        # IoU metrics
        "per_class_iou": MetricDefinition(
            metric_id="per_class_iou",
            canonical_name="Per-Class IoU",
            display_name="IoU_c",
            task_type=TaskType.SEMANTIC_SEGMENTATION,
            direction=Direction.MAXIMIZE,
            formula="TP_c / (TP_c + FP_c + FN_c)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.NONE,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        "all_class_miou": MetricDefinition(
            metric_id="all_class_miou",
            canonical_name="All-Class Mean IoU",
            display_name="mIoU",
            task_type=TaskType.SEMANTIC_SEGMENTATION,
            direction=Direction.MAXIMIZE,
            formula="mean(IoU_c for all c)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.MACRO,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        "miou_ch": MetricDefinition(
            metric_id="miou_ch",
            canonical_name="Change-Class Mean IoU",
            display_name="mIoU_ch",
            task_type=TaskType.POINT_CLOUD_CHANGE_DETECTION,
            direction=Direction.MAXIMIZE,
            formula="mean(IoU_c for c in change_classes, excluding class 0)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.MACRO,
            sample_aggregation=SampleAggregation.GLOBAL,
            excluded_classes=[0],  # Exclude Unchanged
        ),

        "miou_no_bg": MetricDefinition(
            metric_id="miou_no_bg",
            canonical_name="Background-Excluded Mean IoU",
            display_name="mIoU_no_bg",
            task_type=TaskType.SEMANTIC_SEGMENTATION,
            direction=Direction.MAXIMIZE,
            formula="mean(IoU_c for c != background_class)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.MACRO,
            sample_aggregation=SampleAggregation.GLOBAL,
            ignored_labels=[255],  # Common ignore index
        ),

        # Binary metrics
        "binary_iou": MetricDefinition(
            metric_id="binary_iou",
            canonical_name="Binary IoU",
            display_name="IoU_binary",
            task_type=TaskType.CHANGE_DETECTION,
            direction=Direction.MAXIMIZE,
            formula="TP_binary / (TP_binary + FP_binary + FN_binary)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.NONE,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        "binary_precision": MetricDefinition(
            metric_id="binary_precision",
            canonical_name="Binary Precision",
            display_name="Prec_binary",
            task_type=TaskType.CHANGE_DETECTION,
            direction=Direction.MAXIMIZE,
            formula="TP_binary / (TP_binary + FP_binary)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.NONE,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        "binary_recall": MetricDefinition(
            metric_id="binary_recall",
            canonical_name="Binary Recall",
            display_name="Rec_binary",
            task_type=TaskType.CHANGE_DETECTION,
            direction=Direction.MAXIMIZE,
            formula="TP_binary / (TP_binary + FN_binary)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.NONE,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        "binary_f1": MetricDefinition(
            metric_id="binary_f1",
            canonical_name="Binary F1",
            display_name="F1_binary",
            task_type=TaskType.CHANGE_DETECTION,
            direction=Direction.MAXIMIZE,
            formula="2 * Prec * Rec / (Prec + Rec)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.NONE,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        # Other metrics
        "kappa": MetricDefinition(
            metric_id="kappa",
            canonical_name="Kappa Coefficient",
            display_name="Kappa",
            task_type=TaskType.CHANGE_DETECTION,
            direction=Direction.MAXIMIZE,
            formula="(p_o - p_e) / (1 - p_e)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.NONE,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),

        "weighted_miou": MetricDefinition(
            metric_id="weighted_miou",
            canonical_name="Weighted Mean IoU",
            display_name="mIoU_weighted",
            task_type=TaskType.SEMANTIC_SEGMENTATION,
            direction=Direction.MAXIMIZE,
            formula="sum(IoU_c * support_c) / sum(support_c)",
            unit=Unit.FRACTION,
            class_aggregation=ClassAggregation.WEIGHTED,
            sample_aggregation=SampleAggregation.GLOBAL,
        ),
    }


def create_miou_ch_definition(
    excluded_classes: list[int] = [0],
    included_classes: list[int] | None = None,
) -> MetricDefinition:
    """Create mIoU_ch definition for Siamese KPConv."""
    return MetricDefinition(
        metric_id="miou_ch",
        canonical_name="Change-Class Mean IoU",
        display_name="mIoU_ch",
        task_type=TaskType.POINT_CLOUD_CHANGE_DETECTION,
        direction=Direction.MAXIMIZE,
        formula="mean(IoU_c for c in [1,2,3,4,5,6], excluding class 0 Unchanged)",
        unit=Unit.FRACTION,
        class_aggregation=ClassAggregation.MACRO,
        sample_aggregation=SampleAggregation.GLOBAL,
        excluded_classes=excluded_classes,
        included_classes=included_classes or [1, 2, 3, 4, 5, 6],
        absent_class_policy=AbsentClassPolicy.ZERO,
        prediction_level=PredictionLevel.POINT,
        evaluation_scope=EvaluationScope.FULL_PC,
    )
