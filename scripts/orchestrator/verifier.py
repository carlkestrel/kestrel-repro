from __future__ import annotations

import os
from pathlib import Path


class Verifier:
    """Run every acceptance command; only an all-zero result is PASS."""

    def __init__(self, project_root: str | Path, store, process_manager):
        self.project_root = Path(project_root).resolve()
        self.store = store
        self.process_manager = process_manager
        self.logs_dir = self.project_root / ".repro" / "execution" / "logs"

    def verify(self, task: dict) -> tuple[bool, str]:
        tests = task.get("acceptance_tests", [])
        if not tests:
            self.store.record_event("VERIFICATION_PASS", task["id"], {"tests": 0})
            return True, "no acceptance tests"
        for index, test in enumerate(tests, 1):
            test_type = test.get("type", "command") if isinstance(test, dict) else "command"
            if test_type == "file_exists":
                path = test.get("path") if isinstance(test, dict) else str(test)
                log_path = self.logs_dir / f"{task['id']}.acceptance-{index}.log"
                log_path.write_text(f"file_exists check: {path}\n")
                passed = (self.project_root / path).exists()
                code = 0 if passed else 1
                self.store.record_event("ACCEPTANCE_RESULT", task["id"], {
                    "index": index, "type": "file_exists", "path": path,
                    "exists": passed, "exit_code": code,
                    "log_path": str(log_path),
                })
                if code != 0:
                    return False, f"acceptance test {index} (file_exists): {path} not found"
            elif test_type == "numeric_range":
                import json as _json
                path = test.get("path") if isinstance(test, dict) else str(test)
                log_path = self.logs_dir / f"{task['id']}.acceptance-{index}.log"
                full_path = self.project_root / path
                if not full_path.exists():
                    log_path.write_text(f"numeric_range check: {path} — FILE NOT FOUND\n")
                    self.store.record_event("ACCEPTANCE_RESULT", task["id"], {
                        "index": index, "type": "numeric_range", "path": path,
                        "exit_code": 1, "log_path": str(log_path),
                    })
                    return False, f"acceptance test {index} (numeric_range): {path} not found"
                try:
                    raw = full_path.read_text().strip()
                    value = float(raw) if raw.replace(".", "").replace("-", "").isdigit() else _json.loads(raw).get("final_loss", float("nan"))
                except Exception as e:
                    log_path.write_text(f"numeric_range check: {path} — parse error: {e}\n")
                    self.store.record_event("ACCEPTANCE_RESULT", task["id"], {
                        "index": index, "type": "numeric_range", "path": path,
                        "exit_code": 1, "log_path": str(log_path),
                    })
                    return False, f"acceptance test {index} (numeric_range): {path} parse error: {e}"
                lo = float(test.get("min", float("-inf"))) if isinstance(test, dict) else float("-inf")
                hi = float(test.get("max", float("inf"))) if isinstance(test, dict) else float("inf")
                passed = lo <= value <= hi
                code = 0 if passed else 1
                log_path.write_text(f"numeric_range check: {path}={value} in [{lo}, {hi}] -> {'PASS' if passed else 'FAIL'}\n")
                self.store.record_event("ACCEPTANCE_RESULT", task["id"], {
                    "index": index, "type": "numeric_range", "path": path,
                    "value": value, "min": lo, "max": hi,
                    "passed": passed, "exit_code": code,
                    "log_path": str(log_path),
                })
                if code != 0:
                    return False, f"acceptance test {index} (numeric_range): {path}={value} not in [{lo}, {hi}]"
            else:
                command = test["command"] if isinstance(test, dict) else str(test)
                timeout = None
                if isinstance(test, dict) and test.get("timeout_sec") is not None:
                    timeout = float(test["timeout_sec"])
                log_path = self.logs_dir / f"{task['id']}.acceptance-{index}.log"
                _verifier_env = {
                    "REPRO_TASK_ID": task["id"],
                    "REPRO_VERIFY": "1",
                    "PATH": f"/home/carlkestrel/miniconda3/envs/t4/bin:{os.environ.get('PATH', '')}",
                }
                code = self.process_manager.run(
                    command, cwd=self.project_root, log_path=log_path, timeout=timeout,
                    env=_verifier_env,
                )
                self.store.record_event("ACCEPTANCE_RESULT", task["id"], {
                    "index": index, "command": command, "exit_code": code,
                    "log_path": str(log_path),
                })
                if code != 0:
                    return False, f"acceptance test {index} failed with exit code {code}"
        self.store.record_event("VERIFICATION_PASS", task["id"], {"tests": len(tests)})
        return True, f"{len(tests)} acceptance tests passed"
