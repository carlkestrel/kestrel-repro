from __future__ import annotations

import os
import sys
from pathlib import Path

from .process_manager import ProcessManager


class TaskExecutor:
    """Launch tasks as detached, logged, managed subprocesses."""

    def __init__(self, project_root: str | Path, store, process_manager: ProcessManager):
        self.project_root = Path(project_root).resolve()
        self.store = store
        self.process_manager = process_manager
        self.logs_dir = self.project_root / ".repro" / "execution" / "logs"

    def launch(self, task: dict):
        attempt = int(task.get("attempts", 0))
        log_path = self.logs_dir / f"{task['id']}.attempt-{attempt}.log"
        heartbeat_path = (
            self.project_root
            / ".repro"
            / "execution"
            / "task-heartbeats"
            / f"{task['id']}.heartbeat"
        )
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        env = {
            "REPRO_PROJECT_ROOT": str(self.project_root),
            "REPRO_TASK_ID": task["id"],
            "REPRO_TASK_ATTEMPT": str(attempt),
            "REPRO_HEARTBEAT_PATH": str(heartbeat_path),
            "PYTHONUNBUFFERED": "1",
            # Inject t4 conda env so `python` resolves to the right interpreter.
            "PATH": f"{os.path.dirname(sys.executable)}:{os.environ.get('PATH', '')}",
        }
        # R3F-3: orphan-process guard. The pid/log_path persistence happens
        # AFTER the process is actually started. If persistence fails, we
        # terminate the just-launched process so we don't leave an orphan.
        try:
            proc = self.process_manager.start(
                task["command"], cwd=self.project_root, log_path=log_path, env=env
            )
        except Exception:
            # Failed before start; nothing to clean up.
            raise
        try:
            self.store.set_process(task["id"], proc.pid, str(log_path))
        except Exception:
            # Persistence failed — kill the orphan so the controller loop
            # can mark the task as FAILED rather than leaving it RUNNING
            # with no recoverable pid.
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                pass
            raise
        # R3F-3: emit PROCESS_STARTED so audit/observability tests can
        # verify a real subprocess was launched for the task.
        try:
            self.store.record_event(
                "PROCESS_STARTED",
                task["id"],
                {"pid": proc.pid, "log_path": str(log_path), "attempt": attempt},
            )
        except Exception:
            # Event emission is best-effort — do not fail the launch.
            pass
        return proc

    def launch_with_orphan_guard(self, task: dict):
        """Convenience wrapper around ``launch`` that re-raises cleanly on
        orphan-process scenarios so callers can wrap with explicit handling."""
        return self.launch(task)

    def poll(self, task: dict) -> int | None:
        return self.process_manager.poll(int(task["pid"]))
