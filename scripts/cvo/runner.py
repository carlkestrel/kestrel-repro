"""
CVO Runner — executes individual validation nodes with proper isolation.

Each node:
  1. Acquires GPU lock if required
  2. Initializes node state
  3. Calls the node's implementation
  4. Captures stdout/stderr
  5. Updates state atomically
  6. Releases GPU lock
  7. Reports next nodes
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback as tb_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .nodes import NODE_MAP, ValidationNode
from .state import CVOStateStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_hash(path: Path) -> str:
    """Compute SHA256 of a file without loading entire file into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class CVORunner:
    """Execute a single validation node with timeout, GPU lock, and state tracking."""

    def __init__(self, project_root: Path | str | None = None):
        self.project_root = Path(project_root or os.getcwd()).resolve()
        self.store = CVOStateStore(self.project_root)

    def run_node(self, node_id: str, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
        """Run a single node. Returns result dict."""
        node = NODE_MAP.get(node_id)
        if not node:
            return {
                "node_id": node_id,
                "status": "FAILED",
                "error_type": "NOT_FOUND",
                "error_message": f"No node with id {node_id!r}",
            }

        current_status = self.store.get_status(node_id)

        # Skip already-passed nodes unless forced
        if current_status == "PASSED" and not force:
            return {
                "node_id": node_id,
                "status": "PASSED",
                "error_type": "",
                "error_message": "Already passed; use --force to re-run",
            }

        # Check GPU lock
        if node.requires_gpu:
            import os as _os

            acquired = self.store.acquire_gpu_lock(node_id, _os.getpid())
            if not acquired:
                holder = self.store.gpu_lock_holder()
                return {
                    "node_id": node_id,
                    "status": "BLOCKED",
                    "error_type": "GPU_LOCKED",
                    "error_message": f"GPU in use by {holder}",
                }

        try:
            # Initialize / update state
            self.store.set_status(node_id, "RUNNING")

            if dry_run:
                self.store.set_status(
                    node_id,
                    "PASSED",
                    evidence_files=self._expected_outputs(node),
                    extra={"dry_run": True},
                )
                return {"node_id": node_id, "status": "PASSED", "dry_run": True}

            # Execute
            result = self._execute(node)

            # Determine status
            if result.get("status") == "PASSED":
                evidence = self._collect_evidence(node)
                self.store.set_status(
                    node_id,
                    "PASSED",
                    evidence_files=result.get("evidence_files", evidence),
                    output_hashes=result.get("output_hashes", {}),
                    extra=result.get("extra", {}),
                )
            elif result.get("status") == "PARTIAL":
                self.store.set_status(
                    node_id,
                    "PARTIAL",
                    error_type=result.get("error_type", ""),
                    error_message=result.get("error_message", ""),
                    evidence_files=result.get("evidence_files", []),
                    extra=result.get("extra", {}),
                )
            else:
                self.store.set_status(
                    node_id,
                    "FAILED" if not node.retryable else "FAILED",
                    error_type=result.get("error_type", "EXECUTION_ERROR"),
                    error_message=result.get("error_message", ""),
                    extra={
                        "stdout": result.get("stdout", ""),
                        "stderr": result.get("stderr", ""),
                        "traceback": result.get("traceback", ""),
                    },
                )

            return result

        finally:
            if node.requires_gpu:
                self.store.release_gpu_lock(node_id)

    def _execute(self, node: ValidationNode) -> dict[str, Any]:
        """Execute a node's callable or subprocess."""
        log_path = self.store.node_log_path(node.node_id)

        # Heartbeat thread
        stop_heartbeat = threading.Event()

        def heartbeat_thread():
            while not stop_heartbeat.wait(30):
                self.store.update_heartbeat(node.node_id)

        hb_thread = threading.Thread(target=heartbeat_thread, daemon=True)
        hb_thread.start()

        try:
            if node.callable and ":" in node.callable:
                # Python callable: "module.submodule:function"
                result = self._run_callable(node, log_path)
            else:
                # Subprocess: run as standalone script
                result = self._run_subprocess(node, log_path)

            # Check for stale (missed heartbeat)
            if self.store.is_stale(node.node_id):
                result.setdefault("warnings", []).append("Node was marked STALE during execution")

            return result

        finally:
            stop_heartbeat.set()
            hb_thread.join(timeout=2)

    def _run_callable(self, node: ValidationNode, log_path: Path) -> dict[str, Any]:
        """Run a Python callable (module:function)."""
        module_path, func_name = node.callable.split(":", 1)

        # Add project root to sys.path
        project_python = self.project_root / "scripts"
        if str(project_python) not in sys.path:
            sys.path.insert(0, str(project_python))

        try:
            mod = importlib.import_module(module_path)
            func = getattr(mod, func_name, None)
            if not func:
                return {
                    "status": "FAILED",
                    "error_type": "NOT_FOUND",
                    "error_message": f"{module_path}:{func_name} not found",
                }

            # Call with project_root
            sig = getattr(func, "__code__", None) or getattr(func, "__call__", None)
            # Simple: just call with project_root
            kwargs = {"project_root": str(self.project_root)}
            result = func(**kwargs)

            if isinstance(result, dict):
                return result
            else:
                return {"status": "PASSED", "result": result}

        except Exception as e:
            return {
                "status": "FAILED",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": tb_lib.format_exc(),
            }

    def _run_subprocess(self, node: ValidationNode, log_path: Path) -> dict[str, Any]:
        """Run node as a subprocess with timeout."""
        # Find the node's implementation script
        node_script = (
            self.project_root / "scripts" / "cvo" / f"{node.node_id.lower().replace('-', '_')}.py"
        )

        if not node_script.exists():
            return {
                "status": "FAILED",
                "error_type": "NOT_FOUND",
                "error_message": f"Node script not found: {node_script}",
            }

        cmd = [
            sys.executable,
            str(node_script),
            "--project",
            str(self.project_root),
            "--node",
            node.node_id,
        ]

        with open(log_path, "w") as log_f:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.project_root / "scripts") + ":" + env.get("PYTHONPATH", "")

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=str(self.project_root),
            )

            stdout_lines = []
            deadline = time.time() + node.timeout_seconds

            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    proc.kill()
                    return {
                        "status": "FAILED",
                        "error_type": "TIMEOUT",
                        "error_message": f"Node exceeded {node.timeout_seconds}s timeout",
                        "stdout": "".join(stdout_lines),
                    }

                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break

                if line:
                    stdout_lines.append(line)
                    log_f.write(line)
                    log_f.flush()

            proc.wait()
            stdout = "".join(stdout_lines)

            # Parse result from stdout
            result: dict[str, Any] = {"status": "PASSED", "stdout": stdout}

            # Try to parse JSON result from last line
            for line in reversed(stdout_lines):
                stripped = line.strip()
                if stripped.startswith("{"):
                    try:
                        parsed = json.loads(stripped)
                        if "status" in parsed:
                            result = parsed
                            break
                    except json.JSONDecodeError:
                        pass

            if proc.returncode != 0 and result.get("status") == "PASSED":
                result["status"] = "FAILED"
                result["error_type"] = "NONZERO_EXIT"
                result["error_message"] = f"Exit code {proc.returncode}"

            result["stdout"] = stdout
            return result

    def _collect_evidence(self, node: ValidationNode) -> list[str]:
        """Collect evidence files for a node."""
        evidence = []
        node_dir = self.store.node_evidence_dir(node.node_id)
        for f in node_dir.rglob("*"):
            if f.is_file():
                evidence.append(str(f.relative_to(self.project_root)))
        return evidence

    def _expected_outputs(self, node: ValidationNode) -> list[str]:
        """Return expected output file paths for a node."""
        return node.output_fields

    # ── run-next: pick next ready node ──────────────────────────────────────

    def get_next_node(self, max_gpu: int = 1) -> ValidationNode | None:
        """Return the next READY node to run, respecting GPU lock and parallelism."""
        from .nodes import ALL_NODES

        # Count running GPU nodes
        running_gpu = sum(
            1
            for n in self.store.list_all()
            if n.get("status") == "RUNNING"
            and NODE_MAP.get(n["node_id"], ValidationNode("")).requires_gpu
        )

        for node in ALL_NODES:
            status = self.store.get_status(node.node_id)
            if status in ("PASSED", "RUNNING", "PAUSED", "BLOCKED"):
                continue

            # Check dependencies
            deps_ok = all(self.store.get_status(d) == "PASSED" for d in node.depends_on)
            if not deps_ok:
                continue

            # Check GPU constraint
            if node.requires_gpu:
                if self.store.is_gpu_locked():
                    holder = self.store.gpu_lock_holder()
                    if holder != node.node_id:
                        continue
                if running_gpu >= max_gpu:
                    continue
                # Try to acquire lock
                if not self.store.acquire_gpu_lock(node.node_id, os.getpid()):
                    continue

            return node

        return None

    def run_next(self, dry_run: bool = False, max_gpu: int = 1) -> dict[str, Any]:
        """Pick and run the next ready node. Returns node_id and result."""
        node = self.get_next_node(max_gpu=max_gpu)
        if not node:
            return {
                "status": "NO_READY_NODE",
                "message": "No ready nodes available",
                "summary": self.store.summary(),
            }

        result = self.run_node(node.node_id, dry_run=dry_run)
        return {
            "node_id": node.node_id,
            "node_name": node.name,
            **result,
            "summary": self.store.summary(),
        }
