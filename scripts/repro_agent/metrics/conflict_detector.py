"""
Conflict Detection Module

Detects conflicts between metric definitions, observations, and sources.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import (
    ConflictType,
    MetricConflict,
    MetricObservation,
)


class ConflictDetector:
    """Detects conflicts in metric definitions and observations."""

    def __init__(self):
        self.conflicts: list[MetricConflict] = []

    def reset(self) -> None:
        """Reset conflict list."""
        self.conflicts = []

    def add_conflict(
        self,
        conflict_type: ConflictType,
        description: str,
        involved_observations: list[str] | None = None,
        involved_sources: list[str] | None = None,
        severity: str = "ERROR",
    ) -> MetricConflict:
        """Add a new conflict."""
        conflict = MetricConflict(
            conflict_id=f"conflict_{len(self.conflicts)}",
            conflict_type=conflict_type,
            description=description,
            involved_observations=involved_observations,
            involved_sources=involved_sources,
            severity=severity,
        )
        self.conflicts.append(conflict)
        return conflict

    def detect_same_value_different_names(
        self,
        observations: dict[str, MetricObservation],
    ) -> None:
        """Detect when same value appears under different names."""
        value_map: dict[float, list[str]] = {}

        for obs_id, obs in observations.items():
            if obs.value is not None:
                # Round to 4 decimal places for comparison
                key = round(obs.value, 4)
                if key not in value_map:
                    value_map[key] = []
                value_map[key].append(obs_id)

        for value, obs_ids in value_map.items():
            if len(obs_ids) > 1:
                metric_ids = [observations[oid].metric_id for oid in obs_ids]
                unique_metrics = set(metric_ids)
                if len(unique_metrics) > 1:
                    self.add_conflict(
                        ConflictType.SAME_VALUE_DIFFERENT_NAMES,
                        f"Value {value} appears under different names: {unique_metrics}",
                        involved_observations=obs_ids,
                        severity="WARNING",
                    )

    def detect_same_name_different_formula(
        self,
        observations: dict[str, MetricObservation],
        metric_definitions: dict[str, dict],
    ) -> None:
        """Detect when same name has different formulas."""
        # Group by metric_id
        metric_formulas: dict[str, list[tuple[str, str]]] = {}

        for obs_id, obs in observations.items():
            if obs.metric_id in metric_definitions:
                formula = metric_definitions[obs.metric_id].get("formula", "")
                if obs.metric_id not in metric_formulas:
                    metric_formulas[obs.metric_id] = []
                metric_formulas[obs.metric_id].append((obs_id, formula))

        for metric_id, obs_formulas in metric_formulas.items():
            unique_formulas = set(f for _, f in obs_formulas)
            if len(unique_formulas) > 1:
                self.add_conflict(
                    ConflictType.SAME_NAME_DIFFERENT_FORMULA,
                    f"Metric {metric_id} has different formulas: {unique_formulas}",
                    severity="ERROR",
                )

    def detect_report_inconsistent_with_raw(
        self,
        report_metrics: dict[str, float],
        raw_metrics: dict[str, float],
        tolerance: float = 0.001,
    ) -> None:
        """Detect when report values don't match raw metrics."""
        for metric_name, report_value in report_metrics.items():
            if metric_name in raw_metrics:
                raw_value = raw_metrics[metric_name]
                if abs(report_value - raw_value) > tolerance:
                    self.add_conflict(
                        ConflictType.REPORT_INCONSISTENT_WITH_RAW,
                        f"{metric_name}: report={report_value}, raw={raw_value}, diff={abs(report_value - raw_value)}",
                        severity="ERROR",
                    )

    def detect_csv_inconsistent_with_logs(
        self,
        csv_metrics: dict[str, float],
        log_metrics: dict[str, float],
        tolerance: float = 0.001,
    ) -> None:
        """Detect when CSV values don't match log values."""
        for metric_name, csv_value in csv_metrics.items():
            if metric_name in log_metrics:
                log_value = log_metrics[metric_name]
                if abs(csv_value - log_value) > tolerance:
                    self.add_conflict(
                        ConflictType.CSV_INCONSISTENT_WITH_LOGS,
                        f"{metric_name}: csv={csv_value}, log={log_value}",
                        severity="WARNING",
                    )

    def detect_checkpoint_mismatch(
        self,
        checkpoint_name: str,
        reported_epoch: int | None,
        actual_epoch: int | None,
    ) -> None:
        """Detect checkpoint filename vs epoch mismatch."""
        if reported_epoch is not None and actual_epoch is not None:
            if reported_epoch != actual_epoch:
                self.add_conflict(
                    ConflictType.CHECKPOINT_MISMATCH,
                    f"Checkpoint {checkpoint_name}: reported epoch={reported_epoch}, actual epoch={actual_epoch}",
                    severity="ERROR",
                )

    def detect_unit_confusion(
        self,
        value1: float,
        value2: float,
        tolerance_factor: float = 100.0,
    ) -> bool:
        """Detect if values might be confused percent vs fraction."""
        # Values that differ by ~100x might be percent vs fraction
        if value1 > 1.0 and value2 < 1.0:
            if abs(value1 - value2 * 100) < tolerance_factor:
                self.add_conflict(
                    ConflictType.UNIT_CONFUSION,
                    f"Possible unit confusion: {value1} vs {value2} (might be percent vs fraction)",
                    severity="WARNING",
                )
                return True
        return False

    def detect_miou_vs_miou_ch(
        self,
        miou_value: float | None,
        miou_ch_value: float | None,
        class_0_iou: float | None = None,
    ) -> None:
        """
        Detect mIoU vs mIoU_ch confusion.

        mIoU_ch should be mean of classes 1-6 (excluding Unchanged/class 0).
        """
        if miou_value is not None and miou_ch_value is not None:
            # If class 0 has high IoU (as expected for Unchanged),
            # then mIoU_ch < mIoU
            if class_0_iou is not None and class_0_iou > 0.9:
                if miou_ch_value > miou_value:
                    self.add_conflict(
                        ConflictType.MIOU_VS_MIOU_CH,
                        f"mIoU_ch ({miou_ch_value:.4f}) > mIoU ({miou_value:.4f}) but class 0 IoU is high ({class_0_iou:.4f}), indicating possible confusion",
                        severity="ERROR",
                    )

    def detect_validation_vs_test(
        self,
        val_metrics: dict[str, float],
        test_metrics: dict[str, float],
    ) -> None:
        """Detect validation vs test metric confusion."""
        # This is a warning when the same metric is used in both contexts
        common_metrics = set(val_metrics.keys()) & set(test_metrics.keys())
        for metric in common_metrics:
            val_val = val_metrics[metric]
            test_val = test_metrics[metric]
            if abs(val_val - test_val) < 0.001:
                self.add_conflict(
                    ConflictType.VALIDATION_VS_TEST,
                    f"Metric {metric} has identical value in val and test: {val_val} - possible confusion",
                    severity="WARNING",
                )

    def detect_single_vs_multi_seed(
        self,
        observations: dict[str, MetricObservation],
        expected_seeds: int = 3,
    ) -> None:
        """Detect single seed vs multi-seed aggregation confusion."""
        # Group by metric_id and protocol
        run_counts: dict[str, int] = {}

        for obs in observations.values():
            key = f"{obs.metric_id}_{obs.protocol_fingerprint}"
            if obs.run_id:
                if key not in run_counts:
                    run_counts[key] = 0
                run_counts[key] += 1

        for key, count in run_counts.items():
            if count == 1 and expected_seeds > 1:
                self.add_conflict(
                    ConflictType.SINGLE_VS_MULTI_SEED,
                    f"Single run observed for {key}, expected {expected_seeds} runs for statistical validity",
                    severity="WARNING",
                )

    def detect_hardcoded_in_plotting(
        self,
        plotting_code: str,
        paper_values: dict[str, float],
    ) -> list[str]:
        """Detect hardcoded paper values in plotting scripts."""
        issues = []

        for metric_name, value in paper_values.items():
            # Check for exact match or near-match
            patterns = [
                rf"\b{value}\b",  # Exact
                rf"= *{value}",  # Assignment
                rf"\[{value}\]",  # In array
            ]

            for pattern in patterns:
                if re.search(pattern, plotting_code):
                    issues.append(
                        f"Hardcoded value {value} for {metric_name} found in plotting code"
                    )
                    self.add_conflict(
                        ConflictType.HARDCODED_IN_PLOTTING,
                        f"Paper target {metric_name}={value} appears in plotting code",
                        severity="ERROR",
                    )
                    break

        return issues

    def detect_image_without_data(
        self,
        image_path: Path,
        expected_data_files: list[Path],
    ) -> None:
        """Detect when chart image exists but source data is missing."""
        if not image_path.exists():
            return

        missing_data = [f for f in expected_data_files if not f.exists()]

        if missing_data:
            self.add_conflict(
                ConflictType.IMAGE_WITHOUT_DATA,
                f"Chart image {image_path.name} exists but source data files are missing: {missing_data}",
                severity="WARNING",
            )

    def detect_stale_run(
        self,
        run_timestamp: str,
        current_timestamp: str,
        max_age_hours: int = 168,  # 1 week
    ) -> bool:
        """Detect if run is stale."""
        from datetime import datetime

        try:
            run_dt = datetime.fromisoformat(run_timestamp.replace("Z", "+00:00"))
            curr_dt = datetime.fromisoformat(current_timestamp.replace("Z", "+00:00"))

            age_hours = (curr_dt - run_dt).total_seconds() / 3600

            if age_hours > max_age_hours:
                self.add_conflict(
                    ConflictType.STALE_RUN,
                    f"Run from {run_timestamp} is {age_hours:.1f} hours old (> {max_age_hours}h)",
                    severity="INFO",
                )
                return True
        except Exception:
            pass

        return False

    def detect_data_version_conflict(
        self,
        observed_version: str,
        expected_version: str,
        context: str = "",
    ) -> None:
        """Detect V1 vs V2 or other version conflicts."""
        if observed_version != expected_version:
            self.add_conflict(
                ConflictType.DATA_VERSION_CONFLICT,
                f"Data version conflict: observed={observed_version}, expected={expected_version} {context}",
                severity="ERROR",
            )

    def detect_class_mapping_conflict(
        self,
        observed_mapping: dict[int, str],
        expected_mapping: dict[int, str],
    ) -> None:
        """Detect class mapping conflicts."""
        conflicts = []

        for cls_idx in set(observed_mapping.keys()) | set(expected_mapping.keys()):
            obs_name = observed_mapping.get(cls_idx, "<MISSING>")
            exp_name = expected_mapping.get(cls_idx, "<MISSING>")

            if obs_name != exp_name:
                conflicts.append(f"Class {cls_idx}: observed={obs_name}, expected={exp_name}")

        if conflicts:
            self.add_conflict(
                ConflictType.CLASS_MAPPING_CONFLICT,
                f"Class mapping conflicts: {'; '.join(conflicts)}",
                severity="ERROR",
            )

    def get_conflicts(self) -> list[MetricConflict]:
        """Get all detected conflicts."""
        return self.conflicts

    def has_errors(self) -> bool:
        """Check if there are any ERROR severity conflicts."""
        return any(c.severity == "ERROR" for c in self.conflicts)

    def get_error_count(self) -> int:
        """Get count of ERROR severity conflicts."""
        return sum(1 for c in self.conflicts if c.severity == "ERROR")

    def get_warning_count(self) -> int:
        """Get count of WARNING severity conflicts."""
        return sum(1 for c in self.conflicts if c.severity == "WARNING")

    def save_conflicts(self, output_path: Path) -> None:
        """Save conflicts to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump([c.to_dict() for c in self.conflicts], f, indent=2)

    def summary(self) -> dict:
        """Get conflict summary."""
        return {
            "total_conflicts": len(self.conflicts),
            "errors": self.get_error_count(),
            "warnings": self.get_warning_count(),
            "has_errors": self.has_errors(),
            "conflicts_by_type": {
                ct.value: sum(1 for c in self.conflicts if c.conflict_type == ct)
                for ct in ConflictType
            },
        }
