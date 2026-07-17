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
        heartbeat_path = self.project_root / ".repro" / "execution" / "task-heartbeats" / f"{task['id']}.heartbeat"
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
        proc = self.process_manager.start(
            task["command"], cwd=self.project_root, log_path=log_path, env=env
        )
        self.store.set_process(task["id"], proc.pid, str(log_path))
        return proc

    def poll(self, task: dict) -> int | None:
        return self.process_manager.poll(int(task["pid"]))
