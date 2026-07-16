"""
Evidence Manager - Unified artifact root directory for reproducibility evidence.

This module provides:
- Canonical artifact directory structure (artifacts/runs/<run_id>/)
- Evidence tracking and verification
- Claim-to-evidence mapping
- Backward compatibility with legacy output paths
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


# Canonical artifact directory structure
ARTIFACT_ROOT = "artifacts"
RUNS_DIR = f"{ARTIFACT_ROOT}/runs"

# Standard run subdirectories
RUN_SUBDIRS = [
    "command.txt",
    "config_resolved.yaml",
    "environment.json",
    "hardware.json",
    "stdout.log",
    "stderr.log",
    "metrics.csv",
    "checkpoints",
    "predictions",
    "confmat",
    "figures",
    "verification.json",
]

# Legacy path mappings for compatibility
LEGACY_PATHS = {
    "output": "artifacts/output",
    "outputs": "artifacts/outputs",
    "output/experiment": "artifacts/output/experiment",
    "logs": "artifacts/logs",
    "checkpoints": "artifacts/checkpoints",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_run_id(prefix: str = "run") -> str:
    """Generate a unique run ID with timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}"


def get_artifact_root(project_root: str | Path) -> Path:
    """Get the canonical artifact root directory."""
    root = Path(project_root) / ARTIFACT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_run_dir(project_root: str | Path, run_id: str | None = None) -> Path:
    """Get or create a run directory."""
    if run_id is None:
        run_id = generate_run_id()
    run_dir = Path(project_root) / RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def init_run_structure(run_dir: Path) -> dict[str, Path]:
    """Initialize standard subdirectories in a run directory."""
    paths = {}
    for subdir in RUN_SUBDIRS:
        if subdir.endswith(".log") or subdir.endswith(".csv") or subdir.endswith(".json") or subdir.endswith(".yaml") or subdir.endswith(".txt"):
            paths[subdir] = run_dir / subdir
        else:
            paths[subdir] = run_dir / subdir
            paths[subdir].mkdir(parents=True, exist_ok=True)
    return paths


