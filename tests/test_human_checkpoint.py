"""Test the 12-item human checkpoint (P3_T02 surface)."""
import sys, importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reproctl", str(REPO / "scripts" / "reproctl.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["reproctl"] = mod
spec.loader.exec_module(mod)
import os  # noqa: E402
os.chdir(str(REPO))
m = mod


def test_default_flag_blocks():
    """HUMAN_CHECKPOINT=true (default) → check returns 1."""
    s = m._load_state()
    s["flags"]["HUMAN_CHECKPOINT"] = True
    m._save_state(s)
    rc = m.human_checkpoint(action="check")
    assert rc == 1, f"expected 1, got {rc}"


def test_disabled_flag_passes():
    """HUMAN_CHECKPOINT=false → check returns 0."""
    s = m._load_state()
    s["flags"]["HUMAN_CHECKPOINT"] = False
    m._save_state(s)
    rc = m.human_checkpoint(action="check")
    assert rc == 0


def test_override_requires_approver():
    """override without --approved-by returns 2."""
    rc = m.human_checkpoint(action="override", reason="x")
    assert rc == 2


def test_override_with_approver_returns_zero():
    """override with --approved-by returns 0 + writes decision row."""
    rc = m.human_checkpoint(action="override", reason="demo", approved_by="alice", item="P3_T02")
    assert rc == 0
    log = (m._state_path().parent / "DECISION_LOG.md").read_text()
    assert "approved_by=alice" in log


def test_twelve_items_listed():
    """The 12-item list is exposed and non-empty."""
    assert len(m.HUMAN_CHECKPOINT_ITEMS) == 12
    items_text = " ".join(m.HUMAN_CHECKPOINT_ITEMS).lower()
    for kw in ["synthesize","split","metric","oom","loss","batch","amp","checkpoint","cherry","extend","budget","cannot"]:
        assert kw in items_text, f"missing: {kw}"


if __name__ == "__main__":
    test_default_flag_blocks()
    test_disabled_flag_passes()
    test_override_requires_approver()
    test_override_with_approver_returns_zero()
    test_twelve_items_listed()
    print("test_human_checkpoint: 5/5 PASS")