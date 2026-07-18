"""
Deterministic Metric Recomputation Module

This module provides deterministic metric calculation from:
- Raw predictions
- Ground truth
- Non-normalized confusion matrix
- Raw metrics CSV/JSON
- Official evaluation output
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


class MetricRecomputer:
    """Deterministic metric recomputation from raw evidence."""

    @staticmethod
    def compute_confusion_matrix(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        num_classes: int,
        ignore_index: int | None = None,
    ) -> np.ndarray:
        """
        Compute confusion matrix.
        
        Args:
            y_true: Ground truth labels
            y_pred: Predicted labels
            num_classes: Number of classes
            ignore_index: Label to ignore in computation
        
        Returns:
            Confusion matrix where rows are GT, columns are predictions
        """
        if ignore_index is not None:
            mask = (y_true != ignore_index) & (y_pred != ignore_index)
            y_true = y_true[mask]
            y_pred = y_pred[mask]

        # Use np.bincount for efficiency
        cm = np.zeros((num_classes, num_classes), dtype=np.int64)
        indices = np.ravel_multi_index(
            (y_true.astype(int), y_pred.astype(int)),
            (num_classes, num_classes)
        )
        np.add.at(cm.ravel(), indices, 1)
        return cm

    @staticmethod
    def compute_per_class_iou(
        confusion_matrix: np.ndarray,
        absent_class_policy: str = "zero",
    ) -> tuple[dict[int, float], list[int]]:
        """
        Compute per-class IoU from confusion matrix.
        
        IoU_c = TP_c / (TP_c + FP_c + FN_c)
             = cm[c, c] / (sum(cm[:, c]) + sum(cm[c, :]) - cm[c, c])
        
        Args:
            confusion_matrix: Non-normalized confusion matrix (GT rows, Pred columns)
            absent_class_policy: Policy for absent classes ("zero", "ignore", "error")
        
        Returns:
            (per_class_iou dict, absent_classes list)
        """
        num_classes = confusion_matrix.shape[0]
        per_class_iou = {}
        absent_classes = []

        for c in range(num_classes):
            tp = confusion_matrix[c, c]
            fp = confusion_matrix[:, c].sum() - tp
            fn = confusion_matrix[c, :].sum() - tp

            denominator = tp + fp + fn

            if denominator == 0:
                # Class is absent
                absent_classes.append(c)
                if absent_class_policy == "zero":
                    per_class_iou[c] = 0.0
                elif absent_class_policy == "ignore":
                    continue
                else:  # error
                    raise ValueError(f"Class {c} is absent in both GT and predictions")
            else:
                per_class_iou[c] = tp / denominator

        return per_class_iou, absent_classes

    @staticmethod
    def compute_miou(
        confusion_matrix: np.ndarray,
        included_classes: list[int] | None = None,
        excluded_classes: list[int] | None = None,
        absent_class_policy: str = "zero",
    ) -> float:
        """
        Compute mean IoU (mIoU).
        
        Args:
            confusion_matrix: Non-normalized confusion matrix
            included_classes: Classes to include in mean
            excluded_classes: Classes to exclude from mean
            absent_class_policy: Policy for absent classes
        
        Returns:
            mIoU value
        """
        per_class_iou, _ = MetricRecomputer.compute_per_class_iou(
            confusion_matrix, absent_class_policy
        )

        # Determine which classes to include
        if included_classes is not None:
            classes_to_include = [c for c in included_classes if c in per_class_iou]
        elif excluded_classes is not None:
            classes_to_include = [c for c in per_class_iou if c not in excluded_classes]
        else:
            classes_to_include = list(per_class_iou.keys())

        if not classes_to_include:
            return 0.0

        return np.mean([per_class_iou[c] for c in classes_to_include])

    @staticmethod
    def compute_miou_ch(
        confusion_matrix: np.ndarray,
        num_classes: int = 7,
    ) -> float:
        """
        Compute mIoU_ch for Siamese KPConv.
        
        mIoU_ch = mean(IoU_c for c in [1,2,3,4,5,6])
        Excludes class 0 (Unchanged).
        
        Args:
            confusion_matrix: Non-normalized confusion matrix
            num_classes: Total number of classes (default 7)
        
        Returns:
            mIoU_ch value
        """
        # Change classes are 1-6 (excluding 0 Unchanged)
        change_classes = list(range(1, num_classes))
        return MetricRecomputer.compute_miou(
            confusion_matrix,
            included_classes=change_classes,
            absent_class_policy="zero",
        )

    @staticmethod
    def compute_per_class_accuracy(
        confusion_matrix: np.ndarray,
    ) -> dict[int, float]:
        """
        Compute per-class accuracy from confusion matrix.
        
        Accuracy_c = TP_c / (TP_c + FN_c)
                   = cm[c, c] / sum(cm[c, :])
        """
        num_classes = confusion_matrix.shape[0]
        per_class_acc = {}

        for c in range(num_classes):
            total = confusion_matrix[c, :].sum()
            if total > 0:
                per_class_acc[c] = confusion_matrix[c, c] / total
            else:
                per_class_acc[c] = 0.0

        return per_class_acc

    @staticmethod
    def compute_mean_accuracy(
        confusion_matrix: np.ndarray,
        included_classes: list[int] | None = None,
    ) -> float:
        """Compute mean accuracy across classes."""
        per_class_acc = MetricRecomputer.compute_per_class_accuracy(confusion_matrix)

        if included_classes is not None:
            classes = [c for c in included_classes if c in per_class_acc]
        else:
            classes = list(per_class_acc.keys())

        if not classes:
            return 0.0

        return np.mean([per_class_acc[c] for c in classes])

    @staticmethod
    def compute_overall_accuracy(
        confusion_matrix: np.ndarray,
    ) -> float:
        """Compute overall accuracy (OA)."""
        total_correct = np.diag(confusion_matrix).sum()
        total_samples = confusion_matrix.sum()
        return total_correct / total_samples if total_samples > 0 else 0.0

    @staticmethod
    def compute_per_class_precision(
        confusion_matrix: np.ndarray,
    ) -> dict[int, float]:
        """Compute per-class precision."""
        num_classes = confusion_matrix.shape[0]
        per_class_prec = {}

        for c in range(num_classes):
            tp = confusion_matrix[c, c]
            fp = confusion_matrix[:, c].sum() - tp
            denominator = tp + fp
            per_class_prec[c] = tp / denominator if denominator > 0 else 0.0

        return per_class_prec

    @staticmethod
    def compute_per_class_recall(
        confusion_matrix: np.ndarray,
    ) -> dict[int, float]:
        """Compute per-class recall (same as per-class accuracy)."""
        return MetricRecomputer.compute_per_class_accuracy(confusion_matrix)

    @staticmethod
    def compute_per_class_f1(
        confusion_matrix: np.ndarray,
    ) -> dict[int, float]:
        """Compute per-class F1 score."""
        per_class_prec = MetricRecomputer.compute_per_class_precision(confusion_matrix)
        per_class_rec = MetricRecomputer.compute_per_class_recall(confusion_matrix)

        per_class_f1 = {}
        for c in set(per_class_prec.keys()) | set(per_class_rec.keys()):
            p = per_class_prec.get(c, 0)
            r = per_class_rec.get(c, 0)
            denominator = p + r
            per_class_f1[c] = 2 * p * r / denominator if denominator > 0 else 0.0

        return per_class_f1

    @staticmethod
    def compute_binary_change_metrics(
        confusion_matrix: np.ndarray,
        change_class_indices: list[int] | None = None,
    ) -> dict[str, float]:
        """
        Compute binary change detection metrics.
        
        Args:
            confusion_matrix: Non-normalized confusion matrix
            change_class_indices: Indices of change classes (if None, all except 0)
        
        Returns:
            Dictionary with binary IoU, Precision, Recall, F1
        """
        if change_class_indices is None:
            change_class_indices = list(range(1, confusion_matrix.shape[0]))

        num_classes = confusion_matrix.shape[0]

        # Compute binary: change (any of change classes) vs unchanged
        binary_tp = 0
        binary_fp = 0
        binary_fn = 0

        # True Positives: GT is change AND Pred is change
        for c_gt in change_class_indices:
            for c_pred in change_class_indices:
                binary_tp += confusion_matrix[c_gt, c_pred]

        # False Positives: GT is unchanged AND Pred is change
        for c_pred in change_class_indices:
            binary_fp += confusion_matrix[0, c_pred]

        # False Negatives: GT is change AND Pred is unchanged
        for c_gt in change_class_indices:
            binary_fn += confusion_matrix[c_gt, 0]

        # Compute metrics
        binary_iou = binary_tp / (binary_tp + binary_fp + binary_fn) if (binary_tp + binary_fp + binary_fn) > 0 else 0.0
        binary_prec = binary_tp / (binary_tp + binary_fp) if (binary_tp + binary_fp) > 0 else 0.0
        binary_rec = binary_tp / (binary_tp + binary_fn) if (binary_tp + binary_fn) > 0 else 0.0
        binary_f1 = 2 * binary_prec * binary_rec / (binary_prec + binary_rec) if (binary_prec + binary_rec) > 0 else 0.0

        return {
            "binary_iou": binary_iou,
            "binary_precision": binary_prec,
            "binary_recall": binary_rec,
            "binary_f1": binary_f1,
        }

    @staticmethod
    def compute_kappa(
        confusion_matrix: np.ndarray,
    ) -> float:
        """
        Compute Cohen's Kappa coefficient.
        
        Kappa = (p_o - p_e) / (1 - p_e)
        
        where p_o is observed agreement and p_e is expected agreement.
        """
        total = confusion_matrix.sum()
        if total == 0:
            return 0.0

        # Observed agreement
        p_o = np.diag(confusion_matrix).sum() / total

        # Expected agreement
        row_sums = confusion_matrix.sum(axis=1)
        col_sums = confusion_matrix.sum(axis=0)
        p_e = (row_sums * col_sums).sum() / (total * total)

        if p_e == 1.0:
            return 1.0

        return (p_o - p_e) / (1 - p_e)

    @staticmethod
    def recompute_from_confusion_matrix(
        confusion_matrix: np.ndarray,
        class_names: list[str] | None = None,
        compute_all: bool = True,
    ) -> dict[str, Any]:
        """
        Recompute all metrics from a confusion matrix.
        
        Args:
            confusion_matrix: Non-normalized confusion matrix
            class_names: Optional list of class names
            compute_all: If True, compute all metrics
        
        Returns:
            Dictionary of computed metrics
        """
        if confusion_matrix.ndim != 2 or confusion_matrix.shape[0] != confusion_matrix.shape[1]:
            raise ValueError("Confusion matrix must be square")

        num_classes = confusion_matrix.shape[0]

        if class_names is None:
            class_names = [f"class_{i}" for i in range(num_classes)]

        results = {
            "confusion_matrix": confusion_matrix.tolist(),
            "class_names": class_names,
            "num_classes": num_classes,
        }

        # Per-class IoU
        per_class_iou, absent_classes = MetricRecomputer.compute_per_class_iou(
            confusion_matrix
        )
        results["per_class_iou"] = {
            class_names[c]: float(v) for c, v in per_class_iou.items()
        }
        results["absent_classes"] = absent_classes

        # All-class mIoU (classes 0-6)
        all_miou = MetricRecomputer.compute_miou(confusion_matrix)
        results["all_class_miou"] = float(all_miou)

        # mIoU_ch (classes 1-6, excluding Unchanged)
        miou_ch = MetricRecomputer.compute_miou_ch(confusion_matrix, num_classes)
        results["miou_ch"] = float(miou_ch)

        # Per-class accuracy
        per_class_acc = MetricRecomputer.compute_per_class_accuracy(confusion_matrix)
        results["per_class_accuracy"] = {
            class_names[c]: float(v) for c, v in per_class_acc.items()
        }

        # Mean accuracy
        m_acc = MetricRecomputer.compute_mean_accuracy(confusion_matrix)
        results["mean_accuracy"] = float(m_acc)

        # Overall accuracy
        oa = MetricRecomputer.compute_overall_accuracy(confusion_matrix)
        results["overall_accuracy"] = float(oa)

        # Per-class precision
        per_class_prec = MetricRecomputer.compute_per_class_precision(confusion_matrix)
        results["per_class_precision"] = {
            class_names[c]: float(v) for c, v in per_class_prec.items()
        }

        # Per-class recall
        per_class_rec = MetricRecomputer.compute_per_class_recall(confusion_matrix)
        results["per_class_recall"] = {
            class_names[c]: float(v) for c, v in per_class_rec.items()
        }

        # Per-class F1
        per_class_f1 = MetricRecomputer.compute_per_class_f1(confusion_matrix)
        results["per_class_f1"] = {
            class_names[c]: float(v) for c, v in per_class_f1.items()
        }

        # Binary change metrics
        change_classes = list(range(1, num_classes))
        binary_metrics = MetricRecomputer.compute_binary_change_metrics(
            confusion_matrix, change_classes
        )
        results["binary_change"] = {k: float(v) for k, v in binary_metrics.items()}

        # Kappa
        kappa = MetricRecomputer.compute_kappa(confusion_matrix)
        results["kappa"] = float(kappa)

        return results

    @staticmethod
    def load_confusion_matrix(path: Path) -> np.ndarray:
        """Load confusion matrix from file."""
        if path.suffix == ".npy":
            cm = np.load(path)
        elif path.suffix == ".csv":
            cm = np.loadtxt(path, delimiter=",")
        elif path.suffix == ".json":
            with open(path) as f:
                data = json.load(f)
            cm = np.array(data)
        else:
            raise ValueError(f"Unsupported confusion matrix format: {path.suffix}")

        if cm.dtype == float and cm.max() <= 1.0:
            raise ValueError(
                f"Confusion matrix appears to be normalized (max={cm.max():.4f}). "
                "Please provide non-normalized confusion matrix."
            )

        return cm.astype(np.int64)

    @staticmethod
    def save_metrics(results: dict, output_path: Path) -> None:
        """Save recomputed metrics to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
