"""Regression tests for the dl-paper-repro plugin evolution.

These 9 tests run after any `/repro-evolution` round. They guard the
plugin from accidental breakage when new lessons are absorbed.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _read(p):
    return open(REPO / p).read() if (REPO / p).exists() else ""


# ── 9 regression items ─────────────────────────────────────────────────────────

def test_01_manifest_valid():
    """plugin.json parses as JSON and has the canonical name."""
    data = json.loads((REPO / ".cursor-plugin" / "plugin.json").read_text())
    assert data.get("name") == "dl-paper-repro"


def test_02_commands_listed():
    """The plugin's commands directory contains ≥6 known commands."""
    cmds_dir = REPO / "commands"
    md_files = sorted(p.name for p in cmds_dir.glob("*.md"))
    required = {"repro-contract.md","repro-plan.md","repro-review.md",
                "repro-monitor.md","repro-report.md","research-extend.md"}
    assert required.issubset(set(md_files)), f"missing: {required - set(md_files)}"


def test_03_agents_listed():
    """The plugin's agents directory contains the canonical agents."""
    agents_dir = REPO / "agents"
    md_files = sorted(p.name for p in agents_dir.glob("*.md"))
    required = {"repro-lead.md","review-auditor.md","evidence-verifier.md","repo-scout.md"}
    assert required.issubset(set(md_files)), f"missing: {required - set(md_files)}"


def test_04_templates_listed():
    """All canonical templates exist."""
    tpl_dir = REPO / "templates"
    required = {"research_contract.md","human_checkpoints.md","handoff.json",
                "project_memory.md","topic_graph.json","search_plan.json",
                "claim_evidence_matrix.md","experiment_plan.md","experiment_tracker.csv",
                "control_flags.md","dataset_registry.md","narrative_report.md"}
    found = {p.name for p in tpl_dir.iterdir()}
    missing = required - found
    assert not missing, f"missing: {missing}"


def test_05_strict_mode_default():
    """reproctl.py defaults to mode=strict_repro (NOT optimized or experimental)."""
    src = _read("scripts/reproctl.py")
    assert 'default="strict_repro"' in src, "default mode is not strict_repro"


def test_06_short_loop_block():
    """reproctl.py exposes the run-short-loop subcommand."""
    r = subprocess.run([sys.executable, str(REPO/"scripts"/"reproctl.py"), "help"],
                       capture_output=True, text=True)
    assert "run-short-loop" in r.stdout, "run-short-loop missing from help"


def test_07_metrics_file_exists():
    """experiments/experiment_tracker.csv template exists with header only."""
    csv = (REPO / "templates" / "experiment_tracker.csv").read_text().strip()
    assert csv.startswith("experiment_id,module,status,run_id,support_claim")


def test_08_traceability_rule():
    """narrative_report.md includes the hard traceability rule (every number has source:)."""
    t = _read("templates/narrative_report.md")
    assert "source:" in t and "traceability" in t.lower()


def test_09_rollback_capable():
    """task_graph.yaml contains rollback_strategy for at least one task."""
    text = _read(".execution/task_graph.yaml")
    assert "rollback_strategy:" in text, "no rollback_strategy in task graph"


# ── runner ─────────────────────────────────────────────────────────────────────

TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


def main():
    passed = 0
    for fn in TESTS:
        try:
            fn(); passed += 1
        except AssertionError as e:
            print(f"[FAIL] {fn.__name__}: {e}")
        except Exception as e:
            print(f"[ERR]  {fn.__name__}: {e}")
    print(f"\ntest_regression: {passed}/{len(TESTS)} PASS")
    return 0 if passed == len(TESTS) else 2


if __name__ == "__main__":
    sys.exit(main())