def create_run_manifest(
    run_id: str,
    task_id: str,
    command: str,
    config: dict | None = None,
    environment: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create a run manifest with all metadata."""
    manifest = {
        "run_id": run_id,
        "task_id": task_id,
        "command": command,
        "config": config or {},
        "environment": environment or {},
        "metadata": metadata or {},
        "created_at": utc_now(),
        "status": "RUNNING",
    }
    return manifest


def write_run_manifest(run_dir: Path, manifest: dict) -> Path:
    """Write run manifest to run directory."""
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def update_run_manifest(run_dir: Path, updates: dict) -> dict:
    """Update run manifest with new values."""
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {}
    manifest.update(updates)
    manifest["updated_at"] = utc_now()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def write_verification(run_dir: Path, verification: dict) -> Path:
    """Write verification results to run directory."""
    verification_path = run_dir / "verification.json"
    verification_path.write_text(json.dumps(verification, indent=2), encoding="utf-8")
    return verification_path


def write_command(run_dir: Path, command: str) -> Path:
    """Write command to run directory."""
    cmd_path = run_dir / "command.txt"
    cmd_path.write_text(command, encoding="utf-8")
    return cmd_path


def write_metrics(run_dir: Path, metrics: list[dict] | str) -> Path:
    """Write metrics CSV to run directory."""
    metrics_path = run_dir / "metrics.csv"
    if isinstance(metrics, str):
        metrics_path.write_text(metrics, encoding="utf-8")
    else:
        if metrics:
            import csv
            with metrics_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
                writer.writeheader()
                writer.writerows(metrics)
    return metrics_path


def capture_hardware_info() -> dict:
    """Capture current hardware information."""
    info = {
        "captured_at": utc_now(),
    }
    
    # GPU info
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu"] = {
                "device_count": torch.cuda.device_count(),
                "devices": [],
            }
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                info["gpu"]["devices"].append({
                    "id": i,
                    "name": torch.cuda.get_device_name(i),
                    "total_memory_gb": props.total_memory / 1024**3,
                })
    except Exception:
        pass
    
    # CPU/Memory via system commands
    try:
        import subprocess
        # CPU cores
        result = subprocess.run(
            ["nproc"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            info["cpu_cores"] = int(result.stdout.strip())
        
        # Memory
        result = subprocess.run(
            ["free", "-b"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 3:
                    info["memory_total_gb"] = int(parts[1]) / 1024**3
                    info["memory_used_gb"] = int(parts[2]) / 1024**3
    except Exception:
        pass
    
    return info


def capture_environment() -> dict:
    """Capture current Python environment."""
    import subprocess
    import sys
    
    env = {
        "captured_at": utc_now(),
        "python_version": sys.version,
        "platform": sys.platform,
    }
    
    # Key packages
    packages = ["torch", "numpy", "yaml"]
    for pkg in packages:
        try:
            mod = __import__(pkg)
            env[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            env[pkg] = None
    
    return env


class EvidenceManager:
    """Manage evidence collection and verification for reproducibility."""
    
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.artifact_root = self.project_root / ARTIFACT_ROOT
        self.runs_dir = self.project_root / RUNS_DIR
        self.evidence_index_path = self.artifact_root / "evidence_index.json"
        
        # Initialize directories
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
    
    def create_run(self, task_id: str, command: str, config: dict | None = None) -> tuple[str, Path]:
        """Create a new run with standard structure."""
        run_id = generate_run_id()
        run_dir = self.get_run_dir(run_id)
        init_run_structure(run_dir)
        
        # Write manifest
        manifest = create_run_manifest(
            run_id=run_id,
            task_id=task_id,
            command=command,
            config=config,
            environment=capture_environment(),
            metadata={"hardware": capture_hardware_info()},
        )
        write_run_manifest(run_dir, manifest)
        
        # Write command
        write_command(run_dir, command)
        
        # Update index
        self._add_to_index(run_id, task_id)
        
        return run_id, run_dir
    
    def get_run_dir(self, run_id: str) -> Path:
        """Get run directory by ID."""
        return self.runs_dir / run_id
    
    def get_run_manifest(self, run_id: str) -> dict | None:
        """Get run manifest."""
        manifest_path = self.runs_dir / run_id / "run_manifest.json"
        if manifest_path.exists():
            return json.loads(manifest_path.read_text())
        return None
    
    def complete_run(self, run_id: str, status: str = "COMPLETE",
                     metrics: list[dict] | None = None,
                     verification: dict | None = None) -> dict:
        """Mark run as complete with final metrics."""
        run_dir = self.get_run_dir(run_id)
        updates = {
            "status": status,
            "completed_at": utc_now(),
        }
        manifest = update_run_manifest(run_dir, updates)
        
        # Write metrics if provided
        if metrics:
            write_metrics(run_dir, metrics)
        
        # Write verification if provided
        if verification:
            write_verification(run_dir, verification)
        
        return manifest
    
    def fail_run(self, run_id: str, reason: str) -> dict:
        """Mark run as failed."""
        run_dir = self.get_run_dir(run_id)
        updates = {
            "status": "FAILED",
            "completed_at": utc_now(),
            "failure_reason": reason,
        }
        return update_run_manifest(run_dir, updates)
    
    def get_evidence_for_claim(self, claim: str) -> list[dict]:
        """Find evidence (runs) that support a specific claim."""
        # Search through all runs for metrics matching the claim
        evidence = []
        if not self.evidence_index_path.exists():
            return evidence
        
        index = json.loads(self.evidence_index_path.read_text())
        for run_id, run_info in index.get("runs", {}).items():
            run_dir = self.get_run_dir(run_id)
            metrics_path = run_dir / "metrics.csv"
            if metrics_path.exists():
                # Simple search - in production would use more sophisticated matching
                content = metrics_path.read_text()
                if claim.lower() in content.lower():
                    evidence.append({
                        "run_id": run_id,
                        "task_id": run_info.get("task_id"),
                        "metrics_path": str(metrics_path),
                    })
        
        return evidence
    
    def verify_evidence_chain(self, run_id: str) -> dict:
        """Verify the complete evidence chain for a run."""
        run_dir = self.get_run_dir(run_id)
        manifest = self.get_run_manifest(run_id)
        
        verification = {
            "run_id": run_id,
            "verified_at": utc_now(),
            "checks": [],
            "status": "PASS",
        }
        
        # Check required files exist
        required_files = ["command.txt", "run_manifest.json"]
        for fname in required_files:
            path = run_dir / fname
            if path.exists():
                verification["checks"].append({
                    "type": "file_exists",
                    "path": fname,
                    "status": "PASS",
                })
            else:
                verification["checks"].append({
                    "type": "file_exists",
                    "path": fname,
                    "status": "FAIL",
                })
                verification["status"] = "FAIL"
        
        # Check manifest integrity
        if manifest:
            required_manifest_keys = ["run_id", "task_id", "command", "created_at"]
            for key in required_manifest_keys:
                if key in manifest:
                    verification["checks"].append({
                        "type": "manifest_key",
                        "key": key,
                        "status": "PASS",
                    })
                else:
                    verification["checks"].append({
                        "type": "manifest_key",
                        "key": key,
                        "status": "FAIL",
                    })
                    verification["status"] = "FAIL"
        
        # Write verification
        write_verification(run_dir, verification)
        
        return verification
    
    def _add_to_index(self, run_id: str, task_id: str) -> None:
        """Add run to evidence index."""
        if self.evidence_index_path.exists():
            index = json.loads(self.evidence_index_path.read_text())
        else:
            index = {"runs": {}, "last_updated": None}
        
        index["runs"][run_id] = {
            "task_id": task_id,
            "added_at": utc_now(),
        }
        index["last_updated"] = utc_now()
        
        self.evidence_index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    
    def list_runs(self, task_id: str | None = None, status: str | None = None) -> list[dict]:
        """List all runs, optionally filtered."""
        runs = []
        if not self.evidence_index_path.exists():
            return runs
        
        index = json.loads(self.evidence_index_path.read_text())
        for run_id, run_info in index.get("runs", {}).items():
            if task_id and run_info.get("task_id") != task_id:
                continue
            
            manifest = self.get_run_manifest(run_id)
            if manifest:
                if status and manifest.get("status") != status:
                    continue
                runs.append(manifest)
        
        return sorted(runs, key=lambda x: x.get("created_at", ""), reverse=True)
    
    def migrate_legacy_paths(self) -> dict:
        """Migrate legacy output paths to canonical artifact structure."""
        migrations = []
        
        for legacy, canonical in LEGACY_PATHS.items():
            legacy_path = self.project_root / legacy
            canonical_path = self.project_root / canonical
            
            if legacy_path.exists() and not canonical_path.exists():
                # Create symlink for backward compatibility
                try:
                    canonical_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(legacy_path, canonical_path)
                    migrations.append({
                        "legacy": str(legacy_path),
                        "canonical": str(canonical_path),
                        "status": "copied",
                    })
                except Exception as e:
                    migrations.append({
                        "legacy": str(legacy_path),
                        "canonical": str(canonical_path),
                        "status": "error",
                        "error": str(e),
                    })
        
        return {"migrations": migrations}
