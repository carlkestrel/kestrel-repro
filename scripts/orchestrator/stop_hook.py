"""
NORA-style Stop Hook - Automatic state preservation on interrupt.

This module implements NORA's automatic state saving mechanism:
- Saves handoff.json on SIGINT/SIGTERM
- Saves EventJournal snapshot
- Saves StateStore snapshot
- Supports graceful shutdown and crash recovery
"""
from __future__ import annotations

import atexit
import json
import os
import signal
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .state_store import StateStore
from .event_journal import EventJournal


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StopHook:
    """
    NORA-style automatic state preservation hook.

    Registers handlers for:
    - SIGINT (Ctrl+C)
    - SIGTERM (system termination)
    - atexit (programmatic exit)

    On any of these events, saves:
    1. handoff.json - current state for resume
    2. EventJournal snapshot
    3. StateStore snapshot
    """

    def __init__(self, project_root: str | Path,
                 state_store: StateStore | None = None,
                 event_journal: EventJournal | None = None):
        self.project_root = Path(project_root).resolve()
        self.execution_dir = self.project_root / ".repro" / "execution"
        self.state_store = state_store
        self.event_journal = event_journal
        self._registered = False
        self._lock = threading.Lock()
        self._save_count = 0
        self._suppress_save = False

    def register(self) -> None:
        """Register signal handlers and atexit hook."""
        if self._registered:
            return

        with self._lock:
            if self._registered:
                return

            atexit.register(self._save_state)

            # R3-3: signal.signal() can only be called from the main thread.
            # If we're running in a worker thread (e.g., tests launch the
            # controller in a thread), skip signal registration — tests
            # should drive signals via direct method calls or simply use
            # set_control_state().
            if threading.current_thread() is threading.main_thread():
                if hasattr(signal, "SIGINT"):
                    signal.signal(signal.SIGINT, self._signal_handler)

                if hasattr(signal, "SIGTERM"):
                    signal.signal(signal.SIGTERM, self._signal_handler)
            else:
                # Best-effort: register atexit-only; controller will be
                # stopped by its thread when it polls control_state.
                pass

            self._registered = True

    def unregister(self) -> None:
        """Unregister all handlers."""
        with self._lock:
            if not self._registered:
                return

            try:
                atexit.unregister(self._save_state)
            except (TypeError, ValueError):
                pass

            if hasattr(signal, "SIGINT"):
                try:
                    signal.signal(signal.SIGINT, signal.SIG_DFL)
                except (TypeError, ValueError):
                    pass

            if hasattr(signal, "SIGTERM"):
                try:
                    signal.signal(signal.SIGTERM, signal.SIG_DFL)
                except (TypeError, ValueError):
                    pass

            self._registered = False

    def suppress_save(self) -> None:
        """Temporarily suppress save operations."""
        self._suppress_save = True

    def restore_save(self) -> None:
        """Restore save operations after suppress."""
        self._suppress_save = False

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle incoming signals."""
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        self._save_state(signal_sig=sig_name)
        raise SystemExit(128 + signum)

    def _save_state(self, signal_sig: str | None = None) -> dict[str, Any] | None:
        """
        Save current state to handoff.json, EventJournal snapshot, and StateStore snapshot.

        Returns:
            dict with paths to saved files, or None if save was suppressed
        """
        if self._suppress_save:
            return None

        with self._lock:
            self._save_count += 1
            save_number = self._save_count

        timestamp = utc_now()
        results: dict[str, Any] = {
            "timestamp": timestamp,
            "save_number": save_number,
            "trigger": signal_sig or "atexit",
            "pid": os.getpid(),
        }

        try:
            self.execution_dir.mkdir(parents=True, exist_ok=True)

            handoff_path = self._save_handoff(timestamp)
            results["handoff"] = str(handoff_path)

            journal_path = self._save_journal_snapshot()
            if journal_path:
                results["journal_snapshot"] = str(journal_path)

            store_path = self._save_store_snapshot()
            if store_path:
                results["store_snapshot"] = str(store_path)

            results["status"] = "success"

        except Exception as exc:
            results["status"] = "error"
            results["error"] = str(exc)
            results["traceback"] = traceback.format_exc()

        return results

    def _save_handoff(self, timestamp: str) -> Path:
        """
        Save handoff.json - the main state file for NORA-style resume.

        This file contains:
        - Current execution state
        - Pending tasks
        - Last completed task
        - Next recommended action
        """
        handoff: dict[str, Any] = {
            "version": "1.0",
            "timestamp": timestamp,
            "project_root": str(self.project_root),
            "execution_dir": str(self.execution_dir),
        }

        if self.state_store is not None:
            try:
                tasks = self.state_store.list_tasks()
                pending = [t for t in tasks if t["status"] in {
                    "PENDING", "READY", "RUNNING", "VERIFYING", "WAITING_APPROVAL", "RETRY_WAIT"
                }]
                completed = [t for t in tasks if t["status"] in {"PASSED", "FAILED", "REJECTED"}]

                handoff["execution_state"] = {
                    "control_state": self.state_store.control_state(),
                    "pending_task_count": len(pending),
                    "completed_task_count": len(completed),
                    "total_task_count": len(tasks),
                }

                handoff["pending_tasks"] = [
                    {
                        "id": t["id"],
                        "name": t["name"],
                        "status": t["status"],
                        "gate": t["gate"],
                    }
                    for t in pending
                ]

                if completed:
                    handoff["last_completed"] = {
                        "id": completed[-1]["id"],
                        "name": completed[-1]["name"],
                        "status": completed[-1]["status"],
                        "finished_at": completed[-1].get("finished_at"),
                    }

                running = [t for t in tasks if t["status"] == "RUNNING"]
                if running:
                    handoff["running_tasks"] = [
                        {
                            "id": t["id"],
                            "name": t["name"],
                            "pid": t.get("pid"),
                            "started_at": t.get("started_at"),
                        }
                        for t in running
                    ]

            except Exception as exc:
                handoff["state_store_error"] = str(exc)

        if self.event_journal is not None:
            try:
                events = self.event_journal.read()
                handoff["event_count"] = len(events)
                if events:
                    handoff["last_event"] = events[-1]
            except Exception as exc:
                handoff["journal_error"] = str(exc)

        handoff_path = self.execution_dir / "handoff.json"
        self._atomic_write(handoff_path, json.dumps(handoff, indent=2, sort_keys=True))
        return handoff_path

    def _save_journal_snapshot(self) -> Path | None:
        """Save EventJournal snapshot to events.snapshot.jsonl."""
        if self.event_journal is None:
            return None

        try:
            events = self.event_journal.read()
            snapshot_path = self.execution_dir / "events.snapshot.jsonl"
            self._atomic_write_jsonl(snapshot_path, events)
            return snapshot_path
        except Exception:
            return None

    def _save_store_snapshot(self) -> Path | None:
        """Save StateStore snapshot."""
        if self.state_store is None:
            return None

        try:
            snapshot = self.state_store.export_snapshots()
            return Path(snapshot.get("json", ""))
        except Exception:
            return None

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Atomically write content to file."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)

    @staticmethod
    def _atomic_write_jsonl(path: Path, records: list[dict]) -> None:
        """Atomically write JSONL records to file."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        os.replace(tmp, path)


