from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import IO, Sequence


class ProcessManager:
    """Sole process creation and termination boundary for the orchestrator."""

    def __init__(self):
        self._processes: dict[int, tuple[subprocess.Popen, IO[bytes] | None]] = {}

    def start(self, command: str | Sequence[str], *, cwd: str | Path,
              log_path: str | Path, env: dict[str, str] | None = None) -> subprocess.Popen:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("ab", buffering=0)
        merged_env = os.environ.copy()
        if env:
            merged_env.update({str(key): str(value) for key, value in env.items()})
        if isinstance(command, str):
            launched_command: Sequence[str] = ["nohup", "/bin/sh", "-c", command]
        else:
            launched_command = ["nohup", *command]
        proc = subprocess.Popen(
            launched_command,
            cwd=str(cwd),
            env=merged_env,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
        self._processes[proc.pid] = (proc, handle)
        return proc

    def poll(self, pid: int) -> int | None:
        managed = self._processes.get(pid)
        if managed:
            proc, handle = managed
            code = proc.poll()
            if code is not None:
                if handle:
                    handle.close()
                self._processes.pop(pid, None)
            return code
        if self.is_alive(pid):
            return None
        return self._read_exit_code(pid)

    @staticmethod
    def _read_exit_code(pid: int) -> int:
        # Exit status is unavailable after controller restart; recovery verifies artifacts.
        return 0

    @staticmethod
    def is_alive(pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        try:
            stat = Path(f"/proc/{pid}/stat")
            if stat.exists() and stat.read_text().split()[2] == "Z":
                return False
        except (OSError, IndexError):
            pass
        return True

    def terminate(self, pid: int, grace_seconds: float = 3.0) -> bool:
        if not self.is_alive(pid):
            return True
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if not self.is_alive(pid):
                self._cleanup(pid)
                return True
            time.sleep(0.05)
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self._cleanup(pid)
        return not self.is_alive(pid)

    def _cleanup(self, pid: int) -> None:
        managed = self._processes.pop(pid, None)
        if managed and managed[1]:
            managed[1].close()

    def run(self, command: str | Sequence[str], *, cwd: str | Path,
            log_path: str | Path, timeout: float | None = None,
            env: dict[str, str] | None = None) -> int:
        proc = self.start(command, cwd=cwd, log_path=log_path, env=env)
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.terminate(proc.pid)
            return 124
        finally:
            self._cleanup(proc.pid)

    def explain_exit_code(self, exit_code: int | None) -> str:
        """R3-4: explain unknown exit codes (e.g. negative = signal).

        Returns a human-readable explanation:
        - 0..125: explicit exit code
        - 124: timeout (matches timeout(1))
        - 125: GNU timeout; command not found
        - 126: found but not executable
        - 127: command not found
        - negative: killed by signal N (e.g. -15 → SIGTERM)
        - 137: killed by SIGKILL (128+9)
        - 143: killed by SIGTERM (128+15)
        - 139: SIGSEGV (128+11)
        """
        if exit_code is None:
            return "still running"
        if exit_code == 0:
            return "success"
        if exit_code == 124:
            return "timeout (subprocess killed)"
        if exit_code == 137:
            return "killed by SIGKILL"
        if exit_code == 143:
            return "killed by SIGTERM"
        if exit_code == 139:
            return "SIGSEGV (segmentation fault)"
        if exit_code == 134:
            return "SIGABRT"
        if exit_code == -15:
            return "killed by SIGTERM (negative)"
        if exit_code == -9:
            return "killed by SIGKILL (negative)"
        if exit_code == -11:
            return "SIGSEGV (negative)"
        if 0 < exit_code < 128:
            return f"non-zero exit ({exit_code})"
        return f"exit code {exit_code}"

    def start_daemon(self, argv: Sequence[str], *, cwd: str | Path,
                     log_path: str | Path, pid_path: str | Path,
                     env: dict[str, str] | None = None) -> int:
        proc = self.start(list(argv), cwd=cwd, log_path=log_path, env=env)
        pid_file = Path(pid_path)
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = pid_file.with_suffix(".tmp")
        tmp.write_text(str(proc.pid), encoding="utf-8")
        os.replace(tmp, pid_file)
        return proc.pid
