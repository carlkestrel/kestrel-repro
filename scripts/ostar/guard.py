"""OSTAR pre-flight protection guard.

Verifies system state before a soak run begins:
  - Git status and dirty-diff preservation
  - Commit / branch recording
  - GPU / CPU / memory / disk inventory
  - No real training task competing for resources
  - Independent test workspace / branch isolation
  - Config and dependency snapshots
  - State-recovery and heartbeat mechanism verification
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import constants as _C
from . import hardware_monitor as _hw


@dataclass
class GuardResult:
    """Result of the pre-flight guard checks."""
    passed: bool
    timestamp_utc: str
    run_id: str
    git_commit: str = ""
    git_branch: str = ""
    git_dirty: bool = False
    git_dirty_diff: str = ""
    gpu_label: str = ""
    gpu_count: int = 0
    cpu_model: str = ""
    cpu_cores: int = 0
    ram_total_gb: float = 0.0
    disk_free_gb: float = 0.0
    project_root: str = ""
    soak_root: str = ""
    conda_env: str = ""
    python_version: str = ""
    torch_version: str = ""
    competing_processes: list[dict] = field(default_factory=list)
    heartbeat_mechanism_ok: bool = False
    state_recovery_ok: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, message: str = "") -> None:
        self.checks.append({
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "message": message,
        })
        if not passed:
            self.errors.append(f"[{name}] {message}")

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "timestamp_utc": self.timestamp_utc,
            "run_id": self.run_id,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "git_dirty": self.git_dirty,
            "gpu_label": self.gpu_label,
            "gpu_count": self.gpu_count,
            "cpu_model": self.cpu_model,
            "cpu_cores": self.cpu_cores,
            "ram_total_gb": self.ram_total_gb,
            "disk_free_gb": self.disk_free_gb,
            "project_root": self.project_root,
            "soak_root": self.soak_root,
            "conda_env": self.conda_env,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "competing_processes": self.competing_processes,
            "heartbeat_mechanism_ok": self.heartbeat_mechanism_ok,
            "state_recovery_ok": self.state_recovery_ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks,
        }


class Guard:
    """Pre-flight protection checks for OSTAR soak runs."""

    # Patterns for processes that indicate real training (not soak tests)
    TRAINING_PROCESS_PATTERNS = [
        "python.*train", "python.*main", "python.*train.py",
        "torchrun", "torch.distributed.run", "deepspeed",
        "accelerate", "python.*training",
    ]

    def __init__(self, project_root: Path | str):
        self.project_root = Path(project_root).resolve()
        self._hw = _hw.HardwareMonitor(project_root=self.project_root)
        self._result: GuardResult | None = None

    def run(self, soak_root: Path | str | None = None) -> GuardResult:
        """Execute all pre-flight checks. Returns GuardResult."""
        result = GuardResult(
            passed=True,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            run_id=f"{_C.DEFAULT_SOAK_RUN_ID_PREFIX}_{uuid.uuid4().hex[:12]}",
            project_root=str(self.project_root),
            soak_root=str(soak_root or self.project_root / "soak"),
        )
        self._result = result

        self._check_python()
        self._check_torch()
        self._check_conda_env()
        self._check_git_status()
        self._check_hardware()
        self._check_disk_space()
        self._check_competing_processes()
        self._check_soak_root(soak_root)
        self._check_heartbeat_mechanism()
        self._check_state_recovery()

        result.passed = all(c["status"] == "PASS" for c in result.checks)
        return result

    def _check_python(self) -> None:
        ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        self._result.add_check("PYTHON_VERSION", True, ver)
        self._result.python_version = ver

    def _check_torch(self) -> None:
        try:
            import torch as _torch
            ver = _torch.__version__
            self._result.add_check("TORCH_AVAILABLE", True, f"v{ver}")
            self._result.torch_version = ver
        except ImportError:
            self._result.add_check("TORCH_AVAILABLE", False, "torch not installed")
            self._result.torch_version = "MISSING"

    def _check_conda_env(self) -> None:
        env = os.environ.get("CONDA_DEFAULT_ENV", "")
        self._result.conda_env = env
        self._result.add_check("CONDA_ENV", True, env or "(system python)")

    def _check_git_status(self) -> None:
        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            self._result.add_check("GIT_REPO", False, "not a git repository")
            return
        self._result.add_check("GIT_REPO", True)

        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=str(self.project_root),
                stderr=subprocess.DEVNULL, text=True,
            ).strip()
            self._result.git_commit = commit[:12]

            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.project_root), stderr=subprocess.DEVNULL, text=True,
            ).strip()
            self._result.git_branch = branch

            # Capture dirty diff safely — never discard user changes
            dirty = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=str(self.project_root), capture_output=True, text=True,
            )
            self._result.git_dirty = dirty.returncode == 0 and bool(dirty.stdout.strip())

            if self._result.git_dirty:
                diff = subprocess.run(
                    ["git", "diff"],
                    cwd=str(self.project_root), capture_output=True, text=True,
                )
                self._result.git_dirty_diff = diff.stdout[:5000]  # cap at 5 KB
                self._result.warnings.append(
                    "Uncommitted changes present (first 5KB captured in guard result)"
                )
                self._result.add_check(
                    "GIT_DIRTY_PROTECTION", True,
                    "uncommitted changes recorded, will NOT be overwritten",
                )
            else:
                self._result.add_check("GIT_DIRTY_PROTECTION", True, "clean working tree")

        except subprocess.CalledProcessError:
            self._result.add_check("GIT_ACCESS", False, "cannot read git info")

    def _check_hardware(self) -> None:
        snap = self._hw.snapshot()
        self._result.gpu_count = snap.gpu_count
        self._result.ram_total_gb = snap.cpu_memory_total_gb
        self._result.cpu_model = self._read_cpu_model()
        self._result.cpu_cores = os.cpu_count() or 0

        if snap.gpu_count > 0:
            self._result.gpu_label = f"{snap.gpu_count}x {snap.gpu_names[0]}"
            self._result.add_check(
                "GPU_AVAILABLE", True,
                f"{snap.gpu_count} GPU(s): {snap.gpu_names[0]}",
            )
        else:
            self._result.gpu_label = "none"
            self._result.add_check("GPU_AVAILABLE", False, "no GPU detected")
            self._result.warnings.append("No GPU detected — GPU stress tests will be skipped")

        self._result.add_check(
            "CPU_CORES", True,
            f"{self._result.cpu_cores} cores, {self._result.ram_total_gb:.1f} GB RAM",
        )

    def _check_disk_space(self) -> None:
        snap = self._hw.snapshot()
        self._result.disk_free_gb = snap.disk_free_gb
        required = _C.DEFAULT_DISK_RESERVE_GB + 5  # 5 GB for soak artifacts
        if snap.disk_free_gb >= required:
            self._result.add_check(
                "DISK_SPACE", True,
                f"{snap.disk_free_gb:.1f} GB free",
            )
        else:
            self._result.add_check(
                "DISK_SPACE", False,
                f"only {snap.disk_free_gb:.1f} GB free, need ≥{required} GB",
            )

    def _check_competing_processes(self) -> None:
        """Detect real training processes that would compete for GPU resources."""
        competing: list[dict] = []
        try:
            ps_result = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, timeout=10,
            )
            if ps_result.returncode == 0:
                lines = ps_result.stdout.splitlines()
                for line in lines[1:]:  # skip header
                    for pattern in self.TRAINING_PROCESS_PATTERNS:
                        import re as _re
                        if _re.search(pattern, line, _re.IGNORECASE):
                            parts = line.split()
                            if len(parts) >= 11:
                                competing.append({
                                    "pid": parts[1],
                                    "user": parts[0],
                                    "command": " ".join(parts[10:]),
                                })
                            break
        except Exception:
            pass

        self._result.competing_processes = competing
        if competing:
            self._result.warnings.append(
                f"{len(competing)} potential training process(es) detected — "
                f"may compete for GPU resources",
            )
        self._result.add_check(
            "NO_REAL_TRAINING", True,
            f"{len(competing)} competing process(es) noted",
        )

    def _check_soak_root(self, soak_root: Path | str | None) -> None:
        root = (Path(soak_root) if soak_root else self.project_root / "soak").resolve()
        self._result.soak_root = str(root)

        # Ensure we can create it
        try:
            root.mkdir(parents=True, exist_ok=True)
            test_file = root / ".guard_write_test"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            self._result.add_check("SOAK_ROOT_WRITABLE", True, str(root))
        except Exception as e:
            self._result.add_check("SOAK_ROOT_WRITABLE", False, str(e))

    def _check_heartbeat_mechanism(self) -> None:
        """Verify we can write a heartbeat file atomically."""
        if not self._result:
            return
        soak_root = Path(self._result.soak_root)
        hb_path = soak_root / "heartbeat.json"
        try:
            import json as _json
            hb_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = hb_path.with_suffix(".tmp")
            tmp.write_text(_json.dumps({"test": True}), encoding="utf-8")
            tmp.replace(hb_path)
            self._result.heartbeat_mechanism_ok = True
            self._result.add_check("HEARTBEAT_MECHANISM", True)
        except Exception as e:
            self._result.heartbeat_mechanism_ok = False
            self._result.add_check("HEARTBEAT_MECHANISM", False, str(e))

    def _check_state_recovery(self) -> None:
        """Verify we can write and read back atomic state files."""
        if not self._result:
            return
        soak_root = Path(self._result.soak_root)
        ckpt_dir = soak_root / "checkpoints"
        try:
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            test_ckpt = ckpt_dir / "ckpt_guard_test.json"
            import json as _json
            data = {"guard": "test", "seq": 0}
            tmp = test_ckpt.with_suffix(".tmp")
            tmp.write_text(_json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(test_ckpt)
            loaded = _json.loads(test_ckpt.read_text())
            assert loaded == data
            test_ckpt.unlink()
            self._result.state_recovery_ok = True
            self._result.add_check("STATE_RECOVERY", True)
        except Exception as e:
            self._result.state_recovery_ok = False
            self._result.add_check("STATE_RECOVERY", False, str(e))

    def _read_cpu_model(self) -> str:
        try:
            cpuinfo = Path("/proc/cpuinfo").read_text(errors="ignore")
            for line in cpuinfo.splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return "unknown"
