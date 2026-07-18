"""Tests for metrics_recompute acceptance test type."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

THIS = Path(__file__).resolve()
PLUGIN_ROOT = THIS.parents[1]
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from orchestrator import ProcessManager, StateStore, Verifier  # noqa: E402


@pytest.fixture
def verifier(tmp_path):
    proj = tmp_path / "metrics_proj"
    proj.mkdir()
    (proj / ".repro" / "execution" / "logs").mkdir(parents=True, exist_ok=True)
    (proj / "output").mkdir(exist_ok=True)
    store = StateStore(proj)
    store.initialize_plan(
        {
            "plan_id": "metrics-test",
            "mode": "strict",
            "tasks": [{
                "id": "t1", "name": "t1", "gate": "safe",
                "deps": [], "command": "echo t1",
                "timeout_min": 1,
                "acceptance_tests": [],
                "retry_policy": {"max_retries": 0},
            }],
            "mandatory_task_ids": ["t1"],
            "budgets": {},
        },
        plan_path=str(proj / "plan.yaml"),
    )
    return proj, store, Verifier(proj, store, ProcessManager())


def _write_cm(proj: Path, name: str, cm: list[list[float]]) -> str:
    """Write confusion matrix JSON to proj/output and return relative path string."""
    (proj / "output").mkdir(exist_ok=True)
    p = proj / "output" / name
    p.write_text(json.dumps(cm), encoding="utf-8")
    return f"output/{name}"


class TestMetricsRecompute:
    def test_correct_confmat_passes(self, verifier):
        """Correct confusion matrix → PASS with mIoU computed."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json", [[10, 0], [0, 10]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "metric": "mIoU",
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is True, detail
        assert "mIoU" in detail

    def test_wrong_miou_fails(self, verifier):
        """Wrong mIoU (outside tolerance) → FAIL."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json", [[5, 5], [5, 5]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "expected": 0.9,
                "tolerance": 0.01,
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is False
        assert "mIoU" in detail

    def test_within_tolerance_passes(self, verifier):
        """mIoU within tolerance → PASS."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json", [[10, 0], [0, 10]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "expected": 1.0,
                "tolerance": 0.001,
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is True, detail

    def test_missing_file_fails(self, verifier):
        """Non-existent confusion matrix → FAIL."""
        proj, store, v = verifier
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": str(proj / "output" / "nonexistent.json"),
                "metric": "mIoU",
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is False
        assert "not found" in detail

    def test_invalid_json_fails(self, verifier):
        """Invalid JSON → FAIL."""
        proj, store, v = verifier
        (proj / "output").mkdir(exist_ok=True)
        bad = proj / "output" / "bad.json"
        bad.write_text("{ not valid json }", encoding="utf-8")
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": str(bad.resolve()),
                "metric": "mIoU",
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is False
        assert "parse error" in detail

    def test_non_square_matrix_fails(self, verifier):
        """Non-square matrix → FAIL."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json", [[1, 2, 3], [4, 5, 6]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "metric": "mIoU",
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is False
        assert "not a square" in detail

    def test_negative_value_fails(self, verifier):
        """Negative confusion matrix value → FAIL."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json", [[10, -1], [0, 10]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "metric": "mIoU",
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is False
        assert "negative" in detail.lower()

    def test_multiclass_miou(self, verifier):
        """3-class confusion matrix: mIoU computed correctly."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json",
                            [[10, 0, 0], [0, 8, 2], [0, 1, 9]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "metric": "mIoU",
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is True
        assert "mIoU" in detail

    def test_tolerance_boundary_exact(self, verifier):
        """At exact boundary (diff == tolerance) → PASS (≤)."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json", [[5, 0], [0, 5]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "expected": 1.0,
                "tolerance": 0.0,
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is True, detail

    def test_tolerance_boundary_just_outside(self, verifier):
        """Just outside tolerance (diff = tolerance + epsilon) → FAIL."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json", [[10, 0], [0, 10]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "expected": 0.999,
                "tolerance": 0.0009,  # diff = 0.001 > 0.0009 → FAIL
            }],
            "non_evidentiary": False,
        }
        ok, detail = v.verify(task)
        assert ok is False

    def test_emits_acceptance_result_event(self, verifier):
        """metrics_recompute emits ACCEPTANCE_RESULT event with mIoU field."""
        proj, store, v = verifier
        cm_path = _write_cm(proj, "confmat.json", [[10, 0], [0, 10]])
        task = {
            "id": "t1",
            "acceptance_tests": [{
                "type": "metrics_recompute",
                "path": cm_path,
                "expected": 1.0,
                "tolerance": 0.01,
            }],
            "non_evidentiary": False,
        }
        seq_before = store.events()[-1]["seq"] if store.events() else 0
        v.verify(task)
        events = [e for e in store.events(after_seq=seq_before)]
        assert any(e["event_type"] == "ACCEPTANCE_RESULT" for e in events)
        result_event = next(e for e in events if e["event_type"] == "ACCEPTANCE_RESULT")
        assert "miou" in result_event["payload"]
