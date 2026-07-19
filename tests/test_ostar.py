"""Tests for the OSTAR module."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))


# ─────────────────────────────────────────────────────────────────────────────
# Constants tests
# ─────────────────────────────────────────────────────────────────────────────


def test_exit_codes_are_distinct():
    from scripts.ostar import constants as C

    codes = [
        C.EXIT_OK,
        C.EXIT_BAD_CONFIG,
        C.EXIT_GUARD_FAIL,
        C.EXIT_ALREADY_RUNNING,
        C.EXIT_REHEARSAL_FAIL,
        C.EXIT_TEST_FAILED,
        C.EXIT_REPAIR_EXHAUSTED,
        C.EXIT_RESUME_FAILED,
        C.EXIT_HARDWARE_SAFETY,
        C.EXIT_INTERNAL,
        C.EXIT_MANUAL_STOP,
        C.EXIT_DURATION_ENDED,
    ]
    assert len(codes) == len(set(codes)), "exit codes must be distinct"


def test_verdict_values():
    from scripts.ostar import constants as C

    verdicts = [
        C.VERDICT_SOAK_VERIFIED,
        C.VERDICT_REPAIRED_NOT_SOAK_VERIFIED,
        C.VERDICT_FAILED_UNRESOLVED,
        C.VERDICT_BLOCKED_REQUIRES_REVIEW,
        C.VERDICT_ABORTED_HARDWARE,
    ]
    assert len(verdicts) == len(set(verdicts))


def test_error_classes_no_overlap():
    from scripts.ostar import constants as C

    blocked = C.BLOCKED_CLASSES
    allowed = C.AUTO_REPAIR_CLASSES
    overlap = blocked & allowed
    assert not overlap, f"BLOCKED and AUTO_REPAIR must not overlap: {overlap}"


def test_duration_parsing():
    from scripts.ostar.config import OSTARConfig

    assert OSTARConfig._parse_duration("8h") == 8 * 3600
    assert OSTARConfig._parse_duration("30m") == 30 * 60
    assert OSTARConfig._parse_duration("480m") == 480 * 60
    assert OSTARConfig._parse_duration("28800s") == 28800
    assert OSTARConfig._parse_duration("28800") == 28800


def test_duration_parsing_invalid():
    from scripts.ostar.config import OSTARConfig

    assert OSTARConfig._parse_duration("") == 8 * 3600  # default
    assert OSTARConfig._parse_duration("xyz") == 8 * 3600  # fallback


def test_config_validate():
    from scripts.ostar.config import OSTARConfig

    cfg = OSTARConfig(auto_repair_level="invalid")
    errors = cfg.validate()
    assert any("auto_repair_level" in e for e in errors)

    cfg2 = OSTARConfig(disk_reserve_gb=0.5)
    errors2 = cfg2.validate()
    assert any("disk_reserve_gb" in e for e in errors2)


def test_config_to_dict_roundtrip():
    from scripts.ostar.config import OSTARConfig

    cfg = OSTARConfig(
        timezone="UTC",
        duration_seconds=7200,
        max_repairs=5,
        auto_repair_level="full",
    )
    d = cfg.to_dict()
    assert d["timezone"] == "UTC"
    assert d["duration_seconds"] == 7200
    assert d["max_repairs"] == 5
    assert d["auto_repair_level"] == "full"


def test_config_from_args():
    from scripts.ostar.config import OSTARConfig

    args = {
        "project": "/tmp/proj",
        "duration": "4h",
        "max_repairs": "7",
        "max_retries": "2",
        "disk_reserve": "15",
        "gpu_temperature_limit": "80",
        "auto_repair_level": "full",
        "run_ci_stress": True,
        "run_gpu_stress": False,
        "verbose": False,
        "dry_run": False,
        "soak_root": None,
    }
    cfg = OSTARConfig.from_args(args)
    assert cfg.duration_seconds == 4 * 3600
    assert cfg.max_repairs == 7
    assert cfg.max_retries_per_bug == 2
    assert cfg.disk_reserve_gb == 15.0
    assert cfg.gpu_temperature_limit == 80
    assert cfg.auto_repair_level == "full"


# ─────────────────────────────────────────────────────────────────────────────
# SoakStateStore tests
# ─────────────────────────────────────────────────────────────────────────────


def test_soak_state_init_run(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    run_id = store.init_run({"duration": 7200})
    assert run_id.startswith("soak_")
    assert (tmp_path / "soak_manifest.json").exists()
    assert (tmp_path / "soak.sqlite3").exists()


def test_soak_state_heartbeat(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    run_id = store.init_run({})
    store.heartbeat(run_id, os.getpid(), {"test": True})
    assert (tmp_path / "heartbeat.json").exists()
    data = json.loads((tmp_path / "heartbeat.json").read_text())
    assert data["run_id"] == run_id
    assert data["detail"]["test"] is True


def test_soak_state_cycle_record(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    run_id = store.init_run({})
    cycle_id = store.record_cycle(run_id, seq=1, status="PASS")
    assert cycle_id >= 1
    cycles = store.get_cycles(run_id)
    assert len(cycles) == 1
    assert cycles[0]["status"] == "PASS"


def test_soak_state_bug_upsert(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    run_id = store.init_run({})
    bug_id = store.upsert_bug(run_id, "abc123", "CODE")
    assert bug_id.startswith("SOAK-BUG-")
    bugs = store.get_bugs(run_id)
    assert len(bugs) == 1
    assert bugs[0]["error_class"] == "CODE"


def test_soak_state_bug_upsert_increments(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    run_id = store.init_run({})
    store.upsert_bug(run_id, "abc123", "CODE")
    store.upsert_bug(run_id, "abc123", "CODE")  # same fingerprint
    bugs = store.get_bugs(run_id)
    assert len(bugs) == 1  # same bug, updated
    assert bugs[0]["occurrences"] == 2


def test_soak_state_ci_result(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    run_id = store.init_run({})
    cycle_id = store.record_cycle(run_id, 1, "PASS")
    store.record_ci_result(run_id, cycle_id, "CI_STRESS", 10, 0, 0, 30.0, False)
    summary = store.get_ci_summary(run_id)
    assert "CI_STRESS" in summary
    assert summary["CI_STRESS"]["total_pass"] == 10
    assert summary["CI_STRESS"]["total_fail"] == 0
    assert summary["CI_STRESS"]["flaky_count"] == 0


def test_soak_state_repair(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    run_id = store.init_run({})
    bug_id = store.upsert_bug(run_id, "xyz", "CODE")
    repair_id = store.record_repair(
        run_id,
        bug_id,
        1,
        patch={"file": "test.py", "line": 10},
        status="PASS",
        target_test_passed=True,
        regression_passed=True,
    )
    assert repair_id.startswith("REPAIR-")
    repairs = store.get_repairs(run_id)
    assert len(repairs) == 1
    assert repairs[0]["status"] == "PASS"


def test_soak_state_checkpoints(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    store.init_run({})
    ckpt = store.write_checkpoint({"seq": 42, "test": True}, seq=42)
    assert ckpt.exists()
    latest = store.latest_checkpoint()
    assert latest == ckpt


def test_soak_state_status_summary(tmp_path):
    from scripts.ostar import soak_state

    store = soak_state.SoakStateStore(tmp_path)
    store.init_run({})
    summary = store.status_summary()
    assert summary["status"] != "IDLE"
    assert "run_id" in summary


# ─────────────────────────────────────────────────────────────────────────────
# Hardware monitor tests
# ─────────────────────────────────────────────────────────────────────────────


def test_hardware_monitor_snapshot(tmp_path):
    from scripts.ostar import hardware_monitor

    hw = hardware_monitor.HardwareMonitor(project_root=tmp_path)
    snap = hw.snapshot()
    assert "timestamp_utc" in snap.to_dict()
    assert "gpu_available" in snap.to_dict()
    assert snap.disk_free_gb >= 0


def test_hardware_monitor_policy_defaults():
    from scripts.ostar import constants as C
    from scripts.ostar import hardware_monitor

    policy = hardware_monitor.HardwarePolicy()
    assert policy.gpu_warn_temp_c == C.DEFAULT_GPU_WARN_TEMP_C
    assert policy.gpu_critical_temp_c == C.DEFAULT_GPU_CRITICAL_TEMP_C
    assert policy.disk_reserve_gb == C.DEFAULT_DISK_RESERVE_GB


def test_hardware_monitor_check_safe(tmp_path):
    from scripts.ostar import hardware_monitor

    hw = hardware_monitor.HardwareMonitor(project_root=tmp_path)
    safe, violations = hw.check()
    assert isinstance(safe, bool)
    assert isinstance(violations, list)


# ─────────────────────────────────────────────────────────────────────────────
# Guard tests
# ─────────────────────────────────────────────────────────────────────────────


def test_guard_result_to_dict():
    from scripts.ostar import guard

    result = guard.GuardResult(
        passed=True,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        run_id="soak_test",
    )
    result.add_check("TEST", True, "ok")
    result.add_check("FAIL_CHECK", False, "oops")
    d = result.to_dict()
    assert d["passed"] is True
    assert len(d["checks"]) == 2
    assert d["checks"][0]["status"] == "PASS"
    assert d["checks"][1]["status"] == "FAIL"


def test_guard_run(tmp_path):
    from scripts.ostar import guard

    g = guard.Guard(tmp_path)
    # Initialize git in tmp_path so the git check passes
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    result = g.run(soak_root=tmp_path / "soak")
    # At minimum, Python/Torch checks should run
    assert "PYTHON_VERSION" in [c["name"] for c in result.checks]
    assert "GIT_REPO" in [c["name"] for c in result.checks]


# ─────────────────────────────────────────────────────────────────────────────
# Repair node tests
# ─────────────────────────────────────────────────────────────────────────────


def test_repair_node_fingerprint():
    from scripts.ostar import repair_node

    node = repair_node.RepairNode(
        project_root=Path("/tmp"),
        failure_log='File "test.py", line 10\nAttributeError: module has no attribute',
        error_output='AttributeError: module has no attribute "foo"',
    )
    fp = node._compute_fingerprint()
    assert len(fp) == 32
    assert fp.isalnum()


def test_repair_node_classify():
    from scripts.ostar import repair_node

    node = repair_node.RepairNode(
        project_root=Path("/tmp"),
        failure_log="",
        error_output="AttributeError: 'NoneType' object has no attribute 'foo'",
    )
    cls, msg = node._classify_error()
    assert cls in ("CODE", "UNKNOWN")


def test_repair_node_classify_oom():
    from scripts.ostar import repair_node

    node = repair_node.RepairNode(
        project_root=Path("/tmp"),
        failure_log="",
        error_output="RuntimeError: CUDA out of memory",
    )
    cls, msg = node._classify_error()
    assert cls == "RESOURCE"


def test_repair_node_classify_file_not_found():
    from scripts.ostar import repair_node

    node = repair_node.RepairNode(
        project_root=Path("/tmp"),
        failure_log="",
        error_output="FileNotFoundError: [Errno 2] No such file: 'config.yaml'",
    )
    cls, msg = node._classify_error()
    assert cls == "CONFIG"


def test_repair_node_classify_blocked():
    from scripts.ostar import repair_node

    node = repair_node.RepairNode(
        project_root=Path("/tmp"),
        failure_log="",
        error_output="mIoU_ch classes mismatch",
    )
    cls, msg = node._classify_error()
    assert cls in ("PROTOCOL", "UNKNOWN")


# ─────────────────────────────────────────────────────────────────────────────
# Test suites tests
# ─────────────────────────────────────────────────────────────────────────────


def test_run_subprocess_timeout():
    from scripts.ostar import test_suites

    rc, stdout, stderr = test_suites._run_subprocess(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        timeout_seconds=2,
    )
    assert rc == -1
    assert "Timeout" in stderr


def test_run_subprocess_success():
    from scripts.ostar import test_suites

    rc, stdout, stderr = test_suites._run_subprocess(
        [sys.executable, "-c", "print('hello')"],
        timeout_seconds=5,
    )
    assert rc == 0
    assert "hello" in stdout


def test_resource_sample():
    from scripts.ostar import test_suites

    sample = test_suites._sample_resources(Path("/tmp"))
    assert "timestamp" in sample
    assert "ram_used_mb" in sample
    assert "file_handles" in sample


# ─────────────────────────────────────────────────────────────────────────────
# Exit validator tests
# ─────────────────────────────────────────────────────────────────────────────


def test_exit_validator_no_run():
    from scripts.ostar import exit_validator, soak_state

    tmp = Path(tempfile.mkdtemp())
    store = soak_state.SoakStateStore(tmp)
    validator = exit_validator.ExitValidator(store)
    verdict = validator.evaluate("nonexistent_run")
    assert verdict.verdict == "FAILED_WITH_UNRESOLVED_BUGS"


def test_verdict_badges():
    from scripts.ostar import constants as C
    from scripts.ostar import reporter

    badges = reporter._VERDICT_BADGES
    assert C.VERDICT_SOAK_VERIFIED in badges
    assert C.VERDICT_FAILED_UNRESOLVED in badges
    assert "✅" in badges[C.VERDICT_SOAK_VERIFIED]


def test_verdict_colors():
    from scripts.ostar import constants as C
    from scripts.ostar import reporter

    colors = reporter._VERDICT_COLORS
    assert C.VERDICT_SOAK_VERIFIED in colors
    assert colors[C.VERDICT_SOAK_VERIFIED] == "#28a745"


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke tests
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_help():
    # Use reproctl.py dispatch so it tests the actual integration
    plugin_root = Path(__file__).resolve().parents[1]
    reproctl = plugin_root / "scripts" / "reproctl.py"
    result = subprocess.run(
        [sys.executable, str(reproctl), "soak", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OSTAR" in result.stdout


def test_cli_subcommands():
    from scripts.ostar import cli

    parser = cli.build_parser()
    for cmd in ["plan", "start", "status", "pause", "resume", "stop", "report"]:
        args = parser.parse_args([cmd, "--project", "/tmp"])
        assert args.soak_command == cmd
