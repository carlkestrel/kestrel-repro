"""
Enhanced Recovery Manager - Training checkpoint integrity verification and recovery.

This module extends the base RecoveryManager with:
- Checkpoint integrity verification (PyTorch checkpoint validation)
- Metric continuity validation (no mixing pre/post recovery)
- Last valid checkpoint detection
- Recovery chain validation
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckpointIntegrityError(Exception):
    """Raised when checkpoint integrity check fails."""

    pass


class RecoveryManager:
    """Enhanced recovery with checkpoint integrity and metric continuity."""

    def __init__(self, project_root: str | Path, store, journal, process_manager):
        self.project_root = Path(project_root).resolve()
        self.store = store
        self.journal = journal
        self.process_manager = process_manager

    def recover(self) -> dict:
        """Enhanced recovery with checkpoint verification."""
        repaired = self.journal.repair_from(self.store.events(limit=1_000_000))
        alive: list[str] = []
        verification_ready: list[str] = []
        orphaned: list[str] = []
        checkpoint_issues: list[dict] = []

        for task in self.store.list_tasks({"RUNNING"}):
            pid = task.get("pid")
            if self.process_manager.is_alive(pid):
                alive.append(task["id"])
                continue

            # Check checkpoint integrity
            checkpoint = task.get("checkpoint")
            checkpoint_path = self.project_root / checkpoint if checkpoint else None

            if checkpoint_path and checkpoint_path.exists():
                # Verify checkpoint integrity
                integrity = self.verify_checkpoint(checkpoint_path)
                if not integrity["valid"]:
                    checkpoint_issues.append(
                        {
                            "task_id": task["id"],
                            "checkpoint": str(checkpoint_path),
                            "reason": integrity.get("reason", "unknown"),
                        }
                    )
                    # Still mark for verification but flag the issue
                    self.store.record_event("CHECKPOINT_INTEGRITY_WARNING", task["id"], integrity)

            checkpoint_exists = bool(checkpoint and checkpoint_path and checkpoint_path.exists())

            self.store.transition(
                task["id"],
                "VERIFYING",
                expected="RUNNING",
                fields={"pid": None},
                event_type="TASK_RECOVERED",
            )
            verification_ready.append(task["id"])

            if not checkpoint_exists:
                orphaned.append(task["id"])

        # Recover orphaned VERIFYING tasks
        for task in self.store.list_tasks({"VERIFYING"}):
            if not task.get("pid"):
                with self.store.transaction() as conn:
                    conn.execute(
                        "UPDATE tasks SET status='READY', failure_reason=NULL, "
                        "finished_at=NULL, updated_at=? WHERE id=?",
                        (utc_now(), task["id"]),
                    )
                    self.store._record_event_tx(
                        conn,
                        "TASK_ORPHAN_CLEARED",
                        task["id"],
                        {
                            "from": "VERIFYING",
                            "to": "READY",
                            "reason": "orphan_VERIFYING—no pid on resume",
                        },
                    )

        summary = {
            "journal_records_repaired": repaired,
            "running_processes": alive,
            "verification_ready": verification_ready,
            "missing_checkpoint": orphaned,
            "checkpoint_issues": checkpoint_issues,
            "controller_heartbeat_missing": not self.store.heartbeat_path.exists(),
        }
        self.store.record_event("RECOVERY_COMPLETE", payload=summary)
        return summary

    def verify_checkpoint(self, checkpoint_path: Path) -> dict:
        """
        Verify checkpoint integrity.

        Checks:
        1. File exists and is readable
        2. File size is reasonable (not empty, not suspiciously small)
        3. PyTorch checkpoint loads successfully (if available)
        4. Contains expected keys (model_state, optimizer_state, etc.)
        """
        result = {
            "path": str(checkpoint_path),
            "valid": False,
            "reason": None,
            "details": {},
        }

        if not checkpoint_path.exists():
            result["reason"] = "file does not exist"
            return result

        # Check file size
        size = checkpoint_path.stat().st_size
        if size < 100:
            result["reason"] = "file too small"
            return result

        result["details"]["size_bytes"] = size

        # Try to load with PyTorch
        try:
            import torch

            # Check if it's a PyTorch checkpoint
            try:
                # Try loading as full checkpoint
                ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

                # Verify expected keys
                expected_keys = ["model_state_dict", "optimizer_state_dict"]
                found_keys = []
                missing_keys = []

                for key in expected_keys:
                    if (
                        key in ckpt or any(key in k for k in ckpt.keys())
                        if isinstance(ckpt, dict)
                        else False
                    ):
                        found_keys.append(key)
                    else:
                        missing_keys.append(key)

                result["details"]["keys_found"] = found_keys
                result["details"]["keys_missing"] = missing_keys

                # Check for epoch info
                if "epoch" in ckpt:
                    result["details"]["epoch"] = ckpt["epoch"]
                if "step" in ckpt:
                    result["details"]["step"] = ckpt["step"]

                # Calculate checksum
                result["details"]["checksum"] = self._file_checksum(checkpoint_path)

                result["valid"] = True
                result["reason"] = "loaded successfully"

            except Exception as e:
                # Try loading as state dict only
                try:
                    state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
                    result["details"]["type"] = "state_dict"
                    result["details"]["num_params"] = (
                        len(state_dict) if isinstance(state_dict, dict) else 0
                    )
                    result["valid"] = True
                    result["reason"] = "state_dict loaded successfully"
                except Exception as e2:
                    result["reason"] = f"failed to load: {e}, {e2}"

        except ImportError:
            # No PyTorch - basic file check only
            result["details"]["type"] = "no_torch"
            result["valid"] = size > 1000  # Basic size heuristic
            result["reason"] = "no PyTorch, basic size check"

        return result

    def find_last_valid_checkpoint(self, checkpoints_dir: Path) -> Path | None:
        """
        Find the last valid checkpoint in a directory.

        Checks for files matching common checkpoint patterns and returns
        the most recently modified valid checkpoint.
        """
        if not checkpoints_dir.exists():
            return None

        # Common checkpoint patterns
        patterns = ["*.pth", "*.pt", "*checkpoint*.pth", "*checkpoint*.pt", "*.ckpt"]

        candidates = []
        for pattern in patterns:
            candidates.extend(checkpoints_dir.glob(pattern))

        if not candidates:
            return None

        # Sort by modification time (most recent first)
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Try each until we find a valid one
        for candidate in candidates:
            integrity = self.verify_checkpoint(candidate)
            if integrity["valid"]:
                return candidate

        return None

    def get_recovery_info(self, task: dict) -> dict:
        """Get recovery information for a task."""
        recovery = {
            "task_id": task["id"],
            "has_checkpoint": False,
            "checkpoint_valid": False,
            "checkpoint_path": None,
            "recovery_command": None,
            "metrics_continuity": "unknown",
        }

        checkpoint = task.get("checkpoint")
        if checkpoint:
            checkpoint_path = self.project_root / checkpoint
            recovery["checkpoint_path"] = str(checkpoint_path)
            recovery["has_checkpoint"] = checkpoint_path.exists()

            if checkpoint_path.exists():
                integrity = self.verify_checkpoint(checkpoint_path)
                recovery["checkpoint_valid"] = integrity["valid"]
                recovery["checkpoint_epoch"] = integrity.get("details", {}).get("epoch")
                recovery["checkpoint_step"] = integrity.get("details", {}).get("step")

                # Build recovery command
                if integrity["valid"]:
                    recovery["recovery_command"] = self._build_recovery_command(
                        task, checkpoint_path
                    )

        # Check metric continuity
        run_id = task.get("run_id")
        if run_id:
            from .evidence_manager import EvidenceManager

            em = EvidenceManager(self.project_root)
            runs = em.list_runs(task_id=task["id"])
            if len(runs) > 1:
                recovery["metrics_continuity"] = "possible_mixing"
            else:
                recovery["metrics_continuity"] = "ok"

        return recovery

    def _build_recovery_command(self, task: dict, checkpoint_path: Path) -> str:
        """Build the recovery command for a task."""
        # This would be task-specific, but provide a template
        command = task.get("command", "")
        if command:
            # Add checkpoint resume flag if not present
            if "--resume" not in command and "--checkpoint" not in command:
                return f"{command} --resume {checkpoint_path}"
            elif "--checkpoint" not in command:
                return f"{command} --checkpoint {checkpoint_path}"
        return f"# Manual recovery required from {checkpoint_path}"

    def _file_checksum(self, path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()[:16]

    def validate_metric_continuity(self, task_id: str) -> dict:
        """
        Validate that metrics before and after recovery are properly separated.

        Returns:
            - ok: metrics are properly tagged and not mixed
            - mixed: metrics may be mixed across recovery boundaries
            - unknown: insufficient data to determine
        """
        from .evidence_manager import EvidenceManager

        em = EvidenceManager(self.project_root)
        runs = em.list_runs(task_id=task_id)

        if len(runs) <= 1:
            return {"status": "ok", "reason": "single run"}

        # Check if runs have proper continuity tags
        continuity_ok = True
        issues = []

        for run in runs:
            manifest = run
            if manifest.get("status") == "RECOVERED":
                # Check if recovery marker exists
                if not any("recovered_from" in str(r) for r in runs):
                    continuity_ok = False
                    issues.append(f"Run {run.get('run_id')} marked as RECOVERED but no source")

        if not continuity_ok:
            return {
                "status": "mixed",
                "reason": "potential metric mixing across recovery",
                "issues": issues,
            }

        return {"status": "ok", "reason": "continuity validated"}

    def get_recovery_summary(self) -> dict:
        """Get a summary of all recovery states."""
        summary = {
            "total_tasks": 0,
            "running": 0,
            "with_valid_checkpoint": 0,
            "with_invalid_checkpoint": 0,
            "no_checkpoint": 0,
            "needs_attention": [],
        }

        for task in self.store.list_tasks():
            summary["total_tasks"] += 1
            status = task.get("status")

            if status == "RUNNING":
                summary["running"] += 1
            elif status in {"PENDING", "READY"}:
                recovery_info = self.get_recovery_info(task)
                if recovery_info["has_checkpoint"]:
                    if recovery_info["checkpoint_valid"]:
                        summary["with_valid_checkpoint"] += 1
                    else:
                        summary["with_invalid_checkpoint"] += 1
                        summary["needs_attention"].append(
                            {
                                "task_id": task["id"],
                                "issue": "invalid_checkpoint",
                            }
                        )
                else:
                    summary["no_checkpoint"] += 1

        return summary
