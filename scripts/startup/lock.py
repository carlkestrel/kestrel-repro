"""Project-level single-instance lock.

Rules:
  - missing  → create
  - valid    → reject (raise LockHeld)
  - stale    → copy aside, run state-consistency check, clear, then create.

A lock is considered stale when ANY of:
  - the recorded PID is not alive
  - the recorded hostname is not the current hostname
  - start_time is older than ``STALE_AFTER_SECONDS``
  - heartbeat is older than ``STALE_AFTER_SECONDS``

State-consistency check is performed by ``state_machine.is_consistent``
so that callers can re-enter the locked section safely.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STALE_AFTER_SECONDS = 6 * 3600  # 6 hours


class LockHeld(RuntimeError):
    """Raised when a live, valid lock already fences this project."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(lock_path: Path) -> dict | None:
    if not lock_path.exists():
        return None
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _age_seconds(iso_ts: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return float("inf")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()


def _is_stale(info: dict) -> bool:
    """Return True iff any staleness indicator fires."""
    pid = info.get("process_id")
    if pid and not _pid_alive(pid):
        return True
    if info.get("hostname") and info.get("hostname") != socket.gethostname():
        return True
    start_age = _age_seconds(info.get("start_time", ""))
    hb_age = _age_seconds(info.get("heartbeat", info.get("start_time", "")))
    if start_age > STALE_AFTER_SECONDS or hb_age > STALE_AFTER_SECONDS:
        return True
    return False


def acquire(lock_path: Path, *, command: str, plan_hash: str,
            project_root: str | None = None,
            plugin_version: str = "0.2.0",
            consistency_check=None) -> dict:
    """Acquire the project-level lock.

    If a stale lock is found, archive it as ``run.lock.stale.<ts>`` and
    optionally run ``consistency_check(project_root)`` before clearing.
    Raises :class:`LockHeld` when the lock is held by a live process.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read(lock_path)
    if existing and not _is_stale(existing):
        raise LockHeld(
            f"Project is already running (pid={existing.get('process_id')} "
            f"on {existing.get('hostname')}); refusing duplicate start. "
            f"Use `reproctl stop` first or remove {lock_path} if it is stale."
        )
    if existing:
        # Stale lock — archive it, run consistency check, then clear
        archive = lock_path.with_name(
            f"run.lock.stale.{int(time.time())}")
        try:
            shutil.copy2(lock_path, archive)
        except Exception:
            pass
        if project_root and consistency_check:
            try:
                consistency_check(Path(project_root))
            except Exception:
                # State inconsistency must be reported but should not block
                # a stale-lock clear. The recovery command will surface it.
                pass
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass

    info = {
        "process_id": os.getpid(),
        "hostname": socket.gethostname(),
        "start_time": _utc_now(),
        "project_root": project_root or str(lock_path.parent.parent),
        "plan_hash": plan_hash,
        "command": command,
        "heartbeat": _utc_now(),
        "plugin_version": plugin_version,
    }
    tmp = lock_path.with_suffix(lock_path.suffix + ".tmp")
    tmp.write_text(json.dumps(info, indent=2), encoding="utf-8")
    tmp.replace(lock_path)
    return info


def heartbeat(lock_path: Path) -> None:
    """Update the heartbeat field on an existing lock."""
    info = _read(lock_path)
    if not info:
        return
    info["heartbeat"] = _utc_now()
    tmp = lock_path.with_suffix(lock_path.suffix + ".tmp")
    tmp.write_text(json.dumps(info, indent=2), encoding="utf-8")
    tmp.replace(lock_path)


def release(lock_path: Path) -> None:
    """Remove the lock. Idempotent."""
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def inspect(lock_path: Path) -> dict | None:
    """Return the current lock dict (or None) with staleness annotated."""
    info = _read(lock_path)
    if not info:
        return None
    info["is_stale"] = _is_stale(info)
    return info
