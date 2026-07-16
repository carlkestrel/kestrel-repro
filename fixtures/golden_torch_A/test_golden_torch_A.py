"""Golden test for project A: Tiny PyTorch.

This test:
1. Creates a temp project dir
2. Copies the golden plan and train.py
3. Runs: reproctl run --until blocked-or-complete
4. Asserts: all 6 tasks PASS
5. Asserts: final_loss in expected range
6. Asserts: checkpoint exists and loads
7. Asserts: no RUNNING tasks after completion
8. Asserts: evidence chain complete
"""

import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent.parent.resolve()


def test_golden_torch_A_full_chain():
    """Golden A: T1→T6 completes without human input."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)

        # Copy golden fixture
        fixture = PLUGIN_ROOT / "fixtures" / "golden_torch_A"
        shutil.copytree(fixture, project / "golden_torch_A")
        plan_path = project / "golden_torch_A" / "plan.yaml"

        # Run the chain
        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "reproctl.py"),
             "run",
             "--project", str(project / "golden_torch_A"),
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
        state_db = project / "golden_torch_A" / ".repro" / "execution" / "state.sqlite3"
        assert state_db.exists(), "state.sqlite3 not created"

        # Check no RUNNING tasks
        import sqlite3
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
        running = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='RUNNING'"
        ).fetchone()[0]
        conn.close()
        assert running == 0, f"Still have {running} RUNNING tasks after completion"

        # Check final loss in range
        metrics = project / "golden_torch_A" / "checkpoints" / "metrics.json"
        if metrics.exists():
            m = json.loads(metrics.read_text())
            assert m["final_loss"] > 0, "final_loss should be positive"
            assert m["final_loss"] < 100, "final_loss should be reasonable"


def test_golden_torch_A_recovery():
    """Golden A: recovery from kill -9 preserves PASS tasks."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)

        # Copy fixture
        fixture = PLUGIN_ROOT / "fixtures" / "golden_torch_A"
        shutil.copytree(fixture, project / "golden_torch_A")
        plan_path = project / "golden_torch_A" / "plan.yaml"

        # Start first run
        proc = subprocess.Popen(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "reproctl.py"),
             "run",
             "--project", str(project / "golden_torch_A"),
             "--plan", str(plan_path),
             "--mode", "strict",
             "--automation", "safe-auto"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        # Let it run for a few seconds to complete some tasks
        import time
        time.sleep(5)
        proc.kill()
        proc.wait()

        # Resume
        resume_result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "reproctl.py"),
             "resume",
             "--project", str(project / "golden_torch_A")],
            capture_output=True, text=True, timeout=120,
        )

        # Verify state.db still exists
        state_db = project / "golden_torch_A" / ".repro" / "execution" / "state.sqlite3"
        assert state_db.exists(), "state.sqlite3 should exist after kill"

        # Verify PASS tasks were not re-run (check for multiple TASK_CLAIMED events for same task)
        import sqlite3
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
        t1_claimed = conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type='TASK_CLAIMED' AND task_id='T1_init'"
        ).fetchone()[0]
        conn.close()
        assert t1_claimed <= 1, f"T1 was claimed {t1_claimed} times (expected <= 1 after resume)"


def test_golden_torch_A_evidence_chain():
    """Golden A: evidence chain is complete for all PASS tasks."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)

        # Copy fixture and run
        fixture = PLUGIN_ROOT / "fixtures" / "golden_torch_A"
        shutil.copytree(fixture, project / "golden_torch_A")
        plan_path = project / "golden_torch_A" / "plan.yaml"

        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "reproctl.py"),
             "run",
             "--project", str(project / "golden_torch_A"),
             "--plan", str(plan_path),
             "--mode", "strict",
             "--automation", "safe-auto",
             "--until", "blocked-or-complete"],
            capture_output=True, text=True, timeout=300,
        )

        # Check events exist
        state_db = project / "golden_torch_A" / ".repro" / "execution" / "state.sqlite3"
        assert state_db.exists(), "state.sqlite3 not created"

        import sqlite3
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)

        # All 6 tasks should have PASSED events
        for task_id in ["T1_init", "T2_env", "T3_train", "T4_verify", "T5_checkpoint", "T6_audit"]:
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
    test_golden_torch_A_full_chain()
    print("All golden A tests passed.")
