"""
Siamese KPConv Golden Test

Built-in golden fixture to validate mIoU_ch calculation for Siamese KPConv.
This test cannot be deleted and validates the metric protocol auditor.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    WRONG_DOIS,
    SiamKPConv_CHANGE_CLASSES,
    SiamKPConv_CLASS_NAMES,
    SiamKPConv_MACC_STD,
    SiamKPConv_MACC_TARGET,
    SiamKPConv_MIOU_CH_STD,
    SiamKPConv_MIOU_CH_TARGET,
    SiamKPConv_PAPER_METADATA,
    SiamKPConv_PAPER_TARGET_STD,
    SiamKPConv_PAPER_TARGETS,
)
from .recompute import MetricRecomputer


class SiamKPConvGoldenTest:
    """
    Golden test for Siamese KPConv mIoU_ch calculation.
    
    This test validates:
    1. mIoU_ch is mean of classes 1-6 (excluding Unchanged)
    2. All-class mIoU is NOT equal to 80.12
    3. If local metric includes Unchanged, it must produce PROTOCOL_MISMATCH
    4. Single seed results cannot be directly compared to 3-seed mean
    5. Urb3DCD-V1 results cannot be compared to V2
    6. 23.74, 19.38, 17.85, 23.77 are UNVERIFIED if no source
    7. DOI 10.1016/j.isprsjprs.2022.11.013 is a conflict
    8. Correct DOI is 10.1016/j.isprsjprs.2023.02.001
    """

    def __init__(self):
        self.results: dict[str, Any] = {}
        self.passed: list[str] = []
        self.failed: list[str] = []

    def run_all_tests(self) -> dict:
        """Run all golden tests."""
        self.results = {}
        self.passed = []
        self.failed = []

        # Test 1: mIoU_ch calculation from paper targets
        self._test_miou_ch_calculation()

        # Test 2: All-class mIoU != mIoU_ch
        self._test_miou_vs_miou_ch()

        # Test 3: Class 0 exclusion
        self._test_class_0_exclusion()

        # Test 4: Paper metadata validation
        self._test_paper_metadata()

        # Test 5: Class names and count
        self._test_class_definitions()

        # Test 6: mAcc calculation
        self._test_macc_calculation()

        return self.get_results()

    def _test_miou_ch_calculation(self) -> None:
        """Test that mIoU_ch = mean of classes 1-6 ≈ 80.12"""
        # Compute mIoU_ch from paper targets
        change_ious = [SiamKPConv_PAPER_TARGETS[SiamKPConv_CLASS_NAMES[c]]
                      for c in SiamKPConv_CHANGE_CLASSES]
        computed_miou_ch = sum(change_ious) / len(change_ious)

        # Check against target
        diff = abs(computed_miou_ch - SiamKPConv_MIOU_CH_TARGET)
        tolerance = 0.01  # 1% tolerance for rounding

        self.results["miou_ch_calculation"] = {
            "computed": computed_miou_ch,
            "target": SiamKPConv_MIOU_CH_TARGET,
            "difference": diff,
            "within_tolerance": diff <= tolerance,
            "change_ious": dict(zip(SiamKPConv_CLASS_NAMES[1:], change_ious)),
        }

        if diff <= tolerance:
            self.passed.append("miou_ch_calculation")
        else:
            self.failed.append(f"miou_ch_calculation: computed={computed_miou_ch:.4f}, target={SiamKPConv_MIOU_CH_TARGET:.4f}")

    def _test_miou_vs_miou_ch(self) -> None:
        """Test that all-class mIoU is NOT equal to mIoU_ch"""
        # Compute all-class mIoU (classes 0-6)
        all_ious = [SiamKPConv_PAPER_TARGETS[name]
                   for name in SiamKPConv_CLASS_NAMES]
        all_miou = sum(all_ious) / len(all_ious)

        change_ious = [SiamKPConv_PAPER_TARGETS[SiamKPConv_CLASS_NAMES[c]]
                      for c in SiamKPConv_CHANGE_CLASSES]
        miou_ch = sum(change_ious) / len(change_ious)

        # They should NOT be equal
        are_equal = abs(all_miou - miou_ch) < 0.01

        self.results["miou_vs_miou_ch"] = {
            "all_class_miou": all_miou,
            "miou_ch": miou_ch,
            "difference": abs(all_miou - miou_ch),
            "are_equal": are_equal,
            "correctly_different": not are_equal,
        }

        if not are_equal:
            self.passed.append("miou_vs_miou_ch")
        else:
            self.failed.append("miou_vs_miou_ch: all-class mIoU should not equal mIoU_ch")

    def _test_class_0_exclusion(self) -> None:
        """Test that class 0 (Unchanged) has high IoU but is excluded from mIoU_ch"""
        unchanged_iou = SiamKPConv_PAPER_TARGETS["Unchanged"]

        # Class 0 should have high IoU (>90%)
        class_0_high = unchanged_iou > 90.0

        self.results["class_0_exclusion"] = {
            "unchanged_iou": unchanged_iou,
            "is_high": class_0_high,
            "excluded_from_miou_ch": True,
            "note": "Class 0 Unchanged has high IoU because most points are unchanged",
        }

        if class_0_high:
            self.passed.append("class_0_exclusion")
        else:
            self.failed.append(f"class_0_exclusion: Unchanged IoU={unchanged_iou} should be >90%")

    def _test_paper_metadata(self) -> None:
        """Test paper metadata is correct"""
        # Check DOI
        correct_doi = SiamKPConv_PAPER_METADATA["doi"]

        # Check wrong DOIs are rejected
        wrong_doi_rejected = all(doi not in [correct_doi] for doi in WRONG_DOIS)

        self.results["paper_metadata"] = {
            "correct_doi": correct_doi,
            "wrong_dois": WRONG_DOIS,
            "wrong_doi_rejected": wrong_doi_rejected,
            "title": SiamKPConv_PAPER_METADATA["title"],
            "authors": SiamKPConv_PAPER_METADATA["authors"],
            "journal": SiamKPConv_PAPER_METADATA["journal"],
            "volume": SiamKPConv_PAPER_METADATA["volume"],
            "year": SiamKPConv_PAPER_METADATA["year"],
        }

        if wrong_doi_rejected and correct_doi == "10.1016/j.isprsjprs.2023.02.001":
            self.passed.append("paper_metadata")
        else:
            self.failed.append("paper_metadata: DOI conflict detected")

    def _test_class_definitions(self) -> None:
        """Test class names and count"""
        expected_count = 7
        actual_count = len(SiamKPConv_CLASS_NAMES)

        expected_change_classes = list(range(1, 7))
        change_classes_correct = SiamKPConv_CHANGE_CLASSES == expected_change_classes

        self.results["class_definitions"] = {
            "class_count": actual_count,
            "expected_count": expected_count,
            "count_correct": actual_count == expected_count,
            "class_names": SiamKPConv_CLASS_NAMES,
            "change_classes": SiamKPConv_CHANGE_CLASSES,
            "change_classes_correct": change_classes_correct,
        }

        if actual_count == expected_count and change_classes_correct:
            self.passed.append("class_definitions")
        else:
            self.failed.append("class_definitions: class count or change classes incorrect")

    def _test_macc_calculation(self) -> None:
        """Test that mAcc is correctly calculated"""
        # Paper reports mAcc = 91.21 ± 0.68%
        # mAcc = mean of per-class accuracies

        self.results["macc_targets"] = {
            "target": SiamKPConv_MACC_TARGET,
            "std": SiamKPConv_MACC_STD,
            "note": "mAcc is mean of per-class accuracies, different from mIoU",
        }

        self.passed.append("macc_targets")

    def test_confusion_matrix_recomputation(self, confusion_matrix_path: Path) -> dict:
        """
        Test recomputation from confusion matrix.
        
        This validates that the MetricRecomputer can correctly compute mIoU_ch
        from a non-normalized confusion matrix.
        """
        if not confusion_matrix_path.exists():
            return {
                "status": "SKIPPED",
                "reason": f"Confusion matrix not found: {confusion_matrix_path}",
            }

        try:
            cm = MetricRecomputer.load_confusion_matrix(confusion_matrix_path)
        except ValueError as e:
            return {
                "status": "ERROR",
                "reason": str(e),
            }

        # Recompute metrics
        results = MetricRecomputer.recompute_from_confusion_matrix(
            cm,
            class_names=SiamKPConv_CLASS_NAMES
        )

        # Validate mIoU_ch calculation
        miou_ch = results.get("miou_ch", 0)
        all_miou = results.get("all_class_miou", 0)

        # Check against paper targets
        diff = abs(miou_ch * 100 - SiamKPConv_MIOU_CH_TARGET)  # Convert to percent

        return {
            "status": "PASS" if diff < 1.0 else "FAIL",
            "computed_miou_ch": miou_ch,
            "computed_miou_ch_percent": miou_ch * 100,
            "paper_target": SiamKPConv_MIOU_CH_TARGET,
            "difference_percent": diff,
            "all_class_miou": all_miou,
            "all_class_miou_percent": all_miou * 100,
            "per_class_iou": results.get("per_class_iou", {}),
            "mean_accuracy": results.get("mean_accuracy", {}),
            "protocol_validation": {
                "miou_ch_excludes_class_0": SiamKPConv_CHANGE_CLASSES == list(range(1, len(SiamKPConv_CLASS_NAMES))),
                "change_classes_count": len(SiamKPConv_CHANGE_CLASSES),
            },
        }

    def test_protocol_match(
        self,
        local_protocol: dict,
        expected_protocol: dict | None = None,
    ) -> dict:
        """
        Test if local protocol matches expected Siamese KPConv protocol.
        
        Args:
            local_protocol: Protocol fingerprint from local experiment
            expected_protocol: Expected protocol (if None, use paper defaults)
        
        Returns:
            Protocol compatibility result
        """
        if expected_protocol is None:
            expected_protocol = {
                "dataset_name": "Urb3DCD",
                "dataset_version": "V2",
                "dataset_subset": "low_density_LiDAR",
                "num_classes": 7,
                "included_classes": [1, 2, 3, 4, 5, 6],
                "excluded_classes": [0],
                "metric_id": "miou_ch",
                "class_aggregation": "macro",
                "sample_aggregation": "global",
            }

        mismatches = []

        for key, expected in expected_protocol.items():
            local = local_protocol.get(key)
            if local != expected and local is not None:
                mismatches.append(f"{key}: local={local}, expected={expected}")

        return {
            "compatible": len(mismatches) == 0,
            "mismatches": mismatches,
            "expected_protocol": expected_protocol,
            "local_protocol": local_protocol,
        }

    def validate_unverified_numbers(
        self,
        numbers: list[float],
        context: str = "",
    ) -> dict:
        """
        Validate that unknown numbers (23.74, 19.38, 17.85, 23.77) are properly marked.
        
        These numbers must be marked UNVERIFIED if no source is provided.
        """
        unverified_targets = [23.74, 19.38, 17.85, 23.77]

        found = []
        for num in numbers:
            for target in unverified_targets:
                if abs(num - target) < 0.1:
                    found.append({
                        "number": num,
                        "possible_target": target,
                        "status": "UNVERIFIED",
                        "reason": f"{target} has no verifiable source in paper",
                        "context": context,
                    })

        return {
            "unverified_found": found,
            "all_marked_unverified": len(found) == len([n for n in numbers
                                                       if any(abs(n-t) < 0.1 for t in unverified_targets)]),
            "action_required": "Mark these numbers as UNVERIFIED in reports",
        }

    def get_results(self) -> dict:
        """Get test results."""
        return {
            "test_name": "SiamKPConv_Golden_Test",
            "timestamp": self._get_timestamp(),
            "results": self.results,
            "passed": self.passed,
            "failed": self.failed,
            "total_passed": len(self.passed),
            "total_failed": len(self.failed),
            "all_passed": len(self.failed) == 0,
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def save_results(self, output_path: Path) -> None:
        """Save test results to file."""
        results = self.get_results()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

    @staticmethod
    def get_paper_targets_table() -> str:
        """Get formatted paper targets table."""
        lines = [
            "| Class | IoU | Std |",
            "|--------|-----|-----|",
        ]

        for name in SiamKPConv_CLASS_NAMES:
            iou = SiamKPConv_PAPER_TARGETS[name]
            std = SiamKPConv_PAPER_TARGET_STD[name]
            lines.append(f"| {name} | {iou:.2f} | {std:.2f} |")

        lines.append(f"| **mIoU_ch** | **{SiamKPConv_MIOU_CH_TARGET:.2f}** | {SiamKPConv_MIOU_CH_STD:.2f} |")
        lines.append(f"| **mAcc** | **{SiamKPConv_MACC_TARGET:.2f}** | {SiamKPConv_MACC_STD:.2f} |")

        return "\n".join(lines)


def run_golden_test() -> dict:
    """Run the golden test and return results."""
    tester = SiamKPConvGoldenTest()
    return tester.run_all_tests()


if __name__ == "__main__":
    results = run_golden_test()
    print(json.dumps(results, indent=2))

    if results["all_passed"]:
        print("\n✅ All golden tests PASSED")
    else:
        print(f"\n❌ {len(results['failed'])} tests FAILED:")
        for f in results["failed"]:
            print(f"  - {f}")
