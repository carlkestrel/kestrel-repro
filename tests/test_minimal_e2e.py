"""End-to-end test: run the minimal PyTorch fixture through a fake
`/repro-launch` flow and verify all artifacts appear in the right places."""
import subprocess, json, shutil, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "fixtures" / "minimal_pytorch_repo" / "train.py"


def test_fixture_train_produces_expected_artifacts():
    """Running the fixture writes checkpoints/, logs/, metrics/ in the expected layout."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "fixture-run"
        r = subprocess.run([
            "python3", str(FIXTURE),
            "--epochs", "2", "--seed", "42",
            "--output-dir", str(out),
        ], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"train failed:\n{r.stderr}"

        # checkpoints/ — accept either .pth (with torch) or .json (numpy fallback)
        ckpts = sorted((out / "checkpoints").glob("epoch_*.*"))
        assert len(ckpts) == 2, f"expected 2 ckpts, got {len(ckpts)}"

        # logs/
        assert (out / "logs" / "train.log").exists()
        log = (out / "logs" / "train.log").read_text()
        assert "epoch=1 step=1" in log
        assert "epoch=2 step=5" in log

        # metrics/
        metrics = json.loads((out / "metrics" / "raw_metrics.json").read_text())
        assert len(metrics) == 2
        assert metrics[0]["epoch"] == 1
        assert "mean_loss" in metrics[0]


def test_fixture_determinism():
    """Same seed → identical final mean_loss across two runs."""
    with tempfile.TemporaryDirectory() as td:
        out1 = Path(td) / "run1"
        out2 = Path(td) / "run2"
        for out in (out1, out2):
            subprocess.run([
                "python3", str(FIXTURE),
                "--epochs", "2", "--seed", "42",
                "--output-dir", str(out),
            ], check=True, capture_output=True)
        m1 = json.loads((out1 / "metrics" / "raw_metrics.json").read_text())
        m2 = json.loads((out2 / "metrics" / "raw_metrics.json").read_text())
        assert abs(m1[-1]["mean_loss"] - m2[-1]["mean_loss"]) < 1e-6, \
            f"determinism broken: {m1[-1]} vs {m2[-1]}"


if __name__ == "__main__":
    test_fixture_train_produces_expected_artifacts()
    test_fixture_determinism()
    print("test_minimal_e2e: 2/2 PASS")