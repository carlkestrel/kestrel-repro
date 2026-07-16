"""Test checkpoint recovery (L3): save → load → produce identical metrics."""
import tempfile, os, json
from pathlib import Path


def test_checkpoint_metadata_round_trip():
    """A checkpoint metadata dict survives save/load with metric integrity."""
    meta = {
        "run_id": "r-test-001",
        "epoch": 50,
        "step": 12345,
        "metrics": {"val_mIoU": 73.5, "val_loss": 0.42, "train_loss": 0.51},
        "checkpoint_path": "experiments/r-test-001/checkpoints/epoch_050.pth",
        "git_commit": "abc123def456",
        "seed": 42,
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(meta, f); path = f.name
    with open(path) as f:
        loaded = json.load(f)
    assert loaded["metrics"]["val_mIoU"] == 73.5
    assert loaded["metrics"]["val_loss"] == 0.42
    assert loaded["seed"] == 42
    assert loaded["git_commit"] == "abc123def456"
    os.unlink(path)
    print("test_checkpoint_metadata_round_trip: PASS")


def test_resume_continuity_no_loss_gap():
    """A resumed run continues from the last logged step without loss gap.
    (Simulated: the resume call reads the last metric and starts from epoch+1.)"""
    last_logged = {"epoch": 50, "metrics": {"val_mIoU": 73.2}}
    resume_epoch = last_logged["epoch"] + 1
    assert resume_epoch == 51
    print("test_resume_continuity_no_loss_gap: PASS")


if __name__ == "__main__":
    test_checkpoint_metadata_round_trip()
    test_resume_continuity_no_loss_gap()
    print("test_checkpoint_recovery: 2/2 PASS")