"""Golden test for project B: PointNet point cloud classification.

This test:
1. Creates a temp project dir
2. Copies the golden plan and train.py
3. Runs: reproctl run --until blocked-or-complete
4. Asserts: all 6 tasks PASS
5. Asserts: model checkpoint exists and loads
6. Asserts: metrics are in expected range
7. Asserts: no RUNNING tasks after completion
"""

import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent.parent.resolve()


def test_golden_pointcloud_B_full_chain():
    """Golden B: P1→P6 completes without human input."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)

        # Copy golden fixture
        fixture = PLUGIN_ROOT / "fixtures" / "golden_pointcloud_B"
        shutil.copytree(fixture, project / "golden_pointcloud_B")
        plan_path = project / "golden_pointcloud_B" / "plan.yaml"

        # Run the chain
        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "reproctl.py"),
             "run",
             "--project", str(project / "golden_pointcloud_B"),
             "--plan", str(plan_path),
             "--mode", "strict",
             "--automation", "safe-auto",
             "--until", "blocked-or-complete"],
            capture_output=True, text=True, timeout=300,
        )

        assert result.returncode == 0, (
            f"Non-zero exit: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        # Check state store exists
        state_db = project / "golden_pointcloud_B" / ".repro" / "execution" / "state.sqlite3"
        assert state_db.exists(), "state.sqlite3 not created"

        # Check no RUNNING tasks
        import sqlite3
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
        running = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='RUNNING'"
        ).fetchone()[0]
        conn.close()
        assert running == 0, f"Still have {running} RUNNING tasks after completion"

        # Check metrics
        metrics = project / "golden_pointcloud_B" / "checkpoints" / "metrics.json"
        if metrics.exists():
            m = json.loads(metrics.read_text())
            assert m["final_loss"] >= 0, "final_loss should be non-negative"
            assert m["final_loss"] < 100, "final_loss should be reasonable"
            assert m["dataset_size"] == 20, "dataset_size should be 20"
            assert m["point_count"] == 128, "point_count should be 128"


def test_golden_pointcloud_B_model_loads():
    """Golden B: model checkpoint can be loaded after completion."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)

        # Copy fixture and run
        fixture = PLUGIN_ROOT / "fixtures" / "golden_pointcloud_B"
        shutil.copytree(fixture, project / "golden_pointcloud_B")
        plan_path = project / "golden_pointcloud_B" / "plan.yaml"

        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "reproctl.py"),
             "run",
             "--project", str(project / "golden_pointcloud_B"),
             "--plan", str(plan_path),
             "--mode", "strict",
             "--automation", "safe-auto",
             "--until", "blocked-or-complete"],
            capture_output=True, text=True, timeout=300,
        )

        # Verify model loads
        ckpt = project / "golden_pointcloud_B" / "checkpoints" / "pointnet.pt"
        assert ckpt.exists(), "pointnet.pt should exist"

        # Try to load the model
        load_result = subprocess.run(
            [sys.executable, "-c",
             f"import torch; m=torch.load('{ckpt}'); print('loaded:', type(m))"],
            capture_output=True, text=True, timeout=30,
            cwd=project / "golden_pointcloud_B",
        )
        assert load_result.returncode == 0, (
            f"Failed to load model: {load_result.stderr}"
        )
        assert "loaded:" in load_result.stdout


def test_golden_pointcloud_B_evidence_chain():
    """Golden B: evidence chain is complete for all PASS tasks."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)

        # Copy fixture and run
        fixture = PLUGIN_ROOT / "fixtures" / "golden_pointcloud_B"
        shutil.copytree(fixture, project / "golden_pointcloud_B")
        plan_path = project / "golden_pointcloud_B" / "plan.yaml"

        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "reproctl.py"),
             "run",
             "--project", str(project / "golden_pointcloud_B"),
             "--plan", str(plan_path),
             "--mode", "strict",
             "--automation", "safe-auto",
             "--until", "blocked-or-complete"],
            capture_output=True, text=True, timeout=300,
        )

        # Check events exist
        state_db = project / "golden_pointcloud_B" / ".repro" / "execution" / "state.sqlite3"
        assert state_db.exists(), "state.sqlite3 not created"

        import sqlite3
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)

        # All 6 tasks should have PASSED events
        for task_id in ["P1_init", "P2_env", "P3_data", "P4_train", "P5_verify", "P6_audit"]:
            passed_count = conn.execute(
                "SELECT COUNT(*) FROM events WHERE event_type='TASK_PASSED' AND task_id=?",
                (task_id,)
            ).fetchone()[0]
            assert passed_count >= 1, f"{task_id} should have at least one TASK_PASSED event"

        # PLAN_COMPLETE event should exist
        complete_count = conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type='PLAN_COMPLETE'"
        ).fetchone()[0]
        assert complete_count >= 1, "PLAN_COMPLETE event should exist"

        conn.close()


if __name__ == "__main__":
    test_golden_pointcloud_B_full_chain()
    print("All golden B tests passed.")
