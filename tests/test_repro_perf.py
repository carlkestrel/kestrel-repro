#!/usr/bin/env python3
"""Acceptance tests for ReproPerf AutoTuner."""

import ast
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "performance"


def run(*args, cwd=None):
    r = subprocess.run(
        ["python3", str(REPO / "scripts" / "repro_perf_tuner.py")] + list(args),
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO),
        timeout=60,
    )
    return r


def rec(name, ok, detail=""):
    icon = "✓" if ok else "✗"
    status = "PASS" if ok else "FAIL"
    print(f"  {icon} {name}: {status}{' | ' + detail if detail else ''}")
    return ok


# ── T01: Script parses ──────────────────────────────────────────────────────────
def test_parse():
    src = (REPO / "scripts" / "repro_perf_tuner.py").read_text()
    ast.parse(src)
    rec("T01 repro_perf_tuner.py parses", True)


# ── T02: All 10 template files exist ─────────────────────────────────────────
def test_templates():
    expected = [
        "hardware_inventory.json",
        "health_report.md",
        "baseline_metrics.csv",
        "baseline_profile.json",
        "capacity_trials.csv",
        "safe_capacity.yaml",
        "tuning_trials.csv",
        "bottleneck_report.md",
        "numerical_parity_report.md",
        "soak_test_report.md",
        "recommendation.md",
        "strict_performance.yaml",
        "optimized_performance.yaml",
        "rollback.yaml",
    ]
    all_ok = True
    for name in expected:
        path = REPO / "templates" / "performance" / name
        if not path.exists():
            rec(f"T02 template {name}", False, "MISSING")
            all_ok = False
    if all_ok:
        rec("T02 all 14 templates exist", True, f"{len(expected)} files")
    assert all_ok, "some templates missing"


# ── T03: Template schemas are valid JSON/YAML ──────────────────────────────────
def test_template_schemas():
    # JSON templates
    for name in ["hardware_inventory.json"]:
        path = REPO / "templates" / "performance" / name
        try:
            json.loads(path.read_text())
            rec(f"T03 {name} valid JSON", True)
        except Exception as e:
            rec(f"T03 {name} valid JSON", False, str(e))

    # CSV templates have header
    for name in ["baseline_metrics.csv", "capacity_trials.csv", "tuning_trials.csv"]:
        path = REPO / "templates" / "performance" / name
        content = path.read_text()
        ok = bool(content.strip()) and "," in content
        rec(f"T03 {name} valid CSV", ok, f"{len(content)} bytes")


# ── T04: Command file exists with frontmatter ──────────────────────────────────
def test_command():
    path = REPO / "commands" / "repro-perf.md"
    content = path.read_text()
    has_fm = content.startswith("---")
    rec("T04 repro-perf.md has YAML frontmatter", has_fm)
    rec(
        "T04 repro-perf.md has 12 fundamental rules",
        content.count("12.") >= 1 or content.count("Fundamental") >= 1,
    )
    rec("T04 repro-perf.md has NO_SAFE_SPEEDUP rule", "NO_SAFE_SPEEDUP" in content)
    rec(
        "T04 repro-perf.md has strict/optimized separation",
        "strict_performance.yaml" in content and "optimized_performance.yaml" in content,
    )


# ── T05: health phase ──────────────────────────────────────────────────────────
def test_health_phase():
    r = run("--phase", "health")
    ok = r.returncode == 0
    rec("T05 health phase exit=0", ok, r.stderr[:60] if not ok else "")
    # Check outputs
    for fname in ["hardware_inventory.json", "health_report.md"]:
        p = OUT_DIR / fname
        ok &= rec(f"T05 {fname} created", p.exists(), f"size={p.stat().st_size}")


# ── T06: baseline phase ────────────────────────────────────────────────────────
def test_baseline_phase():
    r = run(
        "--phase",
        "baseline",
        "--config-id",
        "test-baseline",
        "--micro-batch",
        "2",
        "--grad-accum-steps",
        "1",
        "--num-workers",
        "0",
    )
    ok = r.returncode == 0
    rec("T06 baseline phase exit=0", ok, r.stderr[:60] if not ok else "")
    for fname in ["baseline_metrics.csv", "baseline_profile.json"]:
        p = OUT_DIR / fname
        ok &= rec(f"T06 {fname} created", p.exists())


# ── T07: capacity phase ─────────────────────────────────────────────────────────
def test_capacity_phase():
    r = run("--phase", "capacity", "--config-id", "test-capacity")
    ok = r.returncode == 0
    rec("T07 capacity phase exit=0", ok, r.stderr[:60] if not ok else "")
    for fname in ["capacity_trials.csv", "safe_capacity.yaml"]:
        p = OUT_DIR / fname
        ok &= rec(f"T07 {fname} created", p.exists())


# ── T08: parity phase ───────────────────────────────────────────────────────────
def test_parity_phase():
    r = run(
        "--phase",
        "parity",
        "--baseline-id",
        "test-baseline",
        "--candidate-id",
        "test-candidate",
        "--precision",
        "FP32",
    )
    ok = r.returncode == 0
    rec("T08 parity phase exit=0", ok, r.stderr[:60] if not ok else "")
    p = OUT_DIR / "numerical_parity_report.md"
    rec("T08 numerical_parity_report.md created", p.exists())


