"""Hardware safety monitor for OSTAR.

Monitors GPU temperature, GPU memory, CPU RAM, disk space, and system
health. Enforces hardware limits and prevents GPU damage.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from . import constants as _C


@dataclass
class HardwareSnapshot:
    """Point-in-time snapshot of all hardware metrics."""
    timestamp_utc: str
    gpu_available: bool = False
    gpu_count: int = 0
    gpu_names: list[str] = field(default_factory=list)
    gpu_temps_c: list[int] = field(default_factory=list)
    gpu_power_w: list[float] = field(default_factory=list)
    gpu_utilization_pct: list[int] = field(default_factory=list)
    gpu_memory_allocated_gb: list[float] = field(default_factory=list)
    gpu_memory_reserved_gb: list[float] = field(default_factory=list)
    gpu_memory_total_gb: list[float] = field(default_factory=list)
    gpu_memory_used_pct: list[float] = field(default_factory=list)
    cpu_memory_used_pct: float = 0.0
    cpu_memory_total_gb: float = 0.0
    cpu_memory_available_gb: float = 0.0
    disk_free_gb: float = 0.0
    disk_total_gb: float = 0.0
    disk_used_pct: float = 0.0
    swap_used_pct: float = 0.0
    load_avg_1m: float = 0.0
    open_file_handles: int = 0
    child_processes: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def max_gpu_temp_c(self) -> int:
        return max(self.gpu_temps_c) if self.gpu_temps_c else 0

    def max_gpu_memory_pct(self) -> float:
        return max(self.gpu_memory_used_pct) if self.gpu_memory_used_pct else 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp_utc": self.timestamp_utc,
            "gpu_available": self.gpu_available,
            "gpu_count": self.gpu_count,
            "gpu_names": self.gpu_names,
            "gpu_temps_c": self.gpu_temps_c,
            "gpu_power_w": self.gpu_power_w,
            "gpu_utilization_pct": self.gpu_utilization_pct,
            "gpu_memory_allocated_gb": self.gpu_memory_allocated_gb,
            "gpu_memory_reserved_gb": self.gpu_memory_reserved_gb,
            "gpu_memory_total_gb": self.gpu_memory_total_gb,
            "gpu_memory_used_pct": self.gpu_memory_used_pct,
            "cpu_memory_used_pct": self.cpu_memory_used_pct,
            "cpu_memory_total_gb": self.cpu_memory_total_gb,
            "cpu_memory_available_gb": self.cpu_memory_available_gb,
            "disk_free_gb": self.disk_free_gb,
            "disk_total_gb": self.disk_total_gb,
            "disk_used_pct": self.disk_used_pct,
            "swap_used_pct": self.swap_used_pct,
            "load_avg_1m": self.load_avg_1m,
            "open_file_handles": self.open_file_handles,
            "child_processes": self.child_processes,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class HardwarePolicy:
    """Hardware safety limits. Read from OSTAR config."""
    gpu_warn_temp_c: int = _C.DEFAULT_GPU_WARN_TEMP_C
    gpu_critical_temp_c: int = _C.DEFAULT_GPU_CRITICAL_TEMP_C
    disk_reserve_gb: float = _C.DEFAULT_DISK_RESERVE_GB
    gpu_memory_reserve_pct: float = _C.DEFAULT_GPU_MEMORY_RESERVE_PCT
    max_consecutive_temp_exceedances: int = 3


class HardwareMonitor:
    """System-wide hardware monitoring with GPU safety enforcement."""

    _GPU_VENDOR_TEMP_MAX = {
        "nvidia": 83,   # conservative; NVIDIA Fermi+ max is 83°C below Boost 3.0
        "amd": 90,
    }
    _CACHE_TTL = 5.0  # seconds

    def __init__(
        self,
        project_root: Path | None = None,
        policy: HardwarePolicy | None = None,
    ):
        self.project_root = project_root
        self.policy = policy or HardwarePolicy()
        self._gpu_cache: dict[int, dict] = {}
        self._cache_time: float = 0
        self._consecutive_temp_exceedances: int = 0

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def snapshot(self) -> HardwareSnapshot:
        """Capture a full hardware snapshot."""
        now_str = datetime.now(timezone.utc).isoformat()
        snap = HardwareSnapshot(timestamp_utc=now_str)
        snap.gpu_available, snap.gpu_count, snap.gpu_names = self._gpu_availability()

        if snap.gpu_available:
            self._update_gpu_cache()
            self._fill_gpu_snapshot(snap)

        self._fill_cpu_snapshot(snap)
        self._fill_disk_snapshot(snap)
        self._fill_system_snapshot(snap)

        self._check_warnings(snap)
        return snap

    def check(self) -> tuple[bool, list[str]]:
        """Return (safe, list_of_violations)."""
        snap = self.snapshot()
        violations: list[str] = []

        # GPU temperature
        max_temp = snap.max_gpu_temp_c()
        if max_temp >= self.policy.gpu_critical_temp_c:
            violations.append(
                f"GPU critical temp {max_temp}°C >= {self.policy.gpu_critical_temp_c}°C"
            )
        elif max_temp >= self.policy.gpu_warn_temp_c:
            violations.append(
                f"GPU warn temp {max_temp}°C >= {self.policy.gpu_warn_temp_c}°C"
            )

        # Disk space
        if snap.disk_free_gb < self.policy.disk_reserve_gb:
            violations.append(
                f"Disk free {snap.disk_free_gb:.1f}GB < reserve {self.policy.disk_reserve_gb}GB"
            )

        # GPU memory
        max_mem_pct = snap.max_gpu_memory_pct()
        if max_mem_pct > (100 - self.policy.gpu_memory_reserve_pct):
            violations.append(
                f"GPU memory {max_mem_pct:.1f}% used (headroom {self.policy.gpu_memory_reserve_pct}%)"
            )

        safe = len(violations) == 0
        return safe, violations

    def check_and_record(self) -> tuple[bool, HardwareSnapshot, list[str]]:
        """Snapshot, check, and record exceedances. Returns (safe, snap, violations)."""
        snap = self.snapshot()
        safe, violations = self.check()
        if not safe:
            max_temp = snap.max_gpu_temp_c()
            if max_temp >= self.policy.gpu_critical_temp_c:
                self._consecutive_temp_exceedances += 1
            else:
                self._consecutive_temp_exceedances = 0
        else:
            self._consecutive_temp_exceedances = 0
        return safe, snap, violations

    def gpu_safe(self) -> bool:
        """True if GPU temp is below critical threshold."""
        snap = self.snapshot()
        return snap.max_gpu_temp_c() < self.policy.gpu_critical_temp_c

    def pause_required(self) -> bool:
        """True if GPU temp exceeded critical threshold too many times consecutively."""
        return self._consecutive_temp_exceedances >= self.policy.max_consecutive_temp_exceedances

    def resume_allowed(self) -> bool:
        """True if GPU temp has cooled below warning threshold."""
        snap = self.snapshot()
        return snap.max_gpu_temp_c() < self.policy.gpu_warn_temp_c

    def vendor_max_temp(self, vendor: str = "nvidia") -> int:
        """Return the manufacturer's maximum safe temperature for the GPU."""
        return self._GPU_VENDOR_TEMP_MAX.get(vendor.lower(), 83)

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    def _gpu_availability(self) -> tuple[bool, int, list[str]]:
        if not TORCH_AVAILABLE:
            return False, 0, []
        try:
            if not torch.cuda.is_available():
                return False, 0, []
            count = torch.cuda.device_count()
            names = [torch.cuda.get_device_name(i) for i in range(count)]
            return True, count, names
        except Exception:
            return False, 0, []

    def _update_gpu_cache(self) -> None:
        now = time.time()
        if (now - self._cache_time) < self._CACHE_TTL and self._gpu_cache:
            return
        self._gpu_cache = {}
        if not TORCH_AVAILABLE:
            return
        try:
            for i in range(torch.cuda.device_count()):
                mem_alloc = torch.cuda.memory_allocated(i) / (1024 ** 3)
                mem_resv = torch.cuda.memory_reserved(i) / (1024 ** 3)
                mem_total = torch.cuda.get_device_properties(i).total_memory / (1024 ** 3)
                self._gpu_cache[i] = {
                    "allocated_gb": round(mem_alloc, 3),
                    "reserved_gb": round(mem_resv, 3),
                    "total_gb": round(mem_total, 3),
                    "used_pct": round(mem_resv / mem_total * 100, 2) if mem_total else 0,
                }
        except Exception:
            pass
        self._cache_time = now

    def _fill_gpu_snapshot(self, snap: HardwareSnapshot) -> None:
        self._update_gpu_cache()
        for i in range(snap.gpu_count):
            dev = self._gpu_cache.get(i, {})
            snap.gpu_memory_allocated_gb.append(dev.get("allocated_gb", 0.0))
            snap.gpu_memory_reserved_gb.append(dev.get("reserved_gb", 0.0))
            snap.gpu_memory_total_gb.append(dev.get("total_gb", 0.0))
            snap.gpu_memory_used_pct.append(dev.get("used_pct", 0.0))

        # Temperature via nvidia-smi
        temp_info = self._nvidia_smi_query()
        if temp_info:
            snap.gpu_temps_c = temp_info.get("temps_c", [])
            snap.gpu_power_w = temp_info.get("power_w", [])
            snap.gpu_utilization_pct = temp_info.get("util_pct", [])

    def _nvidia_smi_query(self) -> dict | None:
        """Query nvidia-smi for temperature, power, utilization. Returns None on failure."""
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=index,temperature.gpu,power.draw,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
            temps_c: list[int] = []
            power_w: list[float] = []
            util_pct: list[int] = []
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    try:
                        temps_c.append(int(parts[1]))
                        power_w.append(float(parts[2]))
                        util_pct.append(int(parts[3]))
                    except ValueError:
                        pass
            return {"temps_c": temps_c, "power_w": power_w, "util_pct": util_pct}
        except Exception:
            return None

    def _fill_cpu_snapshot(self, snap: HardwareSnapshot) -> None:
        try:
            meminfo = Path("/proc/meminfo").read_text(errors="ignore")
            lines = meminfo.splitlines()
            mem: dict[str, int] = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        mem[parts[0].rstrip(":")] = int(parts[1])
                    except ValueError:
                        pass
            total_kb = mem.get("MemTotal", 0)
            available_kb = mem.get("MemAvailable", mem.get("MemFree", 0))
            used_kb = total_kb - available_kb
            if total_kb:
                snap.cpu_memory_used_pct = round(used_kb / total_kb * 100, 1)
            snap.cpu_memory_total_gb = round(total_kb / (1024 ** 2), 2)
            snap.cpu_memory_available_gb = round(available_kb / (1024 ** 2), 2)

            # Swap
            swap_total_kb = mem.get("SwapTotal", 0)
            swap_free_kb = mem.get("SwapFree", 0)
            if swap_total_kb:
                snap.swap_used_pct = round(
                    (swap_total_kb - swap_free_kb) / swap_total_kb * 100, 1
                )
        except Exception:
            pass

    def _fill_disk_snapshot(self, snap: HardwareSnapshot) -> None:
        if not self.project_root:
            return
        try:
            import shutil as _shutil
            usage = _shutil.disk_usage(str(self.project_root))
            snap.disk_free_gb = round(usage.free / (1024 ** 3), 2)
            snap.disk_total_gb = round(usage.total / (1024 ** 3), 2)
            if usage.total:
                snap.disk_used_pct = round(usage.used / usage.total * 100, 1)
        except Exception:
            pass

    def _fill_system_snapshot(self, snap: HardwareSnapshot) -> None:
        # Load average
        try:
            loadavg = Path("/proc/loadavg").read_text(errors="ignore").split()
            if loadavg:
                snap.load_avg_1m = float(loadavg[0])
        except Exception:
            pass

        # Open file handles
        try:
            result = subprocess.run(
                ["ls", "/proc/self/fd"], capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                snap.open_file_handles = len(result.stdout.splitlines())
        except Exception:
            pass

        # Child processes
        try:
            result = subprocess.run(
                ["pgrep", "-c", "-P", str(os.getpid())],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                snap.child_processes = int(result.stdout.strip())
        except Exception:
            pass

    def _check_warnings(self, snap: HardwareSnapshot) -> None:
        max_temp = snap.max_gpu_temp_c()
        if max_temp >= self.policy.gpu_critical_temp_c:
            snap.errors.append(
                f"GPU CRITICAL temperature {max_temp}°C (limit {self.policy.gpu_critical_temp_c}°C)"
            )
        elif max_temp >= self.policy.gpu_warn_temp_c:
            snap.warnings.append(
                f"GPU high temperature {max_temp}°C (warn {self.policy.gpu_warn_temp_c}°C)"
            )

        if snap.disk_free_gb < self.policy.disk_reserve_gb:
            snap.errors.append(
                f"Disk free {snap.disk_free_gb:.1f}GB below reserve {self.policy.disk_reserve_gb}GB"
            )

        if snap.cpu_memory_used_pct > 95:
            snap.warnings.append(
                f"CPU RAM critical: {snap.cpu_memory_used_pct:.1f}% used"
            )
        elif snap.cpu_memory_used_pct > 85:
            snap.warnings.append(
                f"CPU RAM high: {snap.cpu_memory_used_pct:.1f}% used"
            )

        if snap.swap_used_pct > 50:
            snap.warnings.append(f"Swap usage {snap.swap_used_pct:.1f}%")
