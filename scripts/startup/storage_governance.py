"""Disk and artifact governance for reproctl."""

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DiskPolicy:
    warning_free_gb: int = 50
    stop_free_gb: int = 20
    emergency_free_gb: int = 10


@dataclass
class RetentionPolicy:
    raw_data: str = "never_delete"
    best_checkpoint: str = "keep"
    last_checkpoint: str = "keep"
    intermediate_checkpoints: int = 3
    failed_run_logs: str = "keep_until_final_audit"
    generated_plots: str = "regenerable"
    cache: str = "removable"


def get_free_gb(path: Path) -> float:
    """Return free disk space in GB."""
    try:
        stat = shutil.disk_usage(path)
        return stat.free / (1024**3)
    except OSError:
        return float("inf")


def check_disk_policy(
    project_root: Path, disk_policy: DiskPolicy | None = None, config: dict | None = None
) -> dict:
    """Check disk space against policy."""
    dp = disk_policy or DiskPolicy()
    if config and "disk_policy" in config:
        dp = DiskPolicy(**config["disk_policy"])

    free_gb = get_free_gb(project_root)

    if free_gb <= dp.emergency_free_gb:
        status = "EMERGENCY"
        message = f"Emergency: only {free_gb:.1f} GB free (threshold: {dp.emergency_free_gb} GB)"
    elif free_gb <= dp.stop_free_gb:
        status = "STOP"
        message = f"Stop: only {free_gb:.1f} GB free (threshold: {dp.stop_free_gb} GB)"
    elif free_gb <= dp.warning_free_gb:
        status = "WARNING"
        message = f"Warning: only {free_gb:.1f} GB free (threshold: {dp.warning_free_gb} GB)"
    else:
        status = "OK"
        message = f"OK: {free_gb:.1f} GB free"

    return {
        "status": status,
        "free_gb": round(free_gb, 2),
        "warning_threshold_gb": dp.warning_free_gb,
        "stop_threshold_gb": dp.stop_free_gb,
        "emergency_threshold_gb": dp.emergency_free_gb,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def scan_checkpoints(project_root: Path) -> list[dict]:
    """List all checkpoints with size and age."""
    checkpoints = []
    ckpt_dirs = [
        project_root / "checkpoints",
        project_root / ".repro" / "checkpoints",
        project_root / "experiments",
    ]
    for d in ckpt_dirs:
        if not d.exists():
            continue
        for f in d.rglob("*.pt"):
            stat = f.stat()
            checkpoints.append(
                {
                    "path": str(f.relative_to(project_root)),
                    "size_mb": round(stat.st_size / (1024**2), 2),
                    "age_days": (
                        datetime.now(timezone.utc)
                        - datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    ).days,
                }
            )
    checkpoints.sort(key=lambda x: x["age_days"], reverse=True)
    return checkpoints


def plan_cleanup(
    project_root: Path, retention: RetentionPolicy | None = None, dry_run: bool = True
) -> dict:
    """Generate a cleanup plan without executing it.

    Args:
        project_root: project directory
        retention: retention policy
        dry_run: if True, only generate plan; if False, execute

    Returns dict with files_to_delete, space_to_free, warnings.
    """
    rp = retention or RetentionPolicy()
    if isinstance(rp, dict):
        rp = RetentionPolicy(**rp)

    to_delete = []
    warnings = []

    # Scan for intermediate checkpoints (keep best, last, and intermediate_checkpoints)
    checkpoints = scan_checkpoints(project_root)
    if checkpoints:
        # Find best and last by age
        oldest = checkpoints[-1] if checkpoints else None
        newest = checkpoints[0] if checkpoints else None

        # Keep all named special checkpoints
        special_names = {"best", "last", "final"}

        if len(checkpoints) > 2 + rp.intermediate_checkpoints:
            # Remove oldest, keep newest 2 + intermediate
            keep_count = 2 + rp.intermediate_checkpoints
            for ckpt in checkpoints[keep_count:]:
                if not any(sn in ckpt["path"].lower() for sn in special_names):
                    to_delete.append(
                        {
                            "path": ckpt["path"],
                            "size_mb": ckpt["size_mb"],
                            "age_days": ckpt["age_days"],
                            "reason": "intermediate checkpoint beyond retention limit",
                            "type": "checkpoint",
                        }
                    )

    # Plan for cache cleanup
    cache_dirs = [
        project_root / ".cache",
        project_root / ".repro" / "cache",
    ]
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            for f in cache_dir.rglob("*"):
                if f.is_file():
                    to_delete.append(
                        {
                            "path": str(f.relative_to(project_root)),
                            "size_mb": round(f.stat().st_size / (1024**2), 2),
                            "age_days": (
                                datetime.now(timezone.utc)
                                - datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                            ).days,
                            "reason": "cache (removable)",
                            "type": "cache",
                        }
                    )

    # Plan for failed run logs
    if rp.failed_run_logs == "keep_until_final_audit":
        # Only plan to delete if final audit is complete
        audit_state = project_root / ".repro" / "audit" / "STATE.json"
        if not audit_state.exists():
            warnings.append("Final audit not complete — not cleaning failed run logs")

    space_to_free_mb = sum(item["size_mb"] for item in to_delete)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "files_to_delete": to_delete,
        "total_files": len(to_delete),
        "space_to_free_mb": round(space_to_free_mb, 2),
        "space_to_free_gb": round(space_to_free_mb / 1024, 2),
        "warnings": warnings,
        "note": "Plan generated only — execute with --approved-plan to actually delete",
    }

    if not dry_run:
        # Actually execute the plan
        executed = []
        for item in to_delete:
            p = project_root / item["path"]
            try:
                p.unlink()
                executed.append(item)
            except Exception as e:
                warnings.append(f"Failed to delete {item['path']}: {e}")
        result["files_deleted"] = len(executed)
        result["files_failed"] = len(to_delete) - len(executed)

    return result


def apply_retention_config(project_root: Path, config: dict) -> dict:
    """Apply retention and disk_policy from config file."""
    rp_dict = config.get("retention", {})
    dp_dict = config.get("disk_policy", {})

    rp = RetentionPolicy(**rp_dict) if rp_dict else RetentionPolicy()
    dp = DiskPolicy(**dp_dict) if dp_dict else DiskPolicy()

    disk_status = check_disk_policy(project_root, dp, config)

    return {
        "disk_status": disk_status,
        "retention_policy": {
            "raw_data": rp.raw_data,
            "best_checkpoint": rp.best_checkpoint,
            "last_checkpoint": rp.last_checkpoint,
            "intermediate_checkpoints": rp.intermediate_checkpoints,
            "failed_run_logs": rp.failed_run_logs,
            "generated_plots": rp.generated_plots,
            "cache": rp.cache,
        },
        "cleanup_plan": plan_cleanup(project_root, rp, dry_run=True),
    }
