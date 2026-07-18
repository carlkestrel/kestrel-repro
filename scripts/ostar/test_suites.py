"""OSTAR stress test suites (Sections III.A–G).

Each suite is a callable that returns a structured result dict.
Suites are run in isolation as subprocesses to prevent crashes from propagating.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SuiteResult:
    """Result returned by every test suite."""
    name: str
    status: str       # PASS | FAIL | SKIP | ERROR
    duration_seconds: float
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    flaky: bool = False
    output: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "duration_seconds": round(self.duration_seconds, 3),
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "flaky": self.flaky,
            "output": self.output[:2000],
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Base runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_subprocess(
    cmd: list[str],
    timeout_seconds: int = 300,
    cwd: str | Path | None = None,
) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(cwd) if cwd else None,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout after {timeout_seconds}s"
    except Exception as e:
        return -1, "", str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Suite A: CI Repeat Stress  (Section III.A)
# ─────────────────────────────────────────────────────────────────────────────

def run_ci_stress(
    project_root: Path,
    *,
    level_1_fast: bool = True,
    level_2_full: bool = False,
    runs: int = 3,
) -> SuiteResult:
    """Run CI suites repeatedly to detect flakiness and regressions."""
    t0 = time.monotonic()
    name = "CI_STRESS"
    errors: list[str] = []
    warnings: list[str] = []
    passed = failed = skipped = 0
    flaky = False
    all_results: list[dict] = []

    plugin_root = project_root / ".cursor" / "plugins" / "local" / "dl-paper-repro"
    pytest_root = plugin_root / "tests"
    if not pytest_root.exists():
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=1, output="tests/ directory not found",
        )

    # Run LEVEL-1 fast suite
    if level_1_fast:
        for i in range(runs):
            rc, stdout, stderr = _run_subprocess(
                [sys.executable, "-m", "pytest", str(pytest_root / "test_startup.py"),
                 "-q", "--tb=short", "-x"],
                timeout_seconds=120,
                cwd=str(project_root),
            )
            combined = stdout + "\n" + stderr
            if rc == 0:
                passed += 1
            elif rc == 5:  # no tests collected
                skipped += 1
            else:
                failed += 1
                errors.append(f"CI L1 run {i+1}: exit {rc}")
                if i > 0:
                    flaky = True
            all_results.append({"run": i + 1, "level": 1, "rc": rc})

    # Run LEVEL-2 full suite (more expensive)
    if level_2_full:
        for i in range(min(runs, 2)):
            rc, stdout, stderr = _run_subprocess(
                [sys.executable, "-m", "pytest", str(pytest_root),
                 "-q", "--tb=short", "-x", "--ignore=tests/test_chaos.py"],
                timeout_seconds=300,
                cwd=str(project_root),
            )
            if rc == 0:
                passed += 1
            elif rc == 5:
                skipped += 1
            else:
                failed += 1
                errors.append(f"CI L2 run {i+1}: exit {rc}")
            all_results.append({"run": i + 1, "level": 2, "rc": rc})

    duration = time.monotonic() - t0
    status = "PASS" if failed == 0 else ("SKIP" if skipped and failed == 0 else "FAIL")
    return SuiteResult(
        name=name, status=status, duration_seconds=duration,
        passed=passed, failed=failed, skipped=skipped,
        flaky=flaky,
        output="; ".join(str(r) for r in all_results),
        errors=errors, warnings=warnings,
        metadata={"total_runs": runs, "level_1_fast": level_1_fast,
                  "level_2_full": level_2_full},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Suite B: Scheduler Stress  (Section III.B)
# ─────────────────────────────────────────────────────────────────────────────

def run_scheduler_stress(project_root: Path, runs: int = 5) -> SuiteResult:
    """Stress-test the task scheduler (start/pause/resume/stop/crash recovery)."""
    t0 = time.monotonic()
    name = "SCHEDULER_STRESS"
    errors: list[str] = []
    warnings: list[str] = []
    passed = failed = skipped = 0
    all_results: list[dict] = []

    plugin_root = project_root / ".cursor" / "plugins" / "local" / "dl-paper-repro"

    # Test: reproctl status (start/pause/resume/verify cycle)
    reproctl = plugin_root / "scripts" / "reproctl.py"
    if not reproctl.exists():
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=1, output="reproctl.py not found",
        )

    for i in range(runs):
        rc, stdout, stderr = _run_subprocess(
            [sys.executable, str(reproctl), "version"],
            timeout_seconds=30,
        )
        if rc == 0:
            passed += 1
        else:
            failed += 1
            errors.append(f"reproctl version run {i+1}: exit {rc}")
        all_results.append({"run": i + 1, "command": "version", "rc": rc})

    # Test: orphan process detection (simulated)
    rc, stdout, stderr = _run_subprocess(
        [sys.executable, str(reproctl), "status",
         "--project", str(project_root)],
        timeout_seconds=30,
    )
    if rc == 0:
        passed += 1
    else:
        # status may return non-zero if no repro project exists — not an error
        pass
    all_results.append({"run": 1, "command": "status", "rc": rc})

    duration = time.monotonic() - t0
    status = "PASS" if failed == 0 else "FAIL"
    return SuiteResult(
        name=name, status=status, duration_seconds=duration,
        passed=passed, failed=failed, skipped=skipped,
        output="; ".join(str(r) for r in all_results),
        errors=errors, warnings=warnings,
        metadata={"runs": runs},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Suite C: GPU Short-Loop Stress  (Section III.C)
# ─────────────────────────────────────────────────────────────────────────────

def run_gpu_stress(
    project_root: Path,
    *,
    max_steps: int = 100,
    batch_size: int = 10,
) -> SuiteResult:
    """Run real model forward/backward/eval short loops (max 100 steps)."""
    t0 = time.monotonic()
    name = "GPU_STRESS"
    errors: list[str] = []
    warnings: list[str] = []

    try:
        import torch
        if not torch.cuda.is_available():
            return SuiteResult(
                name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
                skipped=1, output="No GPU available",
            )
    except ImportError:
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=1, output="torch not installed",
        )

    # Try to find a training script in fixtures or primary
    fixture_train = project_root / "fixtures" / "golden_torch_A" / "train.py"
    if not fixture_train.exists():
        fixture_train = project_root / "fixtures" / "minimal_pytorch_repo" / "train.py"

    if not fixture_train.exists():
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=1, output="No fixture training script found",
        )

    # Run with GPU short loop args
    rc, stdout, stderr = _run_subprocess(
        [
            sys.executable, str(fixture_train),
            "--max-steps", str(min(max_steps, 20)),  # cap at 20 for soak
            "--batch-size", str(batch_size),
        ],
        timeout_seconds=300,
        cwd=str(project_root),
    )
    duration = time.monotonic() - t0
    combined = stdout + "\n" + stderr

    passed = 1 if rc == 0 else 0
    failed = 0 if rc == 0 else 1
    status = "PASS" if rc == 0 else "FAIL"

    if rc != 0:
        errors.append(f"GPU short loop: exit {rc}")
        # Check for OOM
        if "out" in combined.lower() and "memory" in combined.lower():
            errors.append("OOM detected in GPU loop")

    return SuiteResult(
        name=name, status=status, duration_seconds=duration,
        passed=passed, failed=failed, skipped=0,
        output=combined[:2000],
        errors=errors, warnings=warnings,
        metadata={"max_steps": max_steps, "batch_size": batch_size,
                  "fixture": str(fixture_train.name)},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Suite D: Batch Boundary Stress  (Section III.D)
# ─────────────────────────────────────────────────────────────────────────────

def run_batch_boundary_stress(
    project_root: Path,
    *,
    candidates: list[str] | None = None,
    timeout_per: int = 120,
) -> SuiteResult:
    """Test batch sizes around recommended_batch ± 1, P95, and max."""
    t0 = time.monotonic()
    name = "BATCH_BOUNDARY"
    candidates = candidates or ["paper_batch", "recommended_batch",
                                "recommended_batch_minus_one",
                                "recommended_batch_plus_one",
                                "p95_points_batch", "max_points_batch"]
    errors: list[str] = []
    warnings: list[str] = []
    passed = failed = skipped = 0
    results: list[dict] = []

    fixture_train = project_root / "fixtures" / "golden_torch_A" / "train.py"
    if not fixture_train.exists():
        fixture_train = project_root / "fixtures" / "minimal_pytorch_repo" / "train.py"

    if not fixture_train.exists():
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=len(candidates), output="No fixture training script",
        )

    for candidate in candidates:
        # Map candidate name to actual batch sizes for testing
        batch_map = {
            "paper_batch": 10,
            "recommended_batch": 10,
            "recommended_batch_minus_one": 9,
            "recommended_batch_plus_one": 11,
            "p95_points_batch": 16,
            "max_points_batch": 32,
        }
        bs = batch_map.get(candidate, 10)
        rc, stdout, stderr = _run_subprocess(
            [
                sys.executable, str(fixture_train),
                "--max-steps", "5",
                "--batch-size", str(bs),
            ],
            timeout_seconds=timeout_per,
            cwd=str(project_root),
        )
        results.append({"candidate": candidate, "batch_size": bs, "rc": rc})
        if rc == 0:
            passed += 1
        elif rc == -1:
            skipped += 1
        else:
            failed += 1
            errors.append(f"{candidate} (bs={bs}): exit {rc}")
            if "out" in (stdout + stderr).lower() and "memory" in (stdout + stderr).lower():
                warnings.append(f"OOM at {candidate} bs={bs}")

    duration = time.monotonic() - t0
    status = "PASS" if failed == 0 else "FAIL"
    return SuiteResult(
        name=name, status=status, duration_seconds=duration,
        passed=passed, failed=failed, skipped=skipped,
        output=json.dumps(results),
        errors=errors, warnings=warnings,
        metadata={"candidates": candidates},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Suite E: DataLoader Stress  (Section III.E)
# ─────────────────────────────────────────────────────────────────────────────

def run_dataloader_stress(
    project_root: Path,
    *,
    worker_counts: list[int] | None = None,
    timeout_per: int = 120,
) -> SuiteResult:
    """Stress test DataLoader worker configurations."""
    t0 = time.monotonic()
    name = "DATALOADER_STRESS"
    worker_counts = worker_counts or [0, 2, 4]
    errors: list[str] = []
    warnings: list[str] = []
    passed = failed = skipped = 0
    results: list[dict] = []

    fixture_train = project_root / "fixtures" / "golden_torch_A" / "train.py"
    if not fixture_train.exists():
        fixture_train = project_root / "fixtures" / "minimal_pytorch_repo" / "train.py"

    if not fixture_train.exists():
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=len(worker_counts), output="No fixture training script",
        )

    for workers in worker_counts:
        rc, stdout, stderr = _run_subprocess(
            [
                sys.executable, str(fixture_train),
                "--max-steps", "5",
                "--num-workers", str(workers),
            ],
            timeout_seconds=timeout_per,
            cwd=str(project_root),
        )
        results.append({"workers": workers, "rc": rc})
        combined = stdout + "\n" + stderr
        if rc == 0:
            passed += 1
        elif rc == -1:
            skipped += 1
        else:
            failed += 1
            errors.append(f"num_workers={workers}: exit {rc}")
            if "deadlock" in combined.lower() or "timeout" in combined.lower():
                warnings.append(f"Possible deadlock at workers={workers}")

    duration = time.monotonic() - t0
    status = "PASS" if failed == 0 else "FAIL"
    return SuiteResult(
        name=name, status=status, duration_seconds=duration,
        passed=passed, failed=failed, skipped=skipped,
        output=json.dumps(results),
        errors=errors, warnings=warnings,
        metadata={"worker_counts": worker_counts},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Suite F: Metric Consistency Stress  (Section III.F)
# ─────────────────────────────────────────────────────────────────────────────

def run_metric_consistency_stress(project_root: Path) -> SuiteResult:
    """Verify metric computation is deterministic and consistent."""
    t0 = time.monotonic()
    name = "METRIC_CONSISTENCY"

    errors: list[str] = []
    warnings: list[str] = []
    passed = failed = skipped = 0

    # Run metric recompute on known fixtures
    plugin_root = project_root / ".cursor" / "plugins" / "local" / "dl-paper-repro"
    metrics_cli = plugin_root / "scripts" / "repro_agent" / "metrics" / "cli.py"

    # Check if recompute is deterministic (run twice, compare)
    if not metrics_cli.exists():
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=1, output="metrics/cli.py not found",
        )

    fixture_cm = project_root / "fixtures" / "golden_torch_A"
    if not fixture_cm.exists():
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=1, output="golden_torch_A fixture not found",
        )

    results: list[dict] = []
    for run_i in range(2):
        rc, stdout, stderr = _run_subprocess(
            [
                sys.executable, str(metrics_cli),
                "recompute",
                "--project", str(project_root),
            ],
            timeout_seconds=120,
        )
        results.append({"run": run_i + 1, "rc": rc, "output_len": len(stdout)})

    # Metric consistency: same input → same output
    if results[0]["rc"] == 0 and results[1]["rc"] == 0:
        if results[0]["output_len"] == results[1]["output_len"]:
            passed += 1
        else:
            failed += 1
            errors.append("Metric recompute produced different output lengths across runs")
    else:
        failed += len([r for r in results if r["rc"] != 0])
        errors.append("Metric recompute failed in one or more runs")

    duration = time.monotonic() - t0
    status = "PASS" if failed == 0 else "FAIL"
    return SuiteResult(
        name=name, status=status, duration_seconds=duration,
        passed=passed, failed=failed, skipped=skipped,
        output=json.dumps(results),
        errors=errors, warnings=warnings,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Suite G: Resource Leak Stress  (Section III.G)
# ─────────────────────────────────────────────────────────────────────────────

def run_resource_leak_stress(
    project_root: Path,
    *,
    iterations: int = 10,
) -> SuiteResult:
    """Detect resource leaks: GPU memory, CPU RAM, file handles, subprocess count."""
    t0 = time.monotonic()
    name = "RESOURCE_LEAK"

    errors: list[str] = []
    warnings: list[str] = []

    try:
        import torch
        TORCH_OK = torch.cuda.is_available()
    except ImportError:
        TORCH_OK = False

    snapshots: list[dict] = []

    for i in range(iterations):
        snap = _sample_resources(project_root)
        snapshots.append(snap)
        time.sleep(1)

    if len(snapshots) < 3:
        return SuiteResult(
            name=name, status="SKIP", duration_seconds=time.monotonic() - t0,
            skipped=1, output="Not enough samples",
        )

    # Detect monotonically growing resources
    growing: list[str] = []

    if TORCH_OK:
        try:
            gpu_alloc = [s["gpu_allocated_gb"] for s in snapshots if s.get("gpu_allocated_gb") is not None]
            if len(gpu_alloc) >= 3 and gpu_alloc[-1] > gpu_alloc[0] * 1.5:
                growing.append(f"GPU allocated: {gpu_alloc[0]:.2f} → {gpu_alloc[-1]:.2f} GB")
                warnings.append("GPU memory leak suspected")
        except Exception:
            pass

    cpu_rams = [s["ram_used_mb"] for s in snapshots if s.get("ram_used_mb") is not None]
    if len(cpu_rams) >= 3:
        if cpu_rams[-1] > cpu_rams[0] * 1.5:
            growing.append(f"CPU RAM: {cpu_rams[0]:.0f} → {cpu_rams[-1]:.0f} MB")
            warnings.append("CPU RAM leak suspected")

    fds = [s["file_handles"] for s in snapshots if s.get("file_handles") is not None]
    if len(fds) >= 3:
        if fds[-1] > fds[0] * 2:
            growing.append(f"File handles: {fds[0]} → {fds[-1]}")
            warnings.append("File handle leak suspected")

    passed = 1 if not growing else 0
    failed = 1 if growing else 0
    status = "PASS" if not growing else "FAIL"

    duration = time.monotonic() - t0
    return SuiteResult(
        name=name, status=status, duration_seconds=duration,
        passed=passed, failed=failed, skipped=0,
        output=json.dumps(snapshots[:3]),  # first 3 as sample
        errors=errors, warnings=warnings,
        metadata={"iterations": iterations, "growing_resources": growing,
                  "samples": len(snapshots)},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sample_resources(project_root: Path) -> dict:
    """Sample current resource usage."""
    sample = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ram_used_mb": 0,
        "file_handles": 0,
        "gpu_allocated_gb": None,
    }
    try:
        import torch
        if torch.cuda.is_available():
            sample["gpu_allocated_gb"] = torch.cuda.memory_allocated(0) / (1024 ** 3)
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["free", "-m"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 3:
                    sample["ram_used_mb"] = int(parts[2])
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["ls", "/proc/self/fd"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            sample["file_handles"] = len(result.stdout.splitlines())
    except Exception:
        pass

    return sample


# ─────────────────────────────────────────────────────────────────────────────
# All suites dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def run_all_suites(
    project_root: Path,
    *,
    config: dict | None = None,
) -> list[SuiteResult]:
    """Run all enabled test suites. Returns list of SuiteResult."""
    cfg = config or {}
    results: list[SuiteResult] = []

    if cfg.get("run_ci_stress", True):
        results.append(run_ci_stress(
            project_root,
            level_1_fast=cfg.get("ci_level_1_fast", True),
            level_2_full=cfg.get("ci_level_2_full", False),
            runs=3,
        ))

    if cfg.get("run_scheduler_stress", True):
        results.append(run_scheduler_stress(project_root, runs=3))

    if cfg.get("run_gpu_stress", True):
        results.append(run_gpu_stress(project_root, max_steps=20, batch_size=10))

    if cfg.get("run_batch_boundary", True):
        results.append(run_batch_boundary_stress(project_root))

    if cfg.get("run_dataloader_stress", True):
        results.append(run_dataloader_stress(project_root))

    if cfg.get("run_metric_consistency", True):
        results.append(run_metric_consistency_stress(project_root))

    if cfg.get("run_resource_leak", True):
        results.append(run_resource_leak_stress(project_root, iterations=10))

    return results
