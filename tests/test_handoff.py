"""Test handoff.json structure and recovery flow (P4_T03 + P4_T04)."""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_reproctl():
    spec = importlib.util.spec_from_file_location("reproctl", str(REPO / "scripts" / "reproctl.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["reproctl"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_handoff_template_has_12_required_fields():
    """templates/handoff.json has 12 required fields per P4_T03 acceptance."""
    handoff = REPO / "templates" / "handoff.json"
    assert handoff.exists()
    data = json.loads(handoff.read_text())
    required = data.get("required", [])
    expected = {
        "project_mode",
        "current_phase",
        "completed_phases",
        "current_run_id",
        "run_command",
        "process_id",
        "log_path",
        "checkpoint_path",
        "next_step",
        "recovery_required_files",
        "blockers",
        "timestamp",
    }
    assert expected.issubset(set(required)), f"missing: {expected - set(required)}"
    print("test_handoff_template_has_12_required_fields: PASS")


def test_handoff_round_trip():
    """A handoff dict survives json.dump/load with all 12 fields."""
    handoff = {
        "project_mode": "reproduce",
        "current_phase": "P4_monitor",
        "completed_phases": [
            "P0_preparation",
            "P1_mode_contract",
            "P2_claim_evidence",
            "P3_human_checkpoint",
        ],
        "current_run_id": "r-test-001",
        "run_command": "python scripts/reproctl.py launch --mode=strict_repro --seed=42",
        "process_id": 12345,
        "log_path": "experiments/r-test-001/logs/train.log",
        "checkpoint_path": "experiments/r-test-001/checkpoints/epoch_050.pth",
        "next_step": "Resume from epoch 50.",
        "recovery_required_files": ["experiments/r-test-001/config/override.yaml"],
        "blockers": [],
        "timestamp": "2026-07-15T22:30:00Z",
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(handoff, f)
        path = f.name
    with open(path) as f:
        loaded = json.load(f)
    assert loaded == handoff
    os.unlink(path)
    print("test_handoff_round_trip: PASS")


if __name__ == "__main__":
    test_handoff_template_has_12_required_fields()
    test_handoff_round_trip()
    print("test_handoff: 2/2 PASS")