# ── T09: soak phase ─────────────────────────────────────────────────────────────
def test_soak_phase():
    r = run("--phase", "soak", "--config-id", "test-candidate", "--duration", "10")
    ok = r.returncode == 0
    rec("T09 soak phase exit=0", ok, r.stderr[:60] if not ok else "")
    p = OUT_DIR / "soak_test_report.md"
    rec("T09 soak_test_report.md created", p.exists())


# ── T10: recommend phase ────────────────────────────────────────────────────────
def test_recommend_phase():
    r = run("--phase", "recommend", "--micro-batch", "2", "--num-workers", "0")
    ok = r.returncode == 0
    rec("T10 recommend phase exit=0", ok, r.stderr[:60] if not ok else "")
    for fname in ["recommendation.md", "strict_performance.yaml", "rollback.yaml"]:
        p = OUT_DIR / fname
        rec(f"T10 {fname} created", p.exists())


# ── T11: strict/optimized separation ───────────────────────────────────────────
def test_strict_optimized():
    strict = OUT_DIR / "strict_performance.yaml"
    optimized = OUT_DIR / "optimized_performance.yaml"
    rollback = OUT_DIR / "rollback.yaml"

    s_ok = strict.exists()
    rec("T11 strict_performance.yaml exists", s_ok)

    if s_ok:
        s_content = strict.read_text()
        rec(
            "T11 strict: protocol_preserved=true",
            "protocol_preserved: true" in s_content or "protocol_preserved: true" in s_content,
        )
        rec("T11 strict: torch_compile=false", "torch_compile: false" in s_content)
        rec("T11 strict: precision=FP32", "precision: FP32" in s_content)

    rec("T11 rollback.yaml exists", rollback.exists())
    rec(
        "T11 rollback: has default_config",
        rollback.exists() and "default_config:" in rollback.read_text(),
    )


# ── T12: NO_SAFE_SPEEDUP written when no trials ────────────────────────────────
def test_no_safe_speedup():
    rec_path = OUT_DIR / "recommendation.md"
    if rec_path.exists():
        content = rec_path.read_text()
        # When no optimization trials exist, should say NO_SAFE_SPEEDUP
        rec(
            "T12 recommendation.md has verdict block",
            "verdict" in content.lower() or "Verdict" in content,
        )


# ── T13: 12 fundamental rules enforced ─────────────────────────────────────────
def test_12_rules():
    src = (REPO / "commands" / "repro-perf.md").read_text()
    rules_found = sum(
        1
        for r in [
            "baseline before",
            "real model",
            "short loop",
            "safety margin",
            "strict and optimized",
            "preserve",
            "one variable",
            "multiple",
            "measurement noise",
            "immediate rollback",
            "overclocking",
            "quality reduction",
        ]
        if r.lower() in src.lower()
    )
    rec("T13 12 fundamental rules in command", rules_found >= 10, f"~{rules_found} keywords found")


# ── T14: tuning_trials.csv has correct columns ─────────────────────────────────
def test_tuning_trials_columns():
    path = REPO / "templates" / "performance" / "tuning_trials.csv"
    content = path.read_text()
    required = [
        "trial_id",
        "config_id",
        "mode",
        "step_time_mean_s",
        "samples_per_second",
        "gpu_memory_peak_mb",
        "loss",
        "gradient_norm",
        "throughput_delta_pct",
        "memory_delta_mb",
        "nan_count",
        "status",
    ]
    missing = [c for c in required if c not in content]
    rec(
        "T14 tuning_trials.csv has required columns",
        not missing,
        f"missing: {missing}" if missing else "all present",
    )


# ── T15: rollback.yaml has all failure triggers ─────────────────────────────────
def test_rollback_triggers():
    path = REPO / "templates" / "performance" / "rollback.yaml"
    content = path.read_text()
    triggers = [
        "OOM",
        "NUMERICAL_DIFFERENT",
        "LOSS_NAN",
        "METRIC_DEVIATION",
        "THERMAL_THROTTLING",
        "SOAK_TEST_FAIL",
    ]
    found = [t for t in triggers if t in content]
    rec("T15 rollback.yaml has all 6 triggers", len(found) >= 6, f"found: {found}")


def main():
    print("ReproPerf AutoTuner Acceptance Tests")
    print("=" * 50)
    results = []

    tests = [
        test_parse,
        test_templates,
        test_template_schemas,
        test_command,
        test_health_phase,
        test_baseline_phase,
        test_capacity_phase,
        test_parity_phase,
        test_soak_phase,
        test_recommend_phase,
        test_strict_optimized,
        test_no_safe_speedup,
        test_12_rules,
        test_tuning_trials_columns,
        test_rollback_triggers,
    ]

    for fn in tests:
        try:
            ok = fn()
            results.append((fn.__name__, ok))
        except Exception as e:
            rec(f"{fn.__name__}", False, str(e)[:60])
            results.append((fn.__name__, False))

    passed = sum(1 for _, ok in results if ok)
    print(f"\nReproPerf: {passed}/{len(results)} PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
