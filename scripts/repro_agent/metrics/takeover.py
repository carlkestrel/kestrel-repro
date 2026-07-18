"""
Project Takeover Module

Scans existing projects and builds metric registry from available evidence.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .models import (
    WRONG_DOIS,
)


class TakeoverScanner:
    """
    Scans existing projects for metric evidence.
    
    Performs read-only scan of:
    - README
    - Paper metadata
    - Configs
    - Training logs
    - Evaluation logs
    - Checkpoints
    - Confusion matrices
    - Prediction files
    - Reports
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.evidence: dict[str, Any] = {}
        self.scanned_files: list[str] = []
        self.findings: list[dict] = []

    def scan_all(self) -> dict:
        """Perform full takeover scan."""
        self.evidence = {}
        self.scanned_files = []
        self.findings = []

        # Scan in order of importance
        self._scan_readme()
        self._scan_paper_metadata()
        self._scan_configs()
        self._scan_training_logs()
        self._scan_eval_logs()
        self._scan_checkpoints()
        self._scan_confusion_matrices()
        self._scan_predictions()
        self._scan_reports()
        self._scan_git_diff()

        return self._build_takeover_report()

    def _scan_readme(self) -> None:
        """Scan README for paper info."""
        for name in ["README.md", "README", "readme.md"]:
            path = self.project_root / name
            if path.exists():
                self.scanned_files.append(str(path))
                content = path.read_text(errors="ignore")

                # Check for DOI
                doi_pattern = r"10\.\d{4,}/[^\s]+"
                dois = re.findall(doi_pattern, content)

                for doi in dois:
                    is_wrong = doi in WRONG_DOIS
                    self.findings.append({
                        "type": "DOI",
                        "value": doi,
                        "file": str(path),
                        "is_wrong": is_wrong,
                    })

                # Check for paper title
                for key in ["title", "Title", "TITLE"]:
                    if key in content:
                        # Extract title
                        title_match = re.search(r"#\s+(.+)", content)
                        if title_match:
                            self.evidence["paper_title"] = title_match.group(1)

                break

    def _scan_paper_metadata(self) -> None:
        """Scan for paper metadata files."""
        patterns = [
            "PAPER_INFO.md",
            "paper_info.yaml",
            "paper_info.json",
            ".paper_info",
            "metadata.yaml",
        ]

        for pattern in patterns:
            path = self.project_root / pattern
            if path.exists():
                self.scanned_files.append(str(path))

                if path.suffix == ".yaml":
                    import yaml
                    with open(path) as f:
                        data = yaml.safe_load(f)
                elif path.suffix == ".json":
                    with open(path) as f:
                        data = json.load(f)
                else:
                    continue

                self.evidence["paper_metadata"] = data

                # Validate DOI
                doi = data.get("doi") or data.get("DOI")
                if doi:
                    self.findings.append({
                        "type": "DOI",
                        "value": doi,
                        "file": str(path),
                        "is_wrong": doi in WRONG_DOIS,
                    })

    def _scan_configs(self) -> None:
        """Scan config files for metric definitions."""
        config_paths = [
            self.project_root / "configs",
            self.project_root / "config",
            self.project_root / ".repro",
        ]

        for config_dir in config_paths:
            if not config_dir.exists():
                continue

            for path in config_dir.rglob("*"):
                if path.suffix in {".yaml", ".yml", ".json"}:
                    self.scanned_files.append(str(path))

                    try:
                        if path.suffix in {".yaml", ".yml"}:
                            import yaml
                            with open(path) as f:
                                data = yaml.safe_load(f)
                        else:
                            with open(path) as f:
                                data = json.load(f)

                        # Look for metric-related keys
                        if isinstance(data, dict):
                            metric_keys = [
                                "metric", "metrics", "evaluation", "eval",
                                "miou", "mIoU", "accuracy", "IoU",
                            ]

                            for key in metric_keys:
                                if key in data:
                                    self.findings.append({
                                        "type": "CONFIG_METRIC",
                                        "key": key,
                                        "value": data[key],
                                        "file": str(path),
                                    })
                    except Exception:
                        pass

    def _scan_training_logs(self) -> None:
        """Scan training logs for metrics."""
        log_patterns = [
            "**/train*.log",
            "**/train*.txt",
            "**/output/**/*.log",
            "**/logs/**/*.log",
        ]

        for pattern in log_patterns:
            for path in self.project_root.glob(pattern):
                if path.is_file():
                    self.scanned_files.append(str(path))

                    try:
                        content = path.read_text(errors="ignore")

                        # Look for metric patterns
                        metric_pattern = r"(mIoU|mIoU_ch|mAcc|IoU|accuracy|precision|recall|F1)[:\s=]+([0-9.]+)"
                        matches = re.findall(metric_pattern, content)

                        for metric_name, value in matches:
                            self.findings.append({
                                "type": "TRAIN_LOG_METRIC",
                                "metric": metric_name,
                                "value": float(value),
                                "file": str(path),
                            })
                    except Exception:
                        pass

    def _scan_eval_logs(self) -> None:
        """Scan evaluation logs."""
        eval_patterns = [
            "**/eval*.log",
            "**/evaluate*.log",
            "**/test*.log",
        ]

        for pattern in eval_patterns:
            for path in self.project_root.glob(pattern):
                if path.is_file():
                    self.scanned_files.append(str(path))
                    # Similar to training logs
                    try:
                        content = path.read_text(errors="ignore")
                        metric_pattern = r"(mIoU|mIoU_ch|mAcc|IoU|accuracy)[:\s=]+([0-9.]+)"
                        matches = re.findall(metric_pattern, content)

                        for metric_name, value in matches:
                            self.findings.append({
                                "type": "EVAL_LOG_METRIC",
                                "metric": metric_name,
                                "value": float(value),
                                "file": str(path),
                            })
                    except Exception:
                        pass

    def _scan_checkpoints(self) -> None:
        """Scan for checkpoint files."""
        checkpoint_paths = [
            self.project_root / "checkpoints",
            self.project_root / "outputs" / "checkpoints",
            self.project_root / "artifacts" / "checkpoints",
        ]

        for checkpoint_dir in checkpoint_paths:
            if not checkpoint_dir.exists():
                continue

            for path in checkpoint_dir.rglob("*"):
                if path.suffix in {".pth", ".pt", ".ckpt"}:
                    self.findings.append({
                        "type": "CHECKPOINT",
                        "path": str(path),
                        "size_mb": path.stat().st_size / (1024 * 1024),
                        "modified": path.stat().st_mtime,
                    })

    def _scan_confusion_matrices(self) -> None:
        """Scan for confusion matrix files."""
        cm_patterns = [
            "**/confusion*.npy",
            "**/confusion*.csv",
            "**/confusion*.json",
            "**/confmat*.npy",
            "**/metrics*.csv",
        ]

        for pattern in cm_patterns:
            for path in self.project_root.glob(pattern):
                if path.is_file():
                    self.scanned_files.append(str(path))
                    self.findings.append({
                        "type": "CONFUSION_MATRIX",
                        "path": str(path),
                        "size_bytes": path.stat().st_size,
                    })

    def _scan_predictions(self) -> None:
        """Scan for prediction files."""
        pred_patterns = [
            "**/*.ply",
            "**/predictions/**/*.npy",
            "**/predictions/**/*.npz",
        ]

        for pattern in pred_patterns:
            for path in self.project_root.glob(pattern):
                if path.is_file():
                    self.findings.append({
                        "type": "PREDICTION",
                        "path": str(path),
                        "size_mb": path.stat().st_size / (1024 * 1024),
                    })

    def _scan_reports(self) -> None:
        """Scan for existing reports."""
        report_patterns = [
            "**/report*.md",
            "**/REPORT*.md",
            "**/results*.md",
            "**/*.html",
        ]

        for pattern in report_patterns:
            for path in self.project_root.glob(pattern):
                if path.is_file():
                    self.scanned_files.append(str(path))
                    self.findings.append({
                        "type": "REPORT",
                        "path": str(path),
                        "size_kb": path.stat().st_size / 1024,
                    })

    def _scan_git_diff(self) -> None:
        """Scan git diff for code changes."""
        try:
            result = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                self.evidence["git_diff"] = result.stdout
        except Exception:
            pass

        # Get current commit
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                self.evidence["git_commit"] = result.stdout.strip()
        except Exception:
            pass

    def _build_takeover_report(self) -> dict:
        """Build the takeover report."""
        # Group findings by type
        findings_by_type: dict[str, list] = {}
        for finding in self.findings:
            ftype = finding["type"]
            if ftype not in findings_by_type:
                findings_by_type[ftype] = []
            findings_by_type[ftype].append(finding)

        return {
            "project_root": str(self.project_root),
            "scanned_files": self.scanned_files,
            "findings": self.findings,
            "findings_by_type": findings_by_type,
            "evidence": self.evidence,
            "num_files_scanned": len(self.scanned_files),
            "num_findings": len(self.findings),
        }


def takeover_project(project_root: Path) -> dict:
    """Perform full project takeover."""
    scanner = TakeoverScanner(project_root)
    return scanner.scan_all()
