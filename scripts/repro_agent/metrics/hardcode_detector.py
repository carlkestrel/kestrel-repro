"""
Hardcode Detection Module

Scans code and documents for hardcoded metrics, stubs, and simulated data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


class HardcodeDetector:
    """Detects hardcoded metrics, stubs, and simulated data."""

    # Patterns for suspicious code
    SUSPICIOUS_PATTERNS = {
        "random": [
            r"np\.random",
            r"torch\.rand",
            r"torch\.randn",
            r"random\.random",
            r"np\.zeros",
            r"np\.ones",
            r"np\.empty",
        ],
        "mock_stub": [
            r"class\s+\w+Mock",
            r"class\s+\w+Stub",
            r"class\s+\w+Dummy",
            r"class\s+\w+Fake",
            r"@mock\.patch",
            r"@pytest\.fixture",
            r"def\s+mock_",
            r"def\s+stub_",
            r"def\s+dummy_",
        ],
        "simulate": [
            r"simulate",
            r"fake_",
            r"generate_",
            r"synthetic_",
        ],
        "hardcoded_metric": [
            r"mIoU[:\s]*=[:\s]*\d+\.\d+",
            r"mAcc[:\s]*=[:\s]*\d+\.\d+",
            r"IoU[:\s]*=[:\s]*\d+\.\d+",
            r"accuracy[:\s]*=[:\s]*\d+\.\d+",
            r"precision[:\s]*=[:\s]*\d+\.\d+",
            r"recall[:\s]*=[:\s]*\d+\.\d+",
            r"f1[:\s]*=[:\s]*\d+\.\d+",
        ],
    }

    # Paper target values that should NOT appear in experiment code
    PAPER_TARGET_PATTERNS = [
        (80.12, "mIoU_ch"),
        (91.21, "mAcc"),
        (95.82, "Unchanged IoU"),
        (86.67, "New building IoU"),
        (78.66, "Demolition IoU"),
        (93.16, "New vegetation IoU"),
        (65.18, "Vegetation growth IoU"),
        (65.46, "Missing vegetation IoU"),
        (91.55, "Mobile objects IoU"),
        (23.74, "Unknown metric"),
        (19.38, "Unknown metric"),
        (17.85, "Unknown metric"),
        (23.77, "Unknown metric"),
    ]

    def __init__(self):
        self.findings: list[dict] = []

    def reset(self) -> None:
        """Reset findings."""
        self.findings = []

    def scan_file(self, file_path: Path) -> list[dict]:
        """Scan a single file for hardcoded content."""
        findings = []

        if not file_path.exists():
            return findings

        if file_path.suffix not in {
            ".py",
            ".yaml",
            ".yml",
            ".json",
            ".md",
            ".html",
            ".js",
            ".ipynb",
        }:
            return findings

        try:
            content = file_path.read_text(errors="ignore")
        except Exception:
            return findings

        # Check for suspicious patterns
        for category, patterns in self.SUSPICIOUS_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    findings.append(
                        {
                            "file": str(file_path),
                            "category": category,
                            "pattern": pattern,
                            "match": match.group(),
                            "line": content[: match.start()].count("\n") + 1,
                        }
                    )

        # Check for paper target values
        for target_value, metric_name in self.PAPER_TARGET_PATTERNS:
            # Look for exact value or value with small tolerance
            pattern = rf"\b{target_value}\b"
            matches = re.finditer(pattern, content)
            for match in matches:
                # Exclude if it's in a comment explaining the target
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.end())
                if line_end == -1:
                    line_end = len(content)
                line = content[line_start:line_end]

                if "#" in line:
                    # Check if it's in a comment
                    comment_start = line.find("#")
                    if comment_start < match.start() - line_start:
                        continue  # In comment, might be documentation

                findings.append(
                    {
                        "file": str(file_path),
                        "category": "paper_target",
                        "pattern": pattern,
                        "match": f"{target_value}",
                        "metric_name": metric_name,
                        "line": content[: match.start()].count("\n") + 1,
                    }
                )

        # Check for normalized confusion matrix patterns
        if "confusion" in file_path.name.lower() or "cm" in file_path.name.lower():
            # Look for patterns suggesting normalized values
            normalized_patterns = [
                r"normalize.*true",
                r"normalize.*prop.*true",
                r"cm\s*/\s*cm\.sum",
                r"cm\s*/\s*cm\.max",
            ]

            for pattern in normalized_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    findings.append(
                        {
                            "file": str(file_path),
                            "category": "normalized_confusion",
                            "pattern": pattern,
                            "match": match.group(),
                            "line": content[: match.start()].count("\n") + 1,
                        }
                    )

        return findings

    def scan_directory(self, root: Path, exclude_dirs: list[str] | None = None) -> list[dict]:
        """Scan entire directory for hardcoded content."""
        exclude_dirs = exclude_dirs or [
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".tox",
            "build",
            "dist",
            "*.egg-info",
        ]

        findings = []

        for file_path in root.rglob("*"):
            if file_path.is_file():
                # Check if should exclude
                should_exclude = False
                for excl in exclude_dirs:
                    if excl.startswith("*"):
                        if file_path.name.endswith(excl[1:]):
                            should_exclude = True
                            break
                    elif excl in file_path.parts:
                        should_exclude = True
                        break

                if not should_exclude:
                    findings.extend(self.scan_file(file_path))

        self.findings = findings
        return findings

    def check_stub_data_loader(self, code: str) -> bool:
        """Check if data loader returns stub/simulated data."""
        stub_patterns = [
            r"return.*random",
            r"return.*zeros",
            r"return.*ones",
            r"yield.*random",
            r"yield.*zeros",
        ]

        for pattern in stub_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False

    def check_hardcoded_predictions(self, code: str) -> bool:
        """Check if predictions are hardcoded."""
        hardcoded_patterns = [
            r"predictions?\s*=\s*\[",
            r"y_pred\s*=\s*\[[^\]]+\]",  # y_pred = [...]
            r"pred\s*=\s*np\.array\(\[[^\]]+\]\)",
        ]

        for pattern in hardcoded_patterns:
            if re.search(pattern, code):
                return True
        return False

    def check_metric_calculation_exists(self, code: str) -> bool:
        """Check if actual metric calculation code exists."""
        metric_patterns = [
            r"confusion_matrix",
            r"np\.bincount",
            r"IoU",
            r"intersection",
            r"union",
            r"tp\s*=\s*",
            r"fp\s*=\s*",
            r"fn\s*=\s*",
        ]

        for pattern in metric_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False

    def generate_report(self) -> dict:
        """Generate a hardcode detection report."""
        report = {
            "total_findings": len(self.findings),
            "findings_by_category": {},
            "files_with_findings": [],
            "errors": [],
            "warnings": [],
        }

        for finding in self.findings:
            cat = finding["category"]
            if cat not in report["findings_by_category"]:
                report["findings_by_category"][cat] = 0
            report["findings_by_category"][cat] += 1

            if finding["file"] not in report["files_with_findings"]:
                report["files_with_findings"].append(finding["file"])

            if cat == "paper_target":
                report["errors"].append(
                    f"Paper target {finding.get('metric_name', 'unknown')}={finding['match']} "
                    f"found in {finding['file']} line {finding['line']}"
                )
            elif cat in ("random", "mock_stub", "simulate"):
                report["warnings"].append(
                    f"{cat.title()} pattern in {finding['file']} line {finding['line']}"
                )

        return report

    def save_report(self, output_path: Path) -> None:
        """Save hardcode detection report."""
        report = self.generate_report()
        report["findings"] = self.findings
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
