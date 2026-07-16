"""Tests for L0-L3 scripts: smoke, overfit, mini_loop, checkpoint_resume."""

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent.resolve()


def test_l0_smoke():
    result = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts" / "smoke_test.py"),
         "--primary", str(PLUGIN_ROOT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"L0 FAIL: {result.stderr}"
    assert "PASS" in result.stdout


def test_l1_overfit():
    result = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts" / "overfit_test.py"),
         "--primary", str(PLUGIN_ROOT), "--steps", "50"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"L1 FAIL: {result.stderr}"
    assert "PASS" in result.stdout


def test_l2_mini_loop():
    result = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts" / "mini_loop_test.py"),
         "--primary", str(PLUGIN_ROOT), "--epochs", "2"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"L2 FAIL: {result.stderr}"
    assert "PASS" in result.stdout


def test_l3_checkpoint_resume():
    result = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts" / "checkpoint_resume_test.py"),
         "--primary", str(PLUGIN_ROOT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"L3 FAIL: {result.stderr}"
    assert "PASS" in result.stdout


if __name__ == "__main__":
    test_l0_smoke()
    print("L0 smoke: PASS")
    test_l1_overfit()
    print("L1 overfit: PASS")
    test_l2_mini_loop()
    print("L2 mini_loop: PASS")
    test_l3_checkpoint_resume()
    print("L3 checkpoint: PASS")
    print("All L0-L3 tests passed.")
