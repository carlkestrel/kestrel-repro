#!/usr/bin/env python3
"""
benchmark_runtime.py

Benchmarks training runtime performance:
- Throughput (samples/sec, steps/sec)
- GPU utilization and memory usage
- CPU utilization
- DataLoader throughput
- Comparison between strict (FP32) and optimized (AMP) modes

Usage:
    python benchmark_runtime.py --mode=strict --duration=120 --batch-size=4
    python benchmark_runtime.py --mode=optimized --duration=120 --amp
    python benchmark_runtime.py --mode=compare
"""

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkResult:
    mode: str
    start_time: str = ""
    end_time: str = ""
    duration_sec: float = 0.0
    batch_size: int = 0
    throughput_samples_per_sec: float = 0.0
    throughput_steps_per_sec: float = 0.0
    gpu_utilization_avg: float = 0.0
    gpu_utilization_peak: float = 0.0
    gpu_memory_allocated_gb: float = 0.0
    gpu_memory_reserved_gb: float = 0.0
    gpu_memory_peak_gb: float = 0.0
    cpu_utilization_avg: float = 0.0
    dataloader_throughput_samples_per_sec: float = 0.0
    grad_norm_avg: float = 0.0
    grad_norm_std: float = 0.0
    loss_avg: float = 0.0
    loss_std: float = 0.0
    steps_completed: int = 0
    steps_with_nan: int = 0
    warmup_steps: int = 10
    error: str = ""
    status: str = "unknown"


def run_training_benchmark(mode: str, duration: int, batch_size: int,
                          amp: bool = False, primary_path: Path | None = None,
                          warmup: int = 10) -> BenchmarkResult:
    """Run a benchmark by executing the training script for a fixed duration."""

    result = BenchmarkResult(
        mode=mode,
        batch_size=batch_size,
        warmup_steps=warmup,
        start_time=datetime.now(timezone.utc).isoformat(),
    )

    benchmark_script = Path(__file__).parent / "benchmark_train.py"

    cmd = [
        sys.executable, str(benchmark_script),
        "--duration", str(duration),
        "--batch-size", str(batch_size),
        "--warmup", str(warmup),
    ]
    if amp:
        cmd.append("--amp")
    if primary_path:
        cmd += ["--primary", str(primary_path)]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(primary_path) if primary_path else ".",
        )

        stdout, stderr = proc.communicate(timeout=duration + 120)
        returncode = proc.returncode

        result.end_time = datetime.now(timezone.utc).isoformat()

        if returncode != 0:
            result.status = "failed"
            result.error = stderr[-500:]  # Last 500 chars of error
            return result

        # Parse benchmark output
        for line in stdout.split("\n"):
            if line.startswith("BENCHMARK_RESULT:"):
                try:
                    data = json.loads(line.split("BENCHMARK_RESULT:", 1)[1])
                    for k, v in data.items():
                        if hasattr(result, k):
                            setattr(result, k, v)
                except json.JSONDecodeError:
                    pass

        result.status = "completed"

    except subprocess.TimeoutExpired:
        result.status = "timeout"
        result.error = f"Benchmark timed out after {duration + 120}s"
        proc.kill()
    except FileNotFoundError:
        result.status = "skipped"
        result.error = "benchmark_train.py not found — benchmarking requires a benchmark script"

    return result


def compare_modes(strict_result: BenchmarkResult,
                 optimized_result: BenchmarkResult,
                 tolerance: float = 0.5) -> dict[str, Any]:
    """Compare strict vs optimized mode results."""
    comparison = {
        "strict": asdict(strict_result),
        "optimized": asdict(optimized_result),
        "throughput_speedup": 0.0,
        "memory_reduction_ratio": 0.0,
        "metric_parity": {
            "loss_within_tolerance": True,
            "grad_norm_within_tolerance": True,
            "nan_count_strict": strict_result.steps_with_nan,
            "nan_count_optimized": optimized_result.steps_with_nan,
        },
        "recommendation": "unknown",
    }

    if strict_result.throughput_samples_per_sec > 0:
        comparison["throughput_speedup"] = (
            optimized_result.throughput_samples_per_sec /
            strict_result.throughput_samples_per_sec
        )

    if strict_result.gpu_memory_peak_gb > 0:
        comparison["memory_reduction_ratio"] = (
            strict_result.gpu_memory_peak_gb /
            optimized_result.gpu_memory_peak_gb
            if optimized_result.gpu_memory_peak_gb > 0 else 0
        )

    # Loss parity check
    if strict_result.loss_avg > 0:
        loss_diff_pct = abs(strict_result.loss_avg - optimized_result.loss_avg) / strict_result.loss_avg * 100
        comparison["metric_parity"]["loss_within_tolerance"] = loss_diff_pct < tolerance * 10
        comparison["metric_parity"]["loss_diff_percent"] = round(loss_diff_pct, 3)

    # Recommend
    if comparison["metric_parity"]["loss_within_tolerance"] and \
       optimized_result.steps_with_nan == 0 and \
       comparison["throughput_speedup"] > 1.0:
        comparison["recommendation"] = "optimized_repro_safe"
    elif comparison["throughput_speedup"] > 1.0 and optimized_result.steps_with_nan == 0:
        comparison["recommendation"] = "requires_manual_parity_check"
    else:
        comparison["recommendation"] = "use_strict_repro"

    return comparison


