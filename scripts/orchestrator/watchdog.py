"""
Enhanced Watchdog - GPU monitoring, OOM detection, and training health diagnostics.

This module extends the base Watchdog with:
- GPU utilization, memory, temperature monitoring
- OOM detection and automatic recovery strategies
- Gradient anomaly detection via log parsing
- Dataloader stall detection
- Disk/memory pressure monitoring
"""
from __future__ import annotations

import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class Watchdog:
    """Enhanced watchdog with GPU monitoring, OOM detection, and training health."""

    def __init__(self, store, process_manager, heartbeat_timeout: float = 30.0,
                 project_root: Path | None = None):
        self.store = store
        self.process_manager = process_manager
        self.heartbeat_timeout = heartbeat_timeout
        self.project_root = project_root
        self._gpu_cache: dict[int, dict] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 10.0  # seconds

    def controller_stale(self) -> bool:
        heartbeat = self.store.get_heartbeat()
        if heartbeat is None:
            return True
        return time.time() - heartbeat["timestamp"] > self.heartbeat_timeout

    def inspect(self, task: dict) -> dict:
        """Enhanced inspection with GPU monitoring."""
        pid = task.get("pid")
        alive = self.process_manager.is_alive(pid)
        timed_out = False
        elapsed = 0.0

        if task.get("started_at"):
            started = datetime.fromisoformat(task["started_at"]).timestamp()
            elapsed = max(0.0, time.time() - started)
            timed_out = elapsed > float(task.get("timeout_min", 0)) * 60

        diagnosis = {
            "pid": pid,
            "alive": alive,
            "timed_out": timed_out,
            "elapsed_seconds": elapsed,
        }

        # GPU monitoring
        if alive and pid:
            gpu_info = self.get_gpu_info()
            diagnosis["gpu"] = gpu_info

            # Check GPU health
            if gpu_info.get("available"):
                if gpu_info.get("temperature_c", 0) > 85:
                    diagnosis["gpu_warning"] = "High GPU temperature"
                if gpu_info.get("memory_used_pct", 0) > 95:
                    diagnosis["gpu_warning"] = "High GPU memory usage"

            # Check for OOM in logs
            oom_detected = self._check_oom_in_logs(task)
            if oom_detected:
                diagnosis["oom_detected"] = True
                diagnosis["oom_recovery_strategy"] = self._get_next_recovery_strategy(
                    task.get("id")
                )

            # Check log staleness
            log_stale = self._check_log_stale(task)
            if log_stale:
                diagnosis["log_stale"] = True

        if timed_out and alive:
            self.process_manager.terminate(int(pid))
            diagnosis["terminated"] = True
            self.store.record_event("WATCHDOG_TIMEOUT", task["id"], diagnosis)

        return diagnosis

    def get_gpu_info(self, force_refresh: bool = False) -> dict:
        """Get GPU information with caching. Supports CUDA and MPS."""
        now = time.time()
        if not force_refresh and (now - self._cache_time) < self._cache_ttl:
            return self._gpu_cache.get(0, {})

        info = {"available": False, "devices": [], "type": None}

        if not TORCH_AVAILABLE:
            return info

        # Check MPS first (Apple Silicon)
        mps_info = self._get_mps_info()
        if mps_info.get("available"):
            info.update(mps_info)
            self._cache_time = now
            self._gpu_cache[0] = info
            return info

        # Check CUDA (NVIDIA)
        try:
            if torch.cuda.is_available():
                info["available"] = True
                info["type"] = "cuda"
                info["device_count"] = torch.cuda.device_count()

                for i in range(torch.cuda.device_count()):
                    dev_info = {
                        "id": i,
                        "name": torch.cuda.get_device_name(i),
                    }

                    # Memory info
                    mem_allocated = torch.cuda.memory_allocated(i) / 1024**3  # GB
                    mem_reserved = torch.cuda.memory_reserved(i) / 1024**3
                    mem_total = torch.cuda.get_device_properties(i).total_memory / 1024**3
                    dev_info["memory_allocated_gb"] = round(mem_allocated, 2)
                    dev_info["memory_reserved_gb"] = round(mem_reserved, 2)
                    dev_info["memory_total_gb"] = round(mem_total, 2)
                    dev_info["memory_used_pct"] = round(mem_reserved / mem_total * 100, 1)

                    self._gpu_cache[i] = dev_info

                # Get temperature via nvidia-smi
                temp_info = self._get_nvidia_smi_temp()
                if temp_info and 0 in self._gpu_cache:
                    self._gpu_cache[0].update(temp_info)

                info["devices"] = [self._gpu_cache.get(i, {}) for i in range(info["device_count"])]
            else:
                info["type"] = "none"
        except Exception as e:
            info["error"] = str(e)

        self._cache_time = now
        self._gpu_cache[0] = info
        return info

    def _get_mps_info(self) -> dict:
        """Get MPS (Metal Performance Shaders) GPU info for Apple Silicon."""
        info = {"available": False, "type": "mps", "devices": []}

        try:
            if not hasattr(torch.backends, "mps"):
                return info

            if not torch.backends.mps.is_available():
                return info

            info["available"] = True
            info["device_count"] = 1

            # MPS device info
            dev_info = {
                "id": 0,
                "name": "Apple Silicon GPU (MPS)",
                "type": "mps",
                "architecture": "Apple GPU",
            }

            # Try to get memory info (MPS has limited memory reporting)
            try:
                if hasattr(torch.mps, "current_allocated_memory"):
                    mem_allocated = torch.mps.current_allocated_memory() / 1024**3
                    dev_info["memory_allocated_gb"] = round(mem_allocated, 2)
            except Exception:
                pass

            try:
                if hasattr(torch.mps, "set_per_process_memory_fraction"):
                    # Get system memory for GPU context
                    import subprocess
                    result = subprocess.run(
                        ["sysctl", "-n", "hw.memsize"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        total_mem_bytes = int(result.stdout.strip())
                        dev_info["memory_total_gb"] = round(total_mem_bytes / 1024**3, 2)
            except Exception:
                pass

            info["devices"].append(dev_info)
            self._gpu_cache[0] = info

        except Exception as e:
            info["error"] = str(e)

        return info

    def _get_nvidia_smi_temp(self) -> dict | None:
        """Get GPU temperature via nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,utilization.gpu",
                 "--format=csv,noheader,nounits", "-i", "0"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    return {
                        "temperature_c": int(parts[0].strip()),
                        "power_draw_w": float(parts[1].strip()),
                        "utilization_pct": int(parts[2].strip()),
                    }
        except Exception:
            pass
        return None

    def _check_oom_in_logs(self, task: dict) -> bool:
        """Check if OOM occurred in task logs."""
        log_path = task.get("log_path")
        if not log_path or not Path(log_path).exists():
            return False

        try:
            content = Path(log_path).read_text(errors="ignore")
            oom_patterns = [
                r"out.*of.*memory",
                r"OOM",
                r"CUDA.*out.*of.*memory",
                r"OutOfMemoryError",
                r"RuntimeError.*memory",
                r"Killed.*signal.*SIGKILL",
            ]
            for pattern in oom_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True
        except Exception:
            pass
        return False

    def _check_log_stale(self, task: dict, threshold_seconds: float = 120.0) -> bool:
        """Check if log file hasn't been updated recently."""
        log_path = task.get("log_path")
        if not log_path or not Path(log_path).exists():
            return False

        try:
            mtime = Path(log_path).stat().st_mtime
            age = time.time() - mtime
            return age > threshold_seconds
        except Exception:
            return False

    def _get_next_recovery_strategy(self, task_id: str | None) -> str:
        """Get the next OOM recovery strategy from policy."""
        # Get current strategy count from task metadata
        if task_id:
            task = self.store.get_task(task_id)
            if task:
                attempts = int(task.get("attempts", 0))
                strategies = [
                    "gradient_accumulation",
                    "reduce_batch_size",
                    "activation_checkpointing",
                    "amp",
                    "reduce_workers",
                ]
                idx = min(attempts, len(strategies) - 1)
                return strategies[idx]
        return "gradient_accumulation"

    def check_training_health(self, task: dict) -> dict:
        """Check training health indicators from logs."""
        health = {
            "nan_detected": False,
            "inf_detected": False,
            "loss_stalling": False,
            "dataloader_stall": False,
            "issues": [],
        }

        log_path = task.get("log_path")
        if not log_path or not Path(log_path).exists():
            return health

        try:
            content = Path(log_path).read_text(errors="ignore")

            # Check for NaN/Inf
            if re.search(r"\bnan\b", content, re.IGNORECASE):
                health["nan_detected"] = True
                health["issues"].append("NaN detected in training")

            if re.search(r"\binf\b", content, re.IGNORECASE):
                health["inf_detected"] = True
                health["issues"].append("Inf detected in training")

            # Check for loss stalling (loss not decreasing over last N lines)
            loss_values = re.findall(r"loss[:\s=]+([0-9.]+)", content, re.IGNORECASE)
            if len(loss_values) >= 10:
                recent = [float(v) for v in loss_values[-10:]]
                if max(recent) - min(recent) < 0.001:
                    health["loss_stalling"] = True
                    health["issues"].append("Loss appears to be stalling")

            # Check for dataloader issues
            if re.search(r"DataLoader.*stuck|timeout.*dataloader", content, re.IGNORECASE):
                health["dataloader_stall"] = True
                health["issues"].append("DataLoader appears stuck")

            # Check for gradient explosion
            if re.search(r"gradient.*nan|grad.*inf|exploding.*gradient", content, re.IGNORECASE):
                health["issues"].append("Gradient explosion detected")

            # Check for OOM patterns
            if re.search(r"out.*of.*memory|OOM", content, re.IGNORECASE):
                health["issues"].append("OOM detected")

        except Exception:
            pass

        return health

    def get_system_info(self) -> dict:
        """Get overall system resource information."""
        info = {
            "cpu_percent": 0,
            "memory_used_pct": 0,
            "disk_free_gb": 0,
            "gpu": self.get_gpu_info(),
        }

        try:
            # CPU/Memory via psutil-like output
            result = subprocess.run(
                ["free", "-b"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 3:
                        total = int(parts[1])
                        used = int(parts[2])
                        info["memory_used_pct"] = round(used / total * 100, 1)
        except Exception:
            pass

        # Disk info
        if self.project_root:
            try:
                import shutil
                usage = shutil.disk_usage(str(self.project_root))
                info["disk_free_gb"] = round(usage.free / 1024**3, 1)
            except Exception:
                pass

        return info

    def terminate_running(self) -> list[int]:
        """Terminate all running tasks."""
        stopped: list[int] = []
        for task in self.store.list_tasks({"RUNNING"}):
            pid = task.get("pid")
            if pid and self.process_manager.is_alive(pid):
                self.process_manager.terminate(int(pid))
                stopped.append(int(pid))
            self.store.record_event("PROCESS_STOPPED", task["id"], {"pid": pid})
        return stopped

    def record_health_metrics(self, task_id: str, health: dict) -> None:
        """Record health metrics to event log."""
        self.store.record_event("TRAINING_HEALTH", task_id, health)
