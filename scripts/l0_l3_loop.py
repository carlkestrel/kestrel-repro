"""
L0-L3 Loop - Automated execution of the verification hierarchy.

This script runs L0 → L1 → L2 → L3 automatically:
- L0: Static checks (import, config, paths)
- L1: Real single batch (forward/backward/eval)
- L2: Tiny overfit (small dataset, verify memorization)
- L3: Short evaluation (real checkpoint, evaluation pipeline)

Each stage must pass before the next begins.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

THIS = Path(__file__).resolve()
PACKAGE_ROOT = THIS.parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# L0-L3 Scripts
L0_SCRIPT = THIS.parent / "smoke_test.py"
L1_SCRIPT = THIS.parent / "overfit_test.py"
L2_SCRIPT = THIS.parent / "mini_loop_test.py"
L3_SCRIPT = THIS.parent / "checkpoint_resume_test.py"


class L0L3Loop:
    """Automated L0-L3 verification loop."""

    def __init__(self, project_root: Path, primary: Path | None = None,
                 conda_env: str = "t4", skip_doctor: bool = False):
        self.project_root = project_root.resolve()
        self.primary = (primary or self.project_root / "primary").resolve()
        self.conda_env = conda_env
        self.skip_doctor = skip_doctor
        self.results: dict[str, dict] = {}
        self.start_time = time.time()

    def python(self) -> str:
        """Get Python executable path."""
        return f"/home/carlkestrel/miniconda3/envs/{self.conda_env}/bin/python"

    def run_script(self, script: Path, args: list[str] | None = None) -> dict:
        """Run a test script and capture results."""
        if not script.exists():
            return {
                "status": "FAIL",
                "error": f"Script not found: {script}",
                "stdout": "",
                "stderr": "",
                "returncode": 1,
            }

        cmd = [self.python(), str(script), "--primary", str(self.primary)]
        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout per stage
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "status": "PASS" if result.returncode == 0 else "FAIL",
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "FAIL",
                "error": "Timeout (>5 min)",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "status": "FAIL",
                "error": str(e),
                "returncode": -1,
            }

    def run_l0(self) -> dict:
        """L0: Static smoke test."""
        print("\n" + "=" * 60)
        print("L0: Static Checks (smoke_test.py)")
        print("=" * 60)

        result = self.run_script(L0_SCRIPT)
        self.results["l0"] = {
            **result,
            "stage": "L0",
            "name": "Static Smoke Test",
            "timestamp": utc_now(),
        }

        if result["status"] == "PASS":
            print("✅ L0 PASSED")
        else:
            print("❌ L0 FAILED")
            if result.get("stdout"):
                print(result["stdout"])
            if result.get("stderr"):
                print(result["stderr"])

        return result

    def run_l1(self, steps: int = 50) -> dict:
        """L1: Real batch overfit test."""
        print("\n" + "=" * 60)
        print(f"L1: Real Batch Test (overfit_test.py, steps={steps})")
        print("=" * 60)

        result = self.run_script(L1_SCRIPT, ["--steps", str(steps)])
        self.results["l1"] = {
            **result,
            "stage": "L1",
            "name": "Real Batch Overfit",
            "timestamp": utc_now(),
        }

        if result["status"] == "PASS":
            print("✅ L1 PASSED")
        else:
            print("❌ L1 FAILED")
            if result.get("stdout"):
                print(result["stdout"])
            if result.get("stderr"):
                print(result["stderr"])

        return result

    def run_l2(self, epochs: int = 3) -> dict:
        """L2: Mini loop (small dataset)."""
        print("\n" + "=" * 60)
        print(f"L2: Mini Loop Test (mini_loop_test.py, epochs={epochs})")
        print("=" * 60)

        result = self.run_script(L2_SCRIPT, ["--epochs", str(epochs)])
        self.results["l2"] = {
            **result,
            "stage": "L2",
            "name": "Mini Dataset Loop",
            "timestamp": utc_now(),
        }

        if result["status"] == "PASS":
            print("✅ L2 PASSED")
        else:
            print("❌ L2 FAILED")
            if result.get("stdout"):
                print(result["stdout"])
            if result.get("stderr"):
                print(result["stderr"])

        return result

    def run_l3(self) -> dict:
        """L3: Checkpoint resume and evaluation."""
        print("\n" + "=" * 60)
        print("L3: Checkpoint Resume Test (checkpoint_resume_test.py)")
        print("=" * 60)

        result = self.run_script(L3_SCRIPT)
        self.results["l3"] = {
            **result,
            "stage": "L3",
            "name": "Checkpoint Resume",
            "timestamp": utc_now(),
        }

        if result["status"] == "PASS":
            print("✅ L3 PASSED")
        else:
            print("❌ L3 FAILED")
            if result.get("stdout"):
                print(result["stdout"])
            if result.get("stderr"):
                print(result["stderr"])

        return result

    def run_all(self, stop_on_fail: bool = True,
                l1_steps: int = 50,
                l2_epochs: int = 3) -> dict:
        """
        Run the complete L0-L3 loop.

        Args:
            stop_on_fail: Stop on first failure
            l1_steps: Number of steps for L1
            l2_epochs: Number of epochs for L2

        Returns:
            Complete results dictionary
        """
        print("\n" + "=" * 60)
        print("Starting L0-L3 Automated Verification Loop")
        print(f"Project: {self.project_root}")
        print(f"Primary: {self.primary}")
        print(f"Start time: {utc_now()}")
        print("=" * 60)

        stages = [
            ("L0", lambda: self.run_l0()),
            ("L1", lambda: self.run_l1(l1_steps)),
            ("L2", lambda: self.run_l2(l2_epochs)),
            ("L3", lambda: self.run_l3()),
        ]

        for stage_name, stage_func in stages:
            result = stage_func()
            if result["status"] == "FAIL" and stop_on_fail:
                print(f"\n⚠️  Stopping loop due to {stage_name} failure")
                break

        # Summary
        elapsed = time.time() - self.start_time
        passed = sum(1 for r in self.results.values() if r.get("status") == "PASS")
        total = len(self.results)

        summary = {
            "project_root": str(self.project_root),
            "primary": str(self.primary),
            "start_time": utc_now(),
            "end_time": utc_now(),
            "elapsed_seconds": round(elapsed, 1),
            "total_stages": total,
            "passed_stages": passed,
            "failed_stages": total - passed,
            "all_passed": passed == total,
            "results": self.results,
        }

        print("\n" + "=" * 60)
        print("L0-L3 Loop Complete")
        print("=" * 60)
        print(f"Stages passed: {passed}/{total}")
        print(f"Elapsed time: {elapsed:.1f}s")
        print(f"Status: {'✅ ALL PASSED' if passed == total else '❌ SOME FAILED'}")
        print("=" * 60)

        return summary

    def save_results(self, output_path: Path | None = None) -> Path:
        """Save results to JSON file."""
        if output_path is None:
            output_path = self.project_root / "artifacts" / "l0_l3_results.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = {
            "project_root": str(self.project_root),
            "timestamp": utc_now(),
            "results": self.results,
        }

        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Results saved to: {output_path}")

        return output_path


def main():
    parser = argparse.ArgumentParser(description="Run L0-L3 automated verification loop")
    parser.add_argument("--project", default=".",
                       help="Project root directory")
    parser.add_argument("--primary",
                       help="Primary repository directory")
    parser.add_argument("--conda-env", default="t4",
                       help="Conda environment with torch")
    parser.add_argument("--skip-doctor", action="store_true",
                       help="Skip preflight doctor check")
    parser.add_argument("--l1-steps", type=int, default=50,
                       help="L1: number of overfit steps")
    parser.add_argument("--l2-epochs", type=int, default=3,
                       help="L2: number of mini loop epochs")
    parser.add_argument("--continue-on-fail", action="store_true",
                       help="Continue to next stage on failure")
    parser.add_argument("--output",
                       help="Output path for results JSON")
    parser.add_argument("--save-only", action="store_true",
                       help="Only save results, don't print")

    args = parser.parse_args()

    project = Path(args.project).resolve()
    primary = Path(args.primary) if args.primary else None

    loop = L0L3Loop(
        project_root=project,
        primary=primary,
        conda_env=args.conda_env,
        skip_doctor=args.skip_doctor,
    )

    # Run the loop
    summary = loop.run_all(
        stop_on_fail=not args.continue_on_fail,
        l1_steps=args.l1_steps,
        l2_epochs=args.l2_epochs,
    )

    # Save results
    output_path = Path(args.output) if args.output else None
    results_path = loop.save_results(output_path)

    # Print summary if not save-only
    if not args.save_only:
        print(json.dumps(summary, indent=2, default=str))

    # Exit code
    sys.exit(0 if summary["all_passed"] else 1)


if __name__ == "__main__":
    main()
