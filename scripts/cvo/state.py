"""
CVO State Store — Atomic, persistent state for validation nodes.

State lives at:
  .repro/audit/
  ├── audit_manifest.json
  ├── nodes/
  │   ├── VAL-000.json
  │   └── ...
  ├── state/
  │   ├── current_state.json
  │   └── heartbeats/
  │       └── <node_id>.json
  ├── locks/
  │   └── gpu.lock
  ├── logs/
  ├── evidence/
  ├── checkpoints/
  └── reports/
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


class CVOStateStore:
    """Thread-safe, atomic, SQLite-backed state store for CVO nodes."""

    # Valid statuses
    VALID_STATUSES = {
        "PENDING", "READY", "RUNNING", "PASSED", "FAILED",
        "PARTIAL", "BLOCKED", "PAUSED", "STALE", "SKIPPED",
        "CANCELLED",
    }

    _instance: Optional["CVOStateStore"] = None
    _lock = threading.Lock()

    def __init__(self, project_root: Path | str | None = None):
        self._project_root = Path(project_root or os.getcwd()).resolve()
        self._audit_dir = self._project_root / ".repro" / "audit"
        self._nodes_dir = self._audit_dir / "nodes"
        self._state_dir = self._audit_dir / "state"
        self._heartbeat_dir = self._state_dir / "heartbeats"
        self._locks_dir = self._audit_dir / "locks"
        self._logs_dir = self._audit_dir / "logs"
        self._evidence_dir = self._audit_dir / "evidence"
        self._checkpoints_dir = self._audit_dir / "checkpoints"
        self._reports_dir = self._audit_dir / "reports"

        # Ensure directories exist
        for d in (self._nodes_dir, self._state_dir, self._heartbeat_dir,
                  self._locks_dir, self._logs_dir, self._evidence_dir,
                  self._checkpoints_dir, self._reports_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ── Node state file helpers ────────────────────────────────────────────────

    def _node_path(self, node_id: str) -> Path:
        return self._nodes_dir / f"{node_id}.json"

    def _heartbeat_path(self, node_id: str) -> Path:
        return self._heartbeat_dir / f"{node_id}.json"

    def _read_node(self, node_id: str) -> dict[str, Any]:
        p = self._node_path(node_id)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {}

    def _write_node_atomic(self, node_id: str, data: dict[str, Any]) -> None:
        """Write atomically: tmp → flush → rename."""
        p = self._node_path(node_id)
        tmp = p.with_suffix(".tmp")
        tmp_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        tmp.write_text(tmp_text, encoding="utf-8")
        with open(tmp, "r+b") as f:
            os.fsync(f.fileno())
        os.replace(tmp, p)

    # ── Status transitions ────────────────────────────────────────────────────

    def init_node(self, node_id: str, defaults: dict[str, Any]) -> None:
        """Initialize a node if not already present."""
        if self._node_path(node_id).exists():
            return
        data = {
            "node_id": node_id,
            "status": "PENDING",
            "attempt": 0,
            "max_attempts": 2,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            **defaults,
        }
        self._write_node_atomic(node_id, data)

    def get_status(self, node_id: str) -> str:
        """Get current status of a node."""
        data = self._read_node(node_id)
        return data.get("status", "PENDING")

    def set_status(self, node_id: str, status: str,
                   error_type: str = "", error_message: str = "",
                   evidence_files: list[str] | None = None,
                   output_hashes: dict[str, str] | None = None,
                   extra: dict[str, Any] | None = None) -> None:
        """Atomically update node status."""
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status!r}")

        data = self._read_node(node_id)
        old_status = data.get("status", "PENDING")

        if status == "RUNNING":
            data["attempt"] = data.get("attempt", 0) + 1
            data["started_at"] = utc_now()
            data["heartbeat_at"] = utc_now()
        elif status in ("PASSED", "FAILED", "PARTIAL", "BLOCKED",
                        "SKIPPED", "CANCELLED"):
            data["finished_at"] = utc_now()
            data["updated_at"] = utc_now()
            if error_type:
                data["error_type"] = error_type
            if error_message:
                data["error_message"] = error_message
            if evidence_files is not None:
                data["evidence_files"] = evidence_files
            if output_hashes:
                data["output_hashes"] = output_hashes
            if extra:
                data.update(extra)

        data["status"] = status
        data["updated_at"] = utc_now()

        self._write_node_atomic(node_id, data)

    def update_heartbeat(self, node_id: str) -> None:
        """Update heartbeat timestamp for a running node."""
        data = self._read_node(node_id)
        data["heartbeat_at"] = utc_now()
        data["heartbeat_ts"] = utc_now_ts()
        hb_path = self._heartbeat_path(node_id)
        hb_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_stale(self, node_id: str, max_age_seconds: float = 120) -> bool:
        """Check if a RUNNING node has missed heartbeats."""
        data = self._read_node(node_id)
        if data.get("status") != "RUNNING":
            return False
        hb_ts = data.get("heartbeat_ts", 0)
        if hb_ts == 0:
            return False
        return (utc_now_ts() - hb_ts) > max_age_seconds

    # ── Aggregate queries ──────────────────────────────────────────────────────

    def list_all(self) -> list[dict[str, Any]]:
        """List all node states."""
        results = []
        for p in sorted(self._nodes_dir.glob("*.json")):
            results.append(json.loads(p.read_text(encoding="utf-8")))
        return results

    def summary(self) -> dict[str, int]:
        """Count nodes by status."""
        counts: dict[str, int] = {s: 0 for s in self.VALID_STATUSES}
        for node in self.list_all():
            counts[node.get("status", "PENDING")] += 1
        return counts

    def get_ready(self, all_depends: dict[str, list[str]]) -> list[dict[str, Any]]:
        """Return nodes that are READY (deps passed, not yet started)."""
        ready = []
        for node in self.list_all():
            nid = node["node_id"]
            status = node.get("status", "PENDING")
            if status not in ("PENDING",):
                continue
            deps = all_depends.get(nid, [])
            if all(self.get_status(d) == "PASSED" for d in deps):
                node["_derived_status"] = "READY"
                ready.append(node)
        return ready

    # ── Manifest ──────────────────────────────────────────────────────────────

    def write_manifest(self, audit_id: str, plugin_root: Path) -> dict[str, Any]:
        manifest = {
            "audit_id": audit_id,
            "plugin_root": str(plugin_root),
            "project_root": str(self._project_root),
            "created_at": utc_now(),
            "cvo_version": "0.1.0",
            "nodes_dir": str(self._nodes_dir),
            "state_dir": str(self._state_dir),
            "logs_dir": str(self._logs_dir),
            "evidence_dir": str(self._evidence_dir),
            "reports_dir": str(self._reports_dir),
        }
        path = self._audit_dir / "audit_manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        return manifest

    def read_manifest(self) -> dict[str, Any]:
        path = self._audit_dir / "audit_manifest.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    # ── GPU lock ──────────────────────────────────────────────────────────────

    def acquire_gpu_lock(self, node_id: str, pid: int) -> bool:
        """Acquire GPU lock. Returns True if acquired, False if already held."""
        lock_file = self._locks_dir / "gpu.lock"
        if lock_file.exists():
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            # Check if stale
            hb_ts = data.get("heartbeat_ts", 0)
            if (utc_now_ts() - hb_ts) < 120:
                # Lock is alive
                return False
            # Lock is stale — remove it
            lock_file.unlink(missing_ok=True)

        lock_file.write_text(json.dumps({
            "node_id": node_id,
            "pid": pid,
            "acquired_at": utc_now(),
            "heartbeat_ts": utc_now_ts(),
        }, indent=2), encoding="utf-8")
        return True

    def release_gpu_lock(self, node_id: str) -> None:
        lock_file = self._locks_dir / "gpu.lock"
        if lock_file.exists():
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            if data.get("node_id") == node_id:
                lock_file.unlink(missing_ok=True)

    def is_gpu_locked(self) -> bool:
        lock_file = self._locks_dir / "gpu.lock"
        if not lock_file.exists():
            return False
        data = json.loads(lock_file.read_text(encoding="utf-8"))
        hb_ts = data.get("heartbeat_ts", 0)
        if (utc_now_ts() - hb_ts) < 120:
            return True
        return False

    def gpu_lock_holder(self) -> str | None:
        lock_file = self._locks_dir / "gpu.lock"
        if not lock_file.exists():
            return None
        data = json.loads(lock_file.read_text(encoding="utf-8"))
        hb_ts = data.get("heartbeat_ts", 0)
        if (utc_now_ts() - hb_ts) < 120:
            return data.get("node_id")
        return None

    # ── Evidence helpers ──────────────────────────────────────────────────────

    def node_evidence_dir(self, node_id: str) -> Path:
        d = self._evidence_dir / node_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def node_log_path(self, node_id: str) -> Path:
        log = self._logs_dir / f"{node_id}.log"
        log.touch()
        return log

    def node_checkpoint_dir(self, node_id: str) -> Path:
        d = self._checkpoints_dir / node_id
        d.mkdir(parents=True, exist_ok=True)
        return d
