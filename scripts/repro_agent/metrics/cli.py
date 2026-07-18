"""
Metric Protocol Auditor - CLI

Command-line interface for metric auditing operations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add parent to path
THIS = Path(__file__).resolve()
PACKAGE_ROOT = THIS.parent.parent.parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from repro_agent.metrics import (
    WRONG_DOIS,
    ConflictDetector,
    HardcodeDetector,
    MetricRecomputer,
    MetricRegistry,
    SiamKPConv_CLASS_NAMES,
    SiamKPConv_PAPER_METADATA,
    SiamKPConv_PAPER_TARGETS,
    SiamKPConvGoldenTest,
    get_standard_metrics,
    run_golden_test,
)
from repro_agent.metrics.takeover import TakeoverScanner


def cmd_discover(args) -> int:
    """Discover metrics in a project."""
    project = Path(args.project).resolve()

    print(f"Discovering metrics in: {project}")

    registry = MetricRegistry()

    # Register standard metrics
    for metric_id, metric in get_standard_metrics().items():
        registry.register_metric(metric)

    # Scan for metrics
    scanner = TakeoverScanner(project)
    results = scanner.scan_all()

    # Save results
    output_dir = project / ".repro" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "takeover_inventory.json").write_text(json.dumps(results, indent=2, default=str))

    print("\nDiscovered:")
    print(f"  Files scanned: {results['num_files_scanned']}")
    print(f"  Findings: {results['num_findings']}")

    for ftype, items in results.get("findings_by_type", {}).items():
        print(f"    {ftype}: {len(items)}")

    return 0


def cmd_takeover(args) -> int:
    """Perform full takeover of existing project."""
    project = Path(args.project).resolve()

    print(f"Taking over project: {project}")

    # Perform takeover scan
    scanner = TakeoverScanner(project)
    results = scanner.scan_all()

    # Output directory
    output_dir = project / ".repro" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save inventory
    inventory_path = output_dir / "takeover_inventory.json"
    inventory_path.write_text(json.dumps(results, indent=2, default=str))

    # Check for DOI conflicts
    dois = [f["value"] for f in results["findings"] if f["type"] == "DOI"]
    wrong_doi_found = any(doi in WRONG_DOIS for doi in dois)

    print(f"\n{'=' * 60}")
    print("TAKEOVER REPORT")
    print(f"{'=' * 60}")
    print(f"Project: {project}")
    print(f"Files scanned: {results['num_files_scanned']}")
    print(f"Findings: {results['num_findings']}")

    if wrong_doi_found:
        print("\n⚠️  DOI CONFLICT DETECTED")
        for doi in dois:
            if doi in WRONG_DOIS:
                print(f"  ❌ Wrong DOI: {doi}")

    print("\nFindings by type:")
    for ftype, items in results.get("findings_by_type", {}).items():
        print(f"  {ftype}: {len(items)}")

    print(f"\nInventory saved to: {inventory_path}")

    return 0 if not wrong_doi_found else 1


def cmd_audit(args) -> int:
    """Run metric protocol audit."""
    project = Path(args.project).resolve()

    print(f"Auditing metrics in: {project}")

    # Run golden test first
    print("\nRunning SiamKPConv Golden Test...")
    golden_results = run_golden_test()

    if golden_results["all_passed"]:
        print("✅ Golden test PASSED")
    else:
        print(f"❌ Golden test FAILED: {len(golden_results['failed'])} tests failed")
        for f in golden_results["failed"]:
            print(f"  - {f}")

    # Check for hardcoded metrics
    print("\nScanning for hardcoded metrics...")
    detector = HardcodeDetector()
    detector.scan_directory(project)
    hardcode_report = detector.generate_report()

    print(f"  Findings: {hardcode_report['total_findings']}")
    if hardcode_report["errors"]:
        print("  Errors:")
        for err in hardcode_report["errors"]:
            print(f"    - {err}")

    # Save report
    output_dir = project / ".repro" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    audit_report = {
        "golden_test": golden_results,
        "hardcode_detection": hardcode_report,
        "timestamp": __import__("datetime").datetime.now().__str__(),
    }

    (output_dir / "metric_protocol_audit.md").write_text(generate_audit_markdown(audit_report))

    return 0


def cmd_recompute(args) -> int:
    """Recompute metrics from confusion matrix."""
    cm_path = Path(args.confusion_matrix)

    if not cm_path.exists():
        print(f"Error: Confusion matrix not found: {cm_path}")
        return 1

    print(f"Loading confusion matrix: {cm_path}")

    try:
        cm = MetricRecomputer.load_confusion_matrix(cm_path)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    print(f"Shape: {cm.shape}")
    print(f"Sum: {cm.sum()}")

    # Recompute metrics
    results = MetricRecomputer.recompute_from_confusion_matrix(
        cm, class_names=SiamKPConv_CLASS_NAMES
    )

    print(f"\n{'=' * 60}")
    print("METRIC RECOMPUTATION RESULTS")
    print(f"{'=' * 60}")

    print(f"\nmIoU_ch (classes 1-6): {results['miou_ch']:.4f} ({results['miou_ch'] * 100:.2f}%)")
    print(
        f"All-class mIoU (0-6):   {results['all_class_miou']:.4f} ({results['all_class_miou'] * 100:.2f}%)"
    )
    print(
        f"Overall Accuracy:        {results['overall_accuracy']:.4f} ({results['overall_accuracy'] * 100:.2f}%)"
    )
    print(
        f"Mean Accuracy:           {results['mean_accuracy']:.4f} ({results['mean_accuracy'] * 100:.2f}%)"
    )

    print("\nPer-class IoU:")
    for cls_name, iou in results["per_class_iou"].items():
        marker = " ← mIoU_ch" if cls_name != "Unchanged" else " (excluded)"
        print(f"  {cls_name}: {iou:.4f} ({iou * 100:.2f}%){marker}")

    # Compare with paper targets
    print("\nComparison with paper targets:")
    for cls_name, target in SiamKPConv_PAPER_TARGETS.items():
        computed = results["per_class_iou"].get(cls_name, 0) * 100
        diff = computed - target
        print(f"  {cls_name}: computed={computed:.2f}, target={target:.2f}, diff={diff:+.2f}")

    # Save results
    output_path = Path(args.output) if args.output else cm_path.with_suffix(".metrics.json")
    MetricRecomputer.save_metrics(results, output_path)
    print(f"\nResults saved to: {output_path}")

    return 0


def cmd_conflicts(args) -> int:
    """Detect metric conflicts."""
    project = Path(args.project).resolve()

    print(f"Detecting conflicts in: {project}")

    # Run takeover scan
    scanner = TakeoverScanner(project)
    results = scanner.scan_all()

    # Check for conflicts
    detector = ConflictDetector()

    # Check DOI conflicts
    dois = [f["value"] for f in results["findings"] if f["type"] == "DOI"]
    for doi in dois:
        if doi in WRONG_DOIS:
            detector.add_conflict(
                "DOI_CONFLICT",
                f"Wrong DOI found: {doi}",
                severity="ERROR",
            )

    # Save conflicts
    output_dir = project / ".repro" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    conflicts_file = output_dir / "conflicts.json"
    detector.save_conflicts(conflicts_file)

    print(f"\nConflicts detected: {len(detector.conflicts)}")
    if detector.has_errors():
        print("❌ Errors found")
        for c in detector.conflicts:
            if c.severity == "ERROR":
                print(f"  [{c.severity}] {c.description}")
    else:
        print("✅ No errors")

    print(f"Conflicts saved to: {conflicts_file}")

    return 0 if not detector.has_errors() else 1


def cmd_verify(args) -> int:
    """Verify metric protocol."""
    project = Path(args.project).resolve()

    print(f"Verifying metric protocol in: {project}")

    # Run golden test
    golden = SiamKPConvGoldenTest()
    results = golden.run_all_tests()

    print(f"\n{'=' * 60}")
    print("PROTOCOL VERIFICATION")
    print(f"{'=' * 60}")
    print(f"Passed: {results['total_passed']}/{results['total_passed'] + results['total_failed']}")

    if results["all_passed"]:
        print("\n✅ Protocol verification PASSED")
        return 0
    else:
        print("\n❌ Protocol verification FAILED:")
        for f in results["failed"]:
            print(f"  - {f}")
        return 1


def cmd_report(args) -> int:
    """Generate metric report."""
    project = Path(args.project).resolve()

    print(f"Generating metric report for: {project}")

    # Run golden test
    golden = SiamKPConvGoldenTest()
    golden_results = golden.run_all_tests()

    # Get paper targets table
    targets_table = SiamKPConvGoldenTest.get_paper_targets_table()

    # Generate markdown report
    report = f"""# Metric Protocol Audit Report

