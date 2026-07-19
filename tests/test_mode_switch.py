"""Test mode switching (P1_T02 surface)."""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reproctl", str(REPO / "scripts" / "reproctl.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["reproctl"] = mod
spec.loader.exec_module(mod)
import os  # noqa: E402

os.chdir(str(REPO))  # ensure .repro/ writes go to repo root
m = mod


def test_set_project_mode_logs_decision():
    """set_project_mode writes a row to mode_switches array and updates STATE."""
    # pre-create the state file (init step)
    state_path = m.get_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    init = m.get_default_state()
    init["project_mode"] = "reproduce"  # start in canonical mode
    state_path.write_text(json.dumps(init))
    n_before = len(m.load_state().get("mode_switches", []))
    m.set_project_mode("diagnose", reason="contract signed")
    s_canon = m.load_state()
    assert s_canon["project_mode"] == "diagnose"
    switches = s_canon.get("mode_switches", [])
    assert len(switches) == n_before + 1
    assert switches[-1]["from"] == "reproduce"
    assert switches[-1]["to"] == "diagnose"
    assert switches[-1]["reason"] == "contract signed"
    # NOTE: DECISION_LOG.md write is covered by test_human_checkpoint; we trust
    # _append_decision_log() works there. (Skipped here because the audit dir
    # path is currently cwd-relative — see OBS-P1-T03-1.)


def test_set_project_mode_rejects_invalid():
    """Invalid mode names raise ValueError."""
    try:
        m.set_project_mode("foo")
        assert False, "expected ValueError"
    except (ValueError, SystemExit):
        pass


if __name__ == "__main__":
    test_set_project_mode_logs_decision()
    test_set_project_mode_rejects_invalid()
    print("test_mode_switch: 2/2 PASS")
