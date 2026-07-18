"""OSTAR configuration management.

Handles loading, validation, and schema enforcement for OSTAR soak runs.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import constants as _C

# Add project root to path for schema import
_THIS = Path(__file__).resolve()
_PKG = _THIS.parent.parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

try:
    import jsonschema as _jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


@dataclass
class OSTARConfig:
    """Validated OSTAR configuration."""
    # Timing
    timezone: str = _C.DEFAULT_TIMEZONE
    start_time: str | None = None   # ISO datetime or HH:MM local
    end_time: str | None = None     # ISO datetime or HH:MM local
    duration_seconds: int = _C.DEFAULT_DURATION_SECONDS

    # Auto-repair
    auto_repair_level: str = "safe"  # none | safe | full
    max_repairs: int = _C.DEFAULT_MAX_REPAIRS
    max_retries_per_bug: int = _C.DEFAULT_MAX_RETRIES_PER_BUG

    # Hardware safety
    gpu_temperature_limit: int | None = None  # overrides default
    disk_reserve_gb: float = _C.DEFAULT_DISK_RESERVE_GB
    gpu_memory_reserve_pct: float = _C.DEFAULT_GPU_MEMORY_RESERVE_PCT

    # Stress test toggles
    run_ci_stress: bool = True
    run_scheduler_stress: bool = True
    run_gpu_stress: bool = True
    run_batch_boundary: bool = True
    run_dataloader_stress: bool = True
    run_metric_consistency: bool = True
    run_resource_leak: bool = True

    # CI levels
    ci_level_1_fast: bool = True
    ci_level_2_full: bool = False  # more expensive, off by default for soak

    # Reporting
    verbose: bool = False
    dry_run: bool = False

    # Internal
    soak_root: Path | None = None
    project_root: Path | None = None

    def resolved_duration_seconds(self) -> int:
        """Effective duration: explicit seconds takes priority over time window."""
        return self.duration_seconds

    def resolved_end_time_utc(self, now: datetime) -> datetime:
        """Compute end_time as UTC datetime."""
        import zoneinfo
        tz = zoneinfo.ZoneInfo(self.timezone)
        if self.end_time:
            try:
                # Try parsing as full ISO
                end_dt = datetime.fromisoformat(self.end_time)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=tz)
                return end_dt.astimezone(timezone.utc)
            except ValueError:
                pass
            # Try HH:MM format
            match = re.match(r"(\d{1,2}):(\d{2})", self.end_time)
            if match:
                hour, minute = int(match.group(1)), int(match.group(2))
                end_today = now.astimezone(tz).replace(
                    hour=hour, minute=minute, second=0, microsecond=0,
                )
                end_utc = end_today.astimezone(timezone.utc)
                if end_utc <= now.astimezone(timezone.utc):
                    end_utc = end_utc.replace(day=end_utc.day + 1)
                return end_utc
        # Fall back to duration
        return datetime.fromtimestamp(
            now.timestamp() + self.duration_seconds, tz=timezone.utc,
        )

    def to_dict(self) -> dict:
        return {
            "timezone": self.timezone,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "auto_repair_level": self.auto_repair_level,
            "max_repairs": self.max_repairs,
            "max_retries_per_bug": self.max_retries_per_bug,
            "gpu_temperature_limit": self.gpu_temperature_limit,
            "disk_reserve_gb": self.disk_reserve_gb,
            "gpu_memory_reserve_pct": self.gpu_memory_reserve_pct,
            "run_ci_stress": self.run_ci_stress,
            "run_scheduler_stress": self.run_scheduler_stress,
            "run_gpu_stress": self.run_gpu_stress,
            "run_batch_boundary": self.run_batch_boundary,
            "run_dataloader_stress": self.run_dataloader_stress,
            "run_metric_consistency": self.run_metric_consistency,
            "run_resource_leak": self.run_resource_leak,
            "ci_level_1_fast": self.ci_level_1_fast,
            "ci_level_2_full": self.ci_level_2_full,
            "verbose": self.verbose,
            "dry_run": self.dry_run,
            "soak_root": str(self.soak_root) if self.soak_root else None,
            "project_root": str(self.project_root) if self.project_root else None,
        }

    @classmethod
    def from_args(cls, args) -> OSTARConfig:
        """Build config from parsed argparse namespace or dict."""
        cfg = cls()
        # Handle both argparse.Namespace and plain dict
        def _get(key: str):
            if isinstance(args, dict):
                return args.get(key)
            return getattr(args, key, None)

        duration = _get("duration")
        if duration:
            cfg.duration_seconds = cls._parse_duration(str(duration))
        disk_reserve = _get("disk_reserve")
        if disk_reserve:
            cfg.disk_reserve_gb = float(disk_reserve)
        max_retries = _get("max_retries")
        if max_retries:
            cfg.max_retries_per_bug = int(max_retries)
        gpu_t = _get("gpu_temperature_limit")
        if gpu_t is not None:
            cfg.gpu_temperature_limit = int(gpu_t)
        auto_rep = _get("auto_repair_level")
        if auto_rep:
            cfg.auto_repair_level = auto_rep
        max_rep = _get("max_repairs")
        if max_rep is not None:
            cfg.max_repairs = int(max_rep)
        tz = _get("timezone")
        if tz:
            cfg.timezone = tz
        project = _get("project")
        if project:
            cfg.project_root = Path(project).resolve()
        soak_root = _get("soak_root")
        if soak_root:
            cfg.soak_root = Path(soak_root).resolve()
        elif cfg.project_root:
            cfg.soak_root = cfg.project_root / "soak"
        return cfg

    @staticmethod
    def _parse_duration(s: str) -> int:
        """Parse duration like '8h', '30m', '480m', '28800s', '28800'."""
        s = s.strip().lower()
        if s.isdigit():
            return int(s)
        m = re.match(r"(\d+(?:\.\d+)?)\s*([hms])?", s)
        if not m:
            return _C.DEFAULT_DURATION_SECONDS
        value, unit = float(m.group(1)), (m.group(2) or "s")
        multipliers = {"h": 3600, "m": 60, "s": 1}
        return int(value * multipliers[unit])

    def validate(self) -> list[str]:
        """Return list of validation errors (empty if valid)."""
        errors = []
        if self.auto_repair_level not in _C.AUTO_REPAIR_LEVELS:
            errors.append(
                f"auto_repair_level must be one of {sorted(_C.AUTO_REPAIR_LEVELS)}, "
                f"got {self.auto_repair_level!r}",
            )
        if self.max_repairs < 0:
            errors.append(f"max_repairs must be ≥ 0, got {self.max_repairs}")
        if self.max_retries_per_bug < 1:
            errors.append(
                f"max_retries_per_bug must be ≥ 1, got {self.max_retries_per_bug}",
            )
        if self.disk_reserve_gb < 1:
            errors.append(
                f"disk_reserve_gb must be ≥ 1, got {self.disk_reserve_gb}",
            )
        if self.gpu_temperature_limit is not None:
            if self.gpu_temperature_limit < 30 or self.gpu_temperature_limit > 110:
                errors.append(
                    f"gpu_temperature_limit must be 30-110°C, got {self.gpu_temperature_limit}",
                )
        try:
            ZoneInfo(self.timezone)
        except Exception:
            errors.append(f"invalid timezone: {self.timezone!r}")
        return errors


def load_config(path: Path) -> OSTARConfig:
    """Load OSTAR config from a YAML or JSON file."""
    try:
        import yaml
    except ImportError:
        yaml = None

    if path.suffix in (".yaml", ".yml") and yaml:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    elif path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        # Try both
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            if yaml:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            else:
                data = {}

    cfg = OSTARConfig()
    for k, v in data.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)

    if "duration" in data:
        cfg.duration_seconds = OSTARConfig._parse_duration(str(data["duration"]))
    if "disk_reserve" in data:
        cfg.disk_reserve_gb = float(data["disk_reserve"])

    return cfg


def save_config(config: OSTARConfig, path: Path) -> None:
    """Save OSTAR config to a JSON file."""
    path.write_text(
        json.dumps(config.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