**Project**: {project}
**Generated**: {__import__("datetime").datetime.now()}

## Paper Identity

- **Title**: {SiamKPConv_PAPER_METADATA["title"]}
- **Authors**: {", ".join(SiamKPConv_PAPER_METADATA["authors"])}
- **Journal**: {SiamKPConv_PAPER_METADATA["journal"]}
- **Volume**: {SiamKPConv_PAPER_METADATA["volume"]}
- **Year**: {SiamKPConv_PAPER_METADATA["year"]}
- **DOI**: {SiamKPConv_PAPER_METADATA["doi"]}

## Paper Target Values

{targets_table}

## Golden Test Results

- **Passed**: {golden_results["total_passed"]}/{golden_results["total_passed"] + golden_results["total_failed"]}
- **Status**: {"✅ PASS" if golden_results["all_passed"] else "❌ FAIL"}

### Test Details

"""

    for test_name, result in golden_results.get("results", {}).items():
        report += f"#### {test_name}\n\n"
        report += f"```json\n{json.dumps(result, indent=2)}\n```\n\n"

    # Save report
    output_dir = project / ".repro" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "metric_protocol_audit.md"
    report_path.write_text(report)

    print(f"Report saved to: {report_path}")

    return 0


def cmd_doctor(args) -> int:
    """Run metric doctor checks."""
    project = Path(args.project).resolve()

    print(f"Running metric doctor checks for: {project}")

    issues = []

    # Check for .repro/metrics directory
    metrics_dir = project / ".repro" / "metrics"
    if not metrics_dir.exists():
        issues.append("Missing .repro/metrics directory")

    # Check for paper targets
    if not (metrics_dir / "paper_targets.yaml").exists():
        issues.append("Missing paper_targets.yaml")

    # Run golden test
    golden = SiamKPConvGoldenTest()
    results = golden.run_all_tests()
    if not results["all_passed"]:
        issues.append(f"Golden test failed: {results['failed']}")

    # Check for hardcoded metrics
    detector = HardcodeDetector()
    detector.scan_directory(project, exclude_dirs=[".git", "venv", "node_modules"])
    hardcode_report = detector.generate_report()
    if hardcode_report["errors"]:
        issues.append(f"Hardcoded metrics found: {len(hardcode_report['errors'])}")

    print(f"\n{'=' * 60}")
    print("METRIC DOCTOR RESULTS")
    print(f"{'=' * 60}")

    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("✅ All checks passed")
        return 0


def cmd_golden(args) -> int:
    """Run SiamKPConv golden test."""
    print("Running SiamKPConv Golden Test...")

    results = run_golden_test()

    print(f"\n{'=' * 60}")
    print("SIAMESE KPCONV GOLDEN TEST")
    print(f"{'=' * 60}")
    print(f"Passed: {results['total_passed']}/{results['total_passed'] + results['total_failed']}")

    if results["all_passed"]:
        print("\n✅ All golden tests PASSED")
    else:
        print(f"\n❌ {len(results['failed'])} tests FAILED:")
        for f in results["failed"]:
            print(f"  - {f}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2))
        print(f"Results saved to: {output_path}")

    return 0 if results["all_passed"] else 1


def generate_audit_markdown(audit_report: dict) -> str:
    """Generate markdown audit report."""
    golden = audit_report.get("golden_test", {})
    hardcode = audit_report.get("hardcode_detection", {})

    report = f"""# Metric Protocol Audit Report

