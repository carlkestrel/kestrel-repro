"""Test the project state machine (mode transitions)."""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reproctl", str(REPO / "scripts" / "reproctl.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["reproctl"] = mod  # register for @dataclass etc.
spec.loader.exec_module(mod)
import os  # noqa: E402

os.chdir(str(REPO))
m = mod


def test_valid_project_modes():
    """The three canonical modes are: reproduce, diagnose, extend."""
    assert "reproduce" in m.VALID_PROJECT_MODES
    assert "diagnose" in m.VALID_PROJECT_MODES
    assert "extend" in m.VALID_PROJECT_MODES


def test_default_state():
    """Default state has HUMAN_CHECKPOINT=true and WIP_LIMIT=1.

    The state is materialized from _load_state() which creates state["flags"]
    from control_flags.md defaults. Key properties:
    1. state["flags"] exists
    2. HUMAN_CHECKPOINT is the Python bool True (not string "True")
    3. WIP_LIMIT is the integer 1 (not string "1")

    Uses == for boolean coercion safety across JSON serialization.
    Before calling _load_state(), we ensure a clean state by removing any
    existing STATE.json so it gets re-materialized from defaults.
    """
    # Ensure clean state: remove existing STATE.json so _load_state()
    # re-materializes from defaults
    p = m._state_path()
    if p.exists():
        p.unlink()
    state = m._load_state()
    assert "flags" in state, "state must have flags block"
    # Validate required flag keys exist
    for key in ["HUMAN_CHECKPOINT", "WIP_LIMIT"]:
        assert key in state["flags"], f"required flag {key} missing from state"
    # HUMAN_CHECKPOINT must be bool True (not string "True")
    assert state["flags"]["HUMAN_CHECKPOINT"] == True, (
        f"HUMAN_CHECKPOINT must be True (bool), got {state['flags']['HUMAN_CHECKPOINT']!r}"
    )
    # WIP_LIMIT must be int 1 (not string "1")
    assert state["flags"]["WIP_LIMIT"] == 1, (
        f"WIP_LIMIT must be 1 (int), got {state['flags']['WIP_LIMIT']!r}"
    )


def test_state_machine_round_trip(tmp_path):
    """State round-trips through disk correctly."""
    p = m._state_path()
    assert p.exists(), "state file should be materialized on load"
    s = m._load_state()
    s["flags"]["AUTO_RETRY"] = True
    m._save_state(s)
    s2 = m._load_state()
    assert s2["flags"]["AUTO_RETRY"] is True


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        import os

        old_cwd = os.getcwd()
        try:
            test_valid_project_modes()
            test_default_state()
            test_state_machine_round_trip(Path(td))
            print("test_state_machine: 3/3 PASS")
        finally:
            os.chdir(old_cwd)
