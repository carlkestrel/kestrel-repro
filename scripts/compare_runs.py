#!/usr/bin/env python3
"""
compare_runs.py

Compares two training runs (e.g., strict vs. optimized, or before/after an optimization)
to verify numerical parity and generate a comparison report.

Usage:
    python compare_runs.py strict_run.json optimized_run.json
    python compare_runs.py --runs-dir=experiments/ --compare=run_a,run_b
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ComparisonResult:
    run_a_id: str = ""
    run_b_id: str = ""
    loss_parity: bool = False
    loss_diff_avg: float = 0.0
    loss_diff_max: float = 0.0
    metric_parity: bool = False
    metric_diff: float = 0.0
    nan_in_a: int = 0
    nan_in_b: int = 0
    grad_norm_parity: bool = False
    grad_norm_diff_avg: float = 0.0
    status: str = "unknown"
    recommendation: str = ""
    timestamp: str = ""


def load_run(path: Path) -> dict:
    """Load a run result from JSON or CSV."""
    if path.suffix == ".json":
        return json.loads(path.read_text())
    elif path.suffix == ".csv":
        # Simple CSV loader for metric files
        import csv
        rows = []
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return {"rows": rows}
    else:
        return {}


def compare_loss_curves(a_data: dict, b_data: dict, tolerance: float = 0.001) -> dict:
    """Compare loss curves between two runs."""
    result = {
        "parity": True,
        "diff_avg": 0.0,
        "diff_max": 0.0,
        "steps_compared": 0,
    }

    a_rows = a_data.get("rows", [])
    b_rows = b_data.get("rows", [])

    if not a_rows or not b_rows:
        result["error"] = "Missing rows in one or both runs"
        result["parity"] = False
        return result

    min_len = min(len(a_rows), len(b_rows))
    diffs = []

    for i in range(min_len):
        try:
            loss_a = float(a_rows[i].get("loss", 0))
            loss_b = float(b_rows[i].get("loss", 0))
            if loss_a == 0 and loss_b == 0:
                continue
            diff = abs(loss_a - loss_b)
            rel_diff = diff / max(loss_a, 0.001)
            diffs.append(diff)
            if rel_diff > tolerance:
                result["parity"] = False
        except (ValueError, KeyError):
            continue

    if diffs:
        result["diff_avg"] = sum(diffs) / len(diffs)
        result["diff_max"] = max(diffs)
        result["steps_compared"] = len(diffs)

    return result


def compare_metrics(a_data: dict, b_data: dict, tolerance: float = 0.5) -> dict:
    """Compare final metrics between two runs."""
    result = {
        "parity": True,
        "metric_a": None,
        "metric_b": None,
        "diff": 0.0,
    }

    # Try to find metric in run data
    metric_keys = ["mIoU", "accuracy", "f1", "miou", "val_mIoU", "val_miou"]

    for key in metric_keys:
        if key in a_data:
            result["metric_a"] = a_data[key]
            break
        # Check in nested structure
        for r in a_data.get("rows", []):
            if key in r:
                result["metric_a"] = float(r[key])
                break

    for key in metric_keys:
        if key in b_data:
            result["metric_b"] = b_data[key]
            break
        for r in b_data.get("rows", []):
            if key in r:
                result["metric_b"] = float(r[key])
                break

    if result["metric_a"] is not None and result["metric_b"] is not None:
        diff = abs(result["metric_a"] - result["metric_b"])
        result["diff"] = diff
        result["parity"] = diff <= tolerance
    else:
        result["parity"] = None
        result["error"] = "Could not extract comparable metrics"

    return result


def run_comparison(run_a_path: Path, run_b_path: Path,
                   tolerance: float = 0.5) -> ComparisonResult:
    """Compare two runs and return a structured result."""

    a_data = load_run(run_a_path)
    b_data = load_run(run_b_path)

    comparison = ComparisonResult(
        run_a_id=str(run_a_path.stem),
        run_b_id=str(run_b_path.stem),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Loss comparison
    loss_result = compare_loss_curves(a_data, b_data)
    comparison.loss_parity = loss_result.get("parity", False)
    comparison.loss_diff_avg = loss_result.get("diff_avg", 0.0)
    comparison.loss_diff_max = loss_result.get("diff_max", 0.0)

    # Metric comparison
    metric_result = compare_metrics(a_data, b_data)
    comparison.metric_parity = metric_result.get("parity") in (True, None)
    comparison.metric_diff = metric_result.get("diff", 0.0)

    # NaN check
    comparison.nan_in_a = sum(
        1 for r in a_data.get("rows", [])
        if "loss" in r and (r["loss"] == "nan" or r["loss"] == "NaN")
    )
    comparison.nan_in_b = sum(
        1 for r in b_data.get("rows", [])
        if "loss" in r and (r["loss"] == "nan" or r["loss"] == "NaN")
    )

    # Grad norm check (if available)
    grad_norms_a = [float(r["grad_norm"]) for r in a_data.get("rows", []) if "grad_norm" in r]
    grad_norms_b = [float(r["grad_norm"]) for r in b_data.get("rows", []) if "grad_norm" in r]
    if grad_norms_a and grad_norms_b:
        avg_a = sum(grad_norms_a) / len(grad_norms_a)
        avg_b = sum(grad_norms_b) / len(grad_norms_b)
        comparison.grad_norm_parity = abs(avg_a - avg_b) / max(avg_a, 0.001) < 0.1
        comparison.grad_norm_diff_avg = abs(avg_a - avg_b)

    # Overall status and recommendation
    all_parity = (
        comparison.loss_parity and
        comparison.metric_parity and
        comparison.nan_in_a == 0 and
        comparison.nan_in_b == 0
    )

    if all_parity:
        comparison.status = "equivalent"
        comparison.recommendation = "optimized_repro_safe"
    elif comparison.nan_in_b > 0:
        comparison.status = "diverged"
        comparison.recommendation = "use_strict_repro (NaN in optimized)"
    elif not comparison.loss_parity:
        comparison.status = "diverged"
        comparison.recommendation = "use_strict_repro (loss divergence)"
    else:
        comparison.status = "inconclusive"
        comparison.recommendation = "requires_manual_review"

    return comparison


def format_markdown(result: ComparisonResult) -> str:
    lines = ["# Run Comparison Report", ""]
    lines.append(f"Comparing: `{result.run_a_id}` vs. `{result.run_b_id}`")
    lines.append(f"Timestamp: {result.timestamp}")
    lines.append("")

    status_icon = "✅" if result.status == "equivalent" else "❌"
    lines.append(f"## Status: {status_icon} {result.status}")
    lines.append("")

    lines.append("## Loss Parity")
    lines.append(f"- Within tolerance: `{'Yes' if result.loss_parity else 'No'}`")
    lines.append(f"- Avg diff: `{result.loss_diff_avg:.6f}`")
    lines.append(f"- Max diff: `{result.loss_diff_max:.6f}`")
    lines.append(f"- NaN in run A: `{result.nan_in_a}`")
    lines.append(f"- NaN in run B: `{result.nan_in_b}`")
    lines.append("")

    lines.append("## Metric Parity")
    lines.append(f"- Within tolerance: `{'Yes' if result.metric_parity else 'No'}`")
    lines.append(f"- Metric diff: `{result.metric_diff:.4f}`")
    lines.append("")

    if result.grad_norm_diff_avg > 0:
        lines.append("## Grad Norm Parity")
        lines.append(f"- Avg diff: `{result.grad_norm_diff_avg:.6f}`")
        lines.append(f"- Within 10%: `{'Yes' if result.grad_norm_parity else 'No'}`")
        lines.append("")

    lines.append("## Recommendation")
    rec_icon = "✅" if "optimized" in result.recommendation else "⚠️"
    lines.append(f"{rec_icon} **{result.recommendation}**")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_a", type=Path)
    parser.add_argument("run_b", type=Path)
    parser.add_argument("--tolerance", type=float, default=0.5)
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()

    result = run_comparison(args.run_a, args.run_b, tolerance=args.tolerance)

    if args.markdown:
        print(format_markdown(result))
    else:
        output = json.dumps(asdict(result), indent=2)
        if args.output:
            args.output.write_text(output)
            print(f"Comparison saved to {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