**Generated**: {audit_report.get("timestamp", "N/A")}

## Golden Test Results

- **Passed**: {golden.get("total_passed", 0)}/{golden.get("total_passed", 0) + golden.get("total_failed", 0)}
- **Status**: {"✅ PASS" if golden.get("all_passed") else "❌ FAIL"}

## Hardcode Detection

- **Total findings**: {hardcode.get("total_findings", 0)}
- **Errors**: {len(hardcode.get("errors", []))}
- **Warnings**: {len(hardcode.get("warnings", []))}

"""

    if hardcode.get("errors"):
        report += "### Errors\n\n"
        for err in hardcode["errors"]:
            report += f"- ❌ {err}\n"
        report += "\n"

    if hardcode.get("warnings"):
        report += "### Warnings\n\n"
        for warn in hardcode["warnings"]:
            report += f"- ⚠️ {warn}\n"
        report += "\n"

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Metric Protocol Auditor (MPA)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # discover
    p_discover = sub.add_parser("discover", help="Discover metrics in project")
    p_discover.add_argument("--project", default=".", help="Project root")

    # takeover
    p_takeover = sub.add_parser("takeover", help="Full project takeover")
    p_takeover.add_argument("--project", default=".", help="Project root")

    # audit
    p_audit = sub.add_parser("audit", help="Run metric protocol audit")
    p_audit.add_argument("--project", default=".", help="Project root")

    # recompute
    p_recompute = sub.add_parser("recompute", help="Recompute metrics from confusion matrix")
    p_recompute.add_argument("confusion_matrix", help="Path to confusion matrix file")
    p_recompute.add_argument("--output", help="Output path for results")

    # compare
    p_compare = sub.add_parser("compare", help="Compare metrics")
    p_compare.add_argument("--project", default=".", help="Project root")
    p_compare.add_argument("--run-id", help="Run ID to compare")

    # conflicts
    p_conflicts = sub.add_parser("conflicts", help="Detect metric conflicts")
    p_conflicts.add_argument("--project", default=".", help="Project root")

    # verify
    p_verify = sub.add_parser("verify", help="Verify metric protocol")
    p_verify.add_argument("--project", default=".", help="Project root")

    # report
    p_report = sub.add_parser("report", help="Generate metric report")
    p_report.add_argument("--project", default=".", help="Project root")

    # doctor
    p_doctor = sub.add_parser("doctor", help="Run metric doctor checks")
    p_doctor.add_argument("--project", default=".", help="Project root")

    # golden
    p_golden = sub.add_parser("golden", help="Run SiamKPConv golden test")
    p_golden.add_argument("--output", help="Output path for results")

    args = parser.parse_args()

    commands = {
        "discover": cmd_discover,
        "takeover": cmd_takeover,
        "audit": cmd_audit,
        "recompute": cmd_recompute,
        "conflicts": cmd_conflicts,
        "verify": cmd_verify,
        "report": cmd_report,
        "doctor": cmd_doctor,
        "golden": cmd_golden,
    }

    handler = commands.get(args.command)
    if handler:
        try:
            return handler(args)
        except Exception as e:
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