def format_report(results: dict[str, Any]) -> str:
    """Format benchmark results as Markdown."""
    strict = results.get("strict", {})
    optimized = results.get("optimized", {})
    comparison = results.get("comparison", {})

    lines = ["# Runtime Benchmark Report", ""]

    # Strict
    lines.append("## Strict Mode (FP32, Single GPU)")
    lines.append(f"- Throughput: `{strict.get('throughput_samples_per_sec', 0):.1f}` samples/sec")
    lines.append(f"- Steps/sec: `{strict.get('throughput_steps_per_sec', 0):.2f}`")
    lines.append(f"- GPU memory peak: `{strict.get('gpu_memory_peak_gb', 0):.2f}` GB")
    lines.append(f"- GPU utilization avg: `{strict.get('gpu_utilization_avg', 0):.1f}%`")
    lines.append(f"- Loss avg: `{strict.get('loss_avg', 0):.4f}`")
    lines.append(f"- Status: `{strict.get('status', 'unknown')}`")
    lines.append("")

    # Optimized
    if optimized.get("mode"):
        lines.append("## Optimized Mode (AMP)")
        lines.append(f"- Throughput: `{optimized.get('throughput_samples_per_sec', 0):.1f}` samples/sec")
        lines.append(f"- Steps/sec: `{optimized.get('throughput_steps_per_sec', 0):.2f}`")
        lines.append(f"- GPU memory peak: `{optimized.get('gpu_memory_peak_gb', 0):.2f}` GB")
        lines.append(f"- GPU utilization avg: `{optimized.get('gpu_utilization_avg', 0):.1f}%`")
        lines.append(f"- Loss avg: `{optimized.get('loss_avg', 0):.4f}`")
        lines.append(f"- Status: `{optimized.get('status', 'unknown')}`")
        lines.append("")

    # Comparison
    if comparison:
        lines.append("## Comparison")
        lines.append(f"- Throughput speedup: `{comparison.get('throughput_speedup', 0):.2f}x`")
        lines.append(f"- Memory reduction: `{comparison.get('memory_reduction_ratio', 0):.2f}x`")
        rec = comparison.get("recommendation", "unknown")
        if rec == "optimized_repro_safe":
            lines.append(f"- **Recommendation: `{rec}`** ✅")
        elif rec == "use_strict_repro":
            lines.append(f"- **Recommendation: `{rec}`** ⚠️")
        else:
            lines.append(f"- Recommendation: `{rec}`")

        parity = comparison.get("metric_parity", {})
        lines.append(f"- Loss within tolerance: `{parity.get('loss_within_tolerance', False)}`")
        lines.append(f"- NaN in strict: `{parity.get('nan_count_strict', 0)}`")
        lines.append(f"- NaN in optimized: `{parity.get('nan_count_optimized', 0)}`")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["strict", "optimized", "compare"],
                       default="strict", help="Benchmark mode")
    parser.add_argument("--duration", type=int, default=120,
                       help="Benchmark duration in seconds")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--amp", action="store_true", help="Use AMP")
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--primary", type=Path, help="Path to primary repository")
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument("--markdown", action="store_true", help="Output as Markdown")
    args = parser.parse_args()

    results = {}

    if args.mode == "compare":
        print("Running strict mode benchmark...")
        strict = run_training_benchmark("strict", args.duration, args.batch_size,
                                        amp=False, primary_path=args.primary,
                                        warmup=args.warmup)
        print("Running optimized mode benchmark...")
        optimized = run_training_benchmark("optimized", args.duration, args.batch_size,
                                           amp=True, primary_path=args.primary,
                                           warmup=args.warmup)
        comparison = compare_modes(strict, optimized)
        results = {
            "strict": asdict(strict),
            "optimized": asdict(optimized),
            "comparison": comparison,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        is_amp = args.mode == "optimized"
        result = run_training_benchmark(args.mode, args.duration, args.batch_size,
                                        amp=is_amp, primary_path=args.primary,
                                        warmup=args.warmup)
        results = {
            args.mode: asdict(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    if args.markdown:
        print(format_report(results))
    else:
        output = json.dumps(results, indent=2, default=str)
        if args.output:
            args.output.write_text(output)
            print(f"Benchmark results saved to {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