class RecoveryManager:
    """
    Manager for recovering from handoff.json on restart.

    Implements NORA-style session continuation:
    1. Load handoff.json if exists
    2. Validate saved state
    3. Provide recovered state to Controller
    """

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.execution_dir = self.project_root / ".repro" / "execution"
        self.handoff_path = self.execution_dir / "handoff.json"

    def load_handoff(self) -> dict[str, Any] | None:
        """Load handoff.json if it exists and is valid."""
        if not self.handoff_path.exists():
            return None

        try:
            content = self.handoff_path.read_text(encoding="utf-8")
            handoff = json.loads(content)

            if handoff.get("version") != "1.0":
                return None

            return handoff
        except (json.JSONDecodeError, OSError):
            return None

    def get_pending_tasks(self) -> list[dict[str, Any]]:
        """Get list of tasks that were pending when last stopped."""
        handoff = self.load_handoff()
        if handoff is None:
            return []
        return handoff.get("pending_tasks", [])

    def get_running_tasks(self) -> list[dict[str, Any]]:
        """Get list of tasks that were running when last stopped."""
        handoff = self.load_handoff()
        if handoff is None:
            return []
        return handoff.get("running_tasks", [])

    def get_execution_state(self) -> dict[str, Any] | None:
        """Get overall execution state."""
        handoff = self.load_handoff()
        if handoff is None:
            return None
        return handoff.get("execution_state")

    def clear_handoff(self) -> bool:
        """Clear handoff.json after successful recovery."""
        try:
            if self.handoff_path.exists():
                self.handoff_path.unlink()
            return True
        except OSError:
            return False

    def archive_handoff(self, archive_suffix: str | None = None) -> Path | None:
        """Archive current handoff.json with timestamp."""
        if not self.handoff_path.exists():
            return None

        if archive_suffix is None:
            archive_suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        archive_name = f"handoff.{archive_suffix}.json"
        archive_path = self.execution_dir / "handoff_archive" / archive_name

        try:
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            self.handoff_path.rename(archive_path)
            return archive_path
        except OSError:
            return None


def create_stop_hook(project_root: str | Path,
                    state_store: StateStore | None = None,
                    event_journal: EventJournal | None = None) -> StopHook:
    """
    Factory function to create and register a StopHook.

    Args:
        project_root: Path to project root
        state_store: Optional StateStore instance for state saving
        event_journal: Optional EventJournal instance for event saving

    Returns:
        Configured and registered StopHook instance
    """
    hook = StopHook(project_root, state_store, event_journal)
    hook.register()
    return hook
