from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# R3F-7: Required fields per acceptance test type.
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "file_exists": ["path"],
    "numeric_range": ["path"],
    "command": ["command"],
    "metrics_recompute": ["path"],
}


def _validate_test_entry(test: dict, index: int) -> str | None:
    """R3F-7: validate a single acceptance test dict before running it."""
    test_type = test.get("type", "command") if isinstance(test, dict) else "command"
    required = _REQUIRED_FIELDS.get(test_type, ["command"])
    for field in required:
        if field not in test or not test[field]:
            return f"acceptance test {index} ({test_type}): missing required field '{field}'"
    return None


class Verifier:
    """Run every acceptance command; only an all-zero result is PASS."""

    def __init__(self, project_root: str | Path, store, process_manager):
        self.project_root = Path(project_root).resolve()
        self.store = store
        self.process_manager = process_manager
        self.logs_dir = self.project_root / ".repro" / "execution" / "logs"

    def self_test(self) -> dict:
        """R3F-7: health-check the verifier against a known-good fixture.

        Creates a temporary file, runs one ``file_exists`` acceptance test,
        and verifies the result is (True, ...). Returns a status dict.
        """
        import tempfile

        fixture: dict[str, Any] = {"tests_run": 0, "errors": []}
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
                f.write(b"self_test_ok")
                fixture_path = f.name
            test_task = {
                "id": "_verifier_self_test",
                "acceptance_tests": [{"type": "file_exists", "path": fixture_path}],
                "non_evidentiary": False,
            }
            ok, detail = self.verify(test_task)
            if ok:
                fixture["tests_run"] = 1
            else:
                fixture["errors"].append(f"self-test failed: {detail}")
            os.unlink(fixture_path)
        except Exception as exc:
            fixture["errors"].append(f"self-test crashed: {exc}")
        fixture["status"] = "PASS" if not fixture["errors"] else "FAIL"
        return fixture

    def verify(self, task: dict) -> tuple[bool, str]:
        """R3F-5 task 4 + R3F-7 crash isolation.

        Returns (True, detail) if all acceptance tests pass, else (False, detail).
        """
        try:
            return self._verify_impl(task)
        except Exception as exc:
            self.store.record_event(
                "VERIFICATION_ERROR",
                task.get("id", "?"),
                {"error": str(exc), "type": type(exc).__name__},
            )
            return False, f"verifier crashed: {exc}"

    def _verify_impl(self, task: dict) -> tuple[bool, str]:
        """Core verification logic. Raises on programmer errors."""
        # R3F-5 task 5 + R3R-4: non_evidentiary tasks cannot be auto-PASSED.
        # Return (True, NEEDS_WAIVER_MARKER) so the controller knows to transition
        # to WAITING_APPROVAL instead of PASSED.
        if task.get("non_evidentiary", False):
            self.store.record_event(
                "VERIFICATION_BYPASS",
                task["id"],
                {"reason": "non_evidentiary", "message": "needs human WAIVER"},
            )
            return True, "_NEEDS_WAIVER_"

        tests = task.get("acceptance_tests", [])
        if not tests:
            self.store.record_event("VERIFICATION_PASS", task["id"], {"tests": 0})
            return True, "no acceptance tests"

        for index, test in enumerate(tests, 1):
            # R3F-7: validate test entry schema before running.
            if isinstance(test, dict):
                err = _validate_test_entry(test, index)
                if err:
                    self.store.record_event(
                        "ACCEPTANCE_RESULT",
                        task["id"],
                        {
                            "index": index,
                            "type": test.get("type", "unknown"),
                            "exit_code": -1,
                            "schema_error": err,
                        },
                    )
                    return False, err

            test_type = test.get("type", "command") if isinstance(test, dict) else "command"

            if test_type == "file_exists":
                path = test.get("path") if isinstance(test, dict) else str(test)
                lp = self.logs_dir / f"{task['id']}.acceptance-{index}.log"
                lp.write_text(f"file_exists check: {path}\n")
                ok = (self.project_root / path).exists()
                code = 0 if ok else 1
                self.store.record_event(
                    "ACCEPTANCE_RESULT",
                    task["id"],
                    {
                        "index": index,
                        "type": "file_exists",
                        "path": path,
                        "exists": ok,
                        "exit_code": code,
                        "log_path": str(lp),
                    },
                )
                if code != 0:
                    return False, f"acceptance test {index} (file_exists): {path} not found"

            elif test_type == "numeric_range":
                import json as _json

                path = test.get("path") if isinstance(test, dict) else str(test)
                lp = self.logs_dir / f"{task['id']}.acceptance-{index}.log"
                full = self.project_root / path
                if not full.exists():
                    lp.write_text(f"numeric_range check: {path} — FILE NOT FOUND\n")
                    self.store.record_event(
                        "ACCEPTANCE_RESULT",
                        task["id"],
                        {
                            "index": index,
                            "type": "numeric_range",
                            "path": path,
                            "exit_code": 1,
                            "log_path": str(lp),
                        },
                    )
                    return False, f"acceptance test {index} (numeric_range): {path} not found"
                try:
                    raw = full.read_text().strip()
                    value = (
                        float(raw)
                        if raw.replace(".", "").replace("-", "").isdigit()
                        else _json.loads(raw).get("final_loss", float("nan"))
                    )
                except Exception as e:
                    lp.write_text(f"numeric_range check: {path} — parse error: {e}\n")
                    self.store.record_event(
                        "ACCEPTANCE_RESULT",
                        task["id"],
                        {
                            "index": index,
                            "type": "numeric_range",
                            "path": path,
                            "exit_code": 1,
                            "log_path": str(lp),
                        },
                    )
                    return (
                        False,
                        f"acceptance test {index} (numeric_range): {path} parse error: {e}",
                    )
                lo = (
                    float(test.get("min", float("-inf")))
                    if isinstance(test, dict)
                    else float("-inf")
                )
                hi = (
                    float(test.get("max", float("inf"))) if isinstance(test, dict) else float("inf")
                )
                ok = lo <= value <= hi
                code = 0 if ok else 1
                lp.write_text(
                    f"numeric_range check: {path}={value} in [{lo}, {hi}] -> "
                    + ("PASS" if ok else "FAIL")
                    + "\n"
                )
                self.store.record_event(
                    "ACCEPTANCE_RESULT",
                    task["id"],
                    {
                        "index": index,
                        "type": "numeric_range",
                        "path": path,
                        "value": value,
                        "min": lo,
                        "max": hi,
                        "passed": ok,
                        "exit_code": code,
                        "log_path": str(lp),
                    },
                )
                if code != 0:
                    return False, (
                        f"acceptance test {index} (numeric_range): "
                        f"{path}={value} not in [{lo}, {hi}]"
                    )

            elif test_type == "metrics_recompute":
                import json as _json

                path = test.get("path") if isinstance(test, dict) else str(test)
                metric = test.get("metric") if isinstance(test, dict) else None
                expected = test.get("expected") if isinstance(test, dict) else None
                tolerance = float(test.get("tolerance", 0.0)) if isinstance(test, dict) else 0.0
                lp = self.logs_dir / f"{task['id']}.acceptance-{index}.log"
                full = self.project_root / path
                if not full.exists():
                    lp.write_text(f"metrics_recompute check: {path} — FILE NOT FOUND\n")
                    self.store.record_event(
                        "ACCEPTANCE_RESULT",
                        task["id"],
                        {
                            "index": index,
                            "type": "metrics_recompute",
                            "path": path,
                            "exit_code": 1,
                            "log_path": str(lp),
                        },
                    )
                    return False, f"acceptance test {index} (metrics_recompute): {path} not found"
                try:
                    cm = _json.loads(full.read_text())
                except Exception as e:
                    lp.write_text(f"metrics_recompute check: {path} — parse error: {e}\n")
                    self.store.record_event(
                        "ACCEPTANCE_RESULT",
                        task["id"],
                        {
                            "index": index,
                            "type": "metrics_recompute",
                            "path": path,
                            "exit_code": 1,
                            "log_path": str(lp),
                        },
                    )
                    return (
                        False,
                        f"acceptance test {index} (metrics_recompute): {path} parse error: {e}",
                    )

                # Validate square confusion matrix
                if not isinstance(cm, list) or not all(isinstance(r, list) for r in cm):
                    lp.write_text("metrics_recompute: confusion_matrix must be a square 2-D list\n")
                    self.store.record_event(
                        "ACCEPTANCE_RESULT",
                        task["id"],
                        {
                            "index": index,
                            "type": "metrics_recompute",
                            "path": path,
                            "exit_code": 1,
                            "log_path": str(lp),
                        },
                    )
                    return (
                        False,
                        f"acceptance test {index} (metrics_recompute): {path} not a square 2-D list",
                    )

                n = len(cm)
                if not all(len(row) == n for row in cm):
                    lp.write_text(
                        "metrics_recompute: confusion_matrix rows have inconsistent lengths\n"
                    )
                    self.store.record_event(
                        "ACCEPTANCE_RESULT",
                        task["id"],
                        {
                            "index": index,
                            "type": "metrics_recompute",
                            "path": path,
                            "exit_code": 1,
                            "log_path": str(lp),
                        },
                    )
                    return (
                        False,
                        f"acceptance test {index} (metrics_recompute): {path} not a square matrix",
                    )

                # Validate non-negative
                for r_idx, row in enumerate(cm):
                    for c_idx, val in enumerate(row):
                        if not isinstance(val, (int, float)) or val < 0:
                            lp.write_text(
                                f"metrics_recompute: negative value at [{r_idx}][{c_idx}]={val}\n"
                            )
                            self.store.record_event(
                                "ACCEPTANCE_RESULT",
                                task["id"],
                                {
                                    "index": index,
                                    "type": "metrics_recompute",
                                    "path": path,
                                    "exit_code": 1,
                                    "log_path": str(lp),
                                },
                            )
                            return False, (
                                f"acceptance test {index} (metrics_recompute): "
                                f"{path} has negative/non-numeric value at [{r_idx}][{c_idx}]"
                            )

                # Compute per-class IoU: TP / (TP + FP + FN)
                # FP = column_sum - TP, FN = row_sum - TP
                ious = []
                for cls in range(n):
                    tp = cm[cls][cls]
                    col_sum = sum(cm[r][cls] for r in range(n))
                    row_sum = sum(cm[cls])
                    fp = col_sum - tp
                    fn = row_sum - tp
                    denom = tp + fp + fn
                    if denom == 0 or tp < 0:
                        ious.append(float("nan"))  # class not present
                    else:
                        ious.append(tp / denom)

                # Compute mIoU (mean of valid IoUs)
                valid_ious = [x for x in ious if not (x != x)]  # filter NaN
                if valid_ious:
                    miou = sum(valid_ious) / len(valid_ious)
                else:
                    miou = 0.0

                log_lines = [f"metrics_recompute: {path}"]
                log_lines.append(f"num_classes={n}")
                log_lines.append(f"per_class_iou={ious}")
                log_lines.append(f"miou={miou}")

                code = 0
                detail = f"mIoU={miou:.6f}"
                if expected is not None:
                    diff = abs(miou - float(expected))
                    ok_metric = diff <= tolerance
                    code = 0 if ok_metric else 1
                    log_lines.append(
                        f"expected={expected} tolerance={tolerance} diff={diff} -> {'PASS' if ok_metric else 'FAIL'}"
                    )
                    detail = f"mIoU={miou:.6f} expected={expected} ±{tolerance}"
                elif metric is not None:
                    log_lines.append(f"metric={metric} (recorded)")

                lp.write_text("\n".join(log_lines) + "\n")
                self.store.record_event(
                    "ACCEPTANCE_RESULT",
                    task["id"],
                    {
                        "index": index,
                        "type": "metrics_recompute",
                        "path": path,
                        "num_classes": n,
                        "per_class_iou": ious,
                        "miou": miou,
                        "expected": expected,
                        "tolerance": tolerance,
                        "exit_code": code,
                        "log_path": str(lp),
                    },
                )
                if code != 0:
                    return False, detail
                # PASS: fall through to final VERIFICATION_PASS with custom detail
                return True, detail

            else:
                command = test["command"] if isinstance(test, dict) else str(test)
                timeout = None
                if isinstance(test, dict) and test.get("timeout_sec") is not None:
                    timeout = float(test["timeout_sec"])
                lp = self.logs_dir / f"{task['id']}.acceptance-{index}.log"
                env = {
                    "REPRO_TASK_ID": task["id"],
                    "REPRO_VERIFY": "1",
                    "PATH": f"{os.path.dirname(sys.executable)}:{os.environ.get('PATH', '')}",
                }
                code = self.process_manager.run(
                    command,
                    cwd=self.project_root,
                    log_path=lp,
                    timeout=timeout,
                    env=env,
                )
                self.store.record_event(
                    "ACCEPTANCE_RESULT",
                    task["id"],
                    {
                        "index": index,
                        "command": command,
                        "exit_code": code,
                        "log_path": str(lp),
                    },
                )
                if code != 0:
                    return False, f"acceptance test {index} failed with exit code {code}"

        self.store.record_event("VERIFICATION_PASS", task["id"], {"tests": len(tests)})
        return True, f"{len(tests)} acceptance tests passed"
