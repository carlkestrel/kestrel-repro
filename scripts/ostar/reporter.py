"""OSTAR morning report generator (Section X).

Produces:
  - soak/reports/overnight_summary.md
  - soak/reports/overnight_summary.html
  - soak/reports/failure_timeline.csv
  - soak/reports/repair_history.csv
  - soak/reports/ci_reliability.csv
  - soak/reports/resource_trends.csv
  - soak/reports/unresolved_issues.md
  - soak/reports/final_gate.json
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import constants as _C
from . import exit_validator
from . import soak_state as _state

# ─────────────────────────────────────────────────────────────────────────────
# Data containers
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class OvernightSummary:
    run_id: str
    started_at: str
    ended_at: str
    duration_seconds: float
    cycles_completed: int
    ci_runs: int
    ci_success_rate: float
    bugs_found: int
    auto_repairs: int
    verified_repairs: int
    rollback_count: int
    unresolved_issues: list[dict]
    flaky_tests: list[dict]
    gpu_memory_leak: bool
    cpu_memory_leak: bool
    max_gpu_temp_c: int
    min_disk_free_gb: float
    last_stable_seconds: float
    verdict: str
    fast_can_start: bool
    strict_can_start: bool


# ─────────────────────────────────────────────────────────────────────────────
# Module-level constants (must be after _C import)
# ─────────────────────────────────────────────────────────────────────────────

_VERDICT_BADGES = {
    _C.VERDICT_SOAK_VERIFIED: "✅ SOAK_VERIFIED",
    _C.VERDICT_REPAIRED_NOT_SOAK_VERIFIED: "⚠️ REPAIRED_BUT_NOT_SOAK_VERIFIED",
    _C.VERDICT_FAILED_UNRESOLVED: "❌ FAILED_WITH_UNRESOLVED_BUGS",
    _C.VERDICT_BLOCKED_REQUIRES_REVIEW: "🔒 BLOCKED_REQUIRES_REVIEW",
    _C.VERDICT_ABORTED_HARDWARE: "🚨 ABORTED_FOR_HARDWARE_SAFETY",
}

_VERDICT_COLORS = {
    _C.VERDICT_SOAK_VERIFIED: "#28a745",
    _C.VERDICT_REPAIRED_NOT_SOAK_VERIFIED: "#ffc107",
    _C.VERDICT_FAILED_UNRESOLVED: "#dc3545",
    _C.VERDICT_BLOCKED_REQUIRES_REVIEW: "#6c757d",
    _C.VERDICT_ABORTED_HARDWARE: "#fd7e14",
}

_VERDICT_EXPLANATIONS = {
    _C.VERDICT_SOAK_VERIFIED: (
        "All required acceptance criteria passed. The system is stable and ready.\n"
        "Both FAST and STRICT startup modes can proceed."
    ),
    _C.VERDICT_REPAIRED_NOT_SOAK_VERIFIED: (
        "Repairs were made but the last 2-hour stability window did not complete.\n"
        "FAST mode may proceed with caution. STRICT mode requires SOAK_VERIFIED."
    ),
    _C.VERDICT_FAILED_UNRESOLVED: (
        "Required acceptance criteria failed. Manual review is required.\n"
        "Do NOT start FAST or STRICT until all P0/P1 issues are resolved."
    ),
    _C.VERDICT_BLOCKED_REQUIRES_REVIEW: (
        "A BLOCKED_REQUIRES_REVIEW error class was encountered.\n"
        "These errors (PROTOCOL, DATA) cannot be auto-repaired without human review."
    ),
    _C.VERDICT_ABORTED_HARDWARE: (
        "Hardware safety limit was exceeded (GPU temperature, disk space).\n"
        "OSTAR does not attempt to fix hardware issues by changing training parameters."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Markdown report
# ─────────────────────────────────────────────────────────────────────────────


def generate_markdown_report(summary: OvernightSummary) -> str:
    """Generate the overnight_summary.md report."""
    hours = summary.duration_seconds / 3600
    minutes = (summary.duration_seconds % 3600) / 60
    stable_hours = summary.last_stable_seconds / 3600

    verdict_badge = _VERDICT_BADGES.get(summary.verdict, summary.verdict)
    ci_pct = summary.ci_success_rate
    ci_bar = "█" * int(ci_pct / 5) + "░" * (20 - int(ci_pct / 5))

    lines = [
        "# Overnight Soak Test Report",
        "",
        f"**Run ID**: `{summary.run_id}`",
        f"**Verdict**: {verdict_badge}",
        f"**Started**: {summary.started_at}",
        f"**Ended**: {summary.ended_at}",
        f"**Duration**: {hours:.1f}h {minutes:.0f}m ({summary.duration_seconds:.0f}s)",
        "",
        "## Executive Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Cycles Completed | {summary.cycles_completed} |",
        f"| CI Success Rate | {ci_pct:.1f}% `{ci_bar}` |",
        f"| Bugs Found | {summary.bugs_found} |",
        f"| Auto-Repairs Attempted | {summary.auto_repairs} |",
        f"| Verified Repairs | {summary.verified_repairs} |",
        f"| Rollbacks | {summary.rollback_count} |",
        f"| Unresolved Issues | {len(summary.unresolved_issues)} |",
        f"| Flaky Tests | {len(summary.flaky_tests)} |",
        f"| Last Stable Window | {stable_hours:.1f}h |",
        f"| Max GPU Temp | {summary.max_gpu_temp_c}°C |",
        f"| Min Disk Free | {summary.min_disk_free_gb:.1f} GB |",
        f"| GPU Memory Leak | {'YES' if summary.gpu_memory_leak else 'NO'} |",
        f"| CPU Memory Leak | {'YES' if summary.cpu_memory_leak else 'NO'} |",
        "",
        "## Startup Readiness",
        "",
        f"**FAST mode**: {'✅ CAN START' if summary.fast_can_start else '❌ BLOCKED'}",
        f"**STRICT mode**: {'✅ CAN START' if summary.strict_can_start else '❌ BLOCKED'}",
        "",
    ]

    if summary.unresolved_issues:
        lines.extend(
            [
                f"## Unresolved Issues ({len(summary.unresolved_issues)})",
                "",
            ]
        )
        for issue in summary.unresolved_issues:
            severity = issue.get("severity", "?").upper()
            lines.append(
                f"- **[{severity}]** `{issue.get('bug_id', '?')}` — {issue.get('description', '?')}"
            )

    if summary.flaky_tests:
        lines.extend(
            [
                f"## Flaky Tests ({len(summary.flaky_tests)})",
                "",
            ]
        )
        for fl in summary.flaky_tests:
            lines.append(
                f"- `{fl.get('suite', '?')}` — {fl.get('description', '?')} "
                f"(flaky rate: {fl.get('rate', '?')}%)"
            )

    lines.extend(
        [
            "",
            "## Verdict Explanation",
            "",
            "```",
            _VERDICT_EXPLANATIONS.get(summary.verdict, f"Unknown: {summary.verdict}"),
            "```",
            "",
            f"---\n*Generated: {datetime.now(timezone.utc).isoformat()} UTC*",
        ]
    )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# HTML report
# ─────────────────────────────────────────────────────────────────────────────


def _badge_html(kind: str, text: str) -> str:
    return f'<span class="badge-{kind}">{text}</span>'


def generate_html_report(summary: OvernightSummary) -> str:
    """Generate the overnight_summary.html report."""
    verdict_color = _VERDICT_COLORS.get(summary.verdict, "#888888")
    hours = summary.duration_seconds / 3600
    ci_pct = summary.ci_success_rate
    fast_badge = _badge_html(
        "ok" if summary.fast_can_start else "fail",
        "CAN START" if summary.fast_can_start else "BLOCKED",
    )
    strict_badge = _badge_html(
        "ok" if summary.strict_can_start else "fail",
        "CAN START" if summary.strict_can_start else "BLOCKED",
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OSTAR Report: {summary.run_id}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ color: #1a1a2e; border-bottom: 2px solid #e94560; padding-bottom: 0.5rem; }}
  h2 {{ color: #16213e; margin-top: 2rem; }}
  .verdict {{ display: inline-block; padding: 0.5rem 1rem; border-radius: 4px;
              font-weight: bold; color: white; background: {verdict_color}; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #ddd; }}
  th {{ background: #f5f5f5; }}
  .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }}
  .metric-card {{ background: #f9f9f9; border-radius: 8px; padding: 1rem; border-left: 4px solid #0f3460; }}
  .metric-value {{ font-size: 2rem; font-weight: bold; color: #0f3460; }}
  .metric-label {{ color: #666; font-size: 0.875rem; }}
  .badge-ok {{ background: #28a745; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; }}
  .badge-fail {{ background: #dc3545; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; }}
  .badge-warn {{ background: #ffc107; color: black; padding: 0.2rem 0.5rem; border-radius: 4px; }}
  footer {{ margin-top: 3rem; color: #888; font-size: 0.875rem; }}
</style>
</head>
<body>
<h1>Overnight Soak Test Report</h1>
<div class="verdict">{summary.verdict}</div>

<p><strong>Run ID:</strong> <code>{summary.run_id}</code></p>
<p><strong>Duration:</strong> {hours:.1f} hours</p>
<p><strong>Started:</strong> {summary.started_at}</p>
<p><strong>Ended:</strong> {summary.ended_at}</p>

<h2>Key Metrics</h2>
<div class="metric-grid">
  <div class="metric-card">
    <div class="metric-value">{summary.cycles_completed}</div>
    <div class="metric-label">Cycles Completed</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{summary.ci_success_rate:.1f}%</div>
    <div class="metric-label">CI Success Rate</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{summary.bugs_found}</div>
    <div class="metric-label">Bugs Found</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{summary.verified_repairs}/{summary.auto_repairs}</div>
    <div class="metric-label">Repairs (Verified/Total)</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{summary.max_gpu_temp_c}°C</div>
    <div class="metric-label">Max GPU Temp</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">{summary.min_disk_free_gb:.1f} GB</div>
    <div class="metric-label">Min Disk Free</div>
  </div>
</div>

<h2>Startup Readiness</h2>
<table>
  <tr><th>Mode</th><th>Status</th></tr>
  <tr><td>FAST</td><td>{fast_badge}</td></tr>
  <tr><td>STRICT</td><td>{strict_badge}</td></tr>
</table>
"""
    if summary.unresolved_issues:
        html += f"<h2>Unresolved Issues ({len(summary.unresolved_issues)})</h2>\n<ul>\n"
        for issue in summary.unresolved_issues:
            html += (
                f"<li><strong>[{issue.get('severity', '?').upper()}]</strong> "
                f"{issue.get('description', '?')}</li>\n"
            )
        html += "</ul>\n"

    html += f"""
<footer>
  Generated: {datetime.now(timezone.utc).isoformat()} UTC — OSTAR v0.1.0
</footer>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────────────────────
# CSV reports
# ─────────────────────────────────────────────────────────────────────────────


def generate_failure_timeline_csv(cycles: list[dict], bugs: list[dict], output_path: Path) -> None:
    """Write failure_timeline.csv."""
    fieldnames = [
        "timestamp",
        "cycle_seq",
        "event",
        "bug_id",
        "error_class",
        "consecutive_failures",
        "description",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cyc in cycles:
            writer.writerow(
                {
                    "timestamp": cyc.get("ended_at", ""),
                    "cycle_seq": cyc.get("sequence", ""),
                    "event": f"cycle_{cyc.get('status', '').lower()}",
                    "bug_id": "",
                    "error_class": "",
                    "consecutive_failures": "",
                    "description": cyc.get("exit_reason", ""),
                }
            )
        for bug in bugs:
            writer.writerow(
                {
                    "timestamp": bug.get("last_seen_at", ""),
                    "cycle_seq": "",
                    "event": "bug_detected",
                    "bug_id": bug.get("bug_id", ""),
                    "error_class": bug.get("error_class", ""),
                    "consecutive_failures": bug.get("consecutive_failures", ""),
                    "description": (
                        f"{bug.get('error_class', '')} fingerprint={bug.get('fingerprint', '')[:8]}"
                    ),
                }
            )


def generate_repair_history_csv(repairs: list[dict], output_path: Path) -> None:
    """Write repair_history.csv."""
    fieldnames = [
        "repair_id",
        "bug_id",
        "attempt",
        "started_at",
        "ended_at",
        "status",
        "target_test_passed",
        "regression_test_passed",
        "notes",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in repairs:
            writer.writerow(
                {
                    "repair_id": r.get("repair_id", ""),
                    "bug_id": r.get("bug_id", ""),
                    "attempt": r.get("attempt", ""),
                    "started_at": r.get("started_at", ""),
                    "ended_at": r.get("ended_at", ""),
                    "status": r.get("status", ""),
                    "target_test_passed": r.get("target_test_passed", ""),
                    "regression_test_passed": r.get("regression_test_passed", ""),
                    "notes": r.get("notes", ""),
                }
            )


def generate_ci_reliability_csv(ci_summary: dict, output_path: Path) -> None:
    """Write ci_reliability.csv."""
    fieldnames = [
        "suite",
        "total_pass",
        "total_fail",
        "total_skip",
        "flaky_count",
        "runs",
        "success_rate",
        "flaky_rate",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for suite, data in sorted(ci_summary.items()):
            total_pass = data.get("total_pass", 0)
            total_fail = data.get("total_fail", 0)
            total_skip = data.get("total_skip", 0)
            flaky = data.get("flaky_count", 0)
            runs = data.get("runs", 0)
            denom = total_pass + total_fail
            success_rate = (total_pass / denom * 100) if denom > 0 else 0.0
            flaky_rate = (flaky / runs * 100) if runs > 0 else 0.0
            writer.writerow(
                {
                    "suite": suite,
                    "total_pass": total_pass,
                    "total_fail": total_fail,
                    "total_skip": total_skip,
                    "flaky_count": flaky,
                    "runs": runs,
                    "success_rate": round(success_rate, 2),
                    "flaky_rate": round(flaky_rate, 2),
                }
            )


def generate_resource_trends_csv(metrics_dir: Path, output_path: Path) -> None:
    """Write resource_trends.csv from metrics JSON files."""
    fieldnames = [
        "timestamp",
        "gpu_allocated_gb",
        "gpu_memory_used_pct",
        "gpu_temp_c",
        "cpu_ram_used_pct",
        "disk_free_gb",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for mf in sorted(metrics_dir.glob("*.json")):
            try:
                data = json.loads(mf.read_text())
                row = {
                    "timestamp": data.get("timestamp_utc", ""),
                    "gpu_allocated_gb": (
                        data.get("gpu_memory_allocated_gb", [0])[0]
                        if data.get("gpu_memory_allocated_gb")
                        else 0
                    ),
                    "gpu_memory_used_pct": (
                        data.get("gpu_memory_used_pct", [0])[0]
                        if data.get("gpu_memory_used_pct")
                        else 0
                    ),
                    "gpu_temp_c": (
                        data.get("gpu_temps_c", [0])[0] if data.get("gpu_temps_c") else 0
                    ),
                    "cpu_ram_used_pct": data.get("cpu_memory_used_pct", 0),
                    "disk_free_gb": data.get("disk_free_gb", 0),
                }
                writer.writerow(row)
            except Exception:
                pass


def generate_unresolved_issues_md(bugs: list[dict], output_path: Path) -> None:
    """Write unresolved_issues.md."""
    unresolved = [
        b for b in bugs if b.get("consecutive_failures", 0) > 0 and not b.get("is_blocked")
    ]
    lines = [
        "# Unresolved Issues",
        "",
        f"Total: {len(unresolved)}",
        "",
        "| Bug ID | Error Class | Occurrences | Severity |",
        "|---|---|---|---|",
    ]
    for b in unresolved:
        severity = "P0" if b.get("is_blocked") else "P1"
        lines.append(
            f"| `{b.get('bug_id', '')}` | {b.get('error_class', '')} "
            f"| {b.get('occurrences', 0)} | {severity} |"
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def generate_final_gate_json(summary: OvernightSummary, verdict: dict, output_path: Path) -> None:
    """Write final_gate.json."""
    gate = {
        "verdict": summary.verdict,
        "run_id": summary.run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "duration_seconds": summary.duration_seconds,
            "cycles_completed": summary.cycles_completed,
            "ci_success_rate": summary.ci_success_rate,
            "bugs_found": summary.bugs_found,
            "auto_repairs": summary.auto_repairs,
            "verified_repairs": summary.verified_repairs,
            "rollback_count": summary.rollback_count,
        },
        "hardware": {
            "max_gpu_temp_c": summary.max_gpu_temp_c,
            "min_disk_free_gb": summary.min_disk_free_gb,
            "gpu_memory_leak": summary.gpu_memory_leak,
            "cpu_memory_leak": summary.cpu_memory_leak,
        },
        "readiness": {
            "fast_can_start": summary.fast_can_start,
            "strict_can_start": summary.strict_can_start,
        },
        "criteria": verdict.get("criteria", []),
        "final_status": verdict.get("verdict", summary.verdict),
    }
    output_path.write_text(
        json.dumps(gate, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# All-reports dispatcher
# ─────────────────────────────────────────────────────────────────────────────


def generate_all_reports(
    state_store: _state.SoakStateStore, run_id: str, output_dir: Path | None = None
) -> dict:
    """Generate all morning reports and return a summary dict."""
    if output_dir is None:
        output_dir = state_store.reports_dir

    run = state_store.get_run(run_id)
    cycles = state_store.get_cycles(run_id)
    bugs = state_store.get_bugs(run_id)
    repairs = state_store.get_repairs(run_id)
    ci_summary = state_store.get_ci_summary(run_id)

    started = run.get("started_at", "") if run else ""
    ended = run.get("ended_at", "") if run else ""
    duration = run.get("duration_seconds", 0.0) if run else 0.0

    # CI reliability
    total_pass = sum(v.get("total_pass", 0) for v in ci_summary.values())
    total_fail = sum(v.get("total_fail", 0) for v in ci_summary.values())
    ci_rate = total_pass / (total_pass + total_fail) * 100 if (total_pass + total_fail) > 0 else 0.0

    # Hardware (best-effort from last metric file)
    max_temp = 0
    min_disk = float("inf")
    gpu_leak = False
    cpu_leak = False
    metrics_files = sorted(state_store.metrics_dir.glob("*.json"))
    if metrics_files:
        try:
            last_metric = json.loads(metrics_files[-1].read_text())
        except Exception:
            last_metric = {}
    else:
        last_metric = {}

    temps = last_metric.get("gpu_temps_c", [])
    max_temp = max(temps) if temps else 0
    min_disk = last_metric.get("disk_free_gb", float("inf"))
    gpu_alloc = last_metric.get("gpu_memory_allocated_gb", [])
    if len(gpu_alloc) >= 2 and gpu_alloc[-1] > gpu_alloc[0] * 1.5:
        gpu_leak = True
    if last_metric.get("cpu_memory_used_pct", 0) > 85:
        cpu_leak = True

    # Exit verdict
    validator = exit_validator.ExitValidator(state_store)
    verdict = validator.evaluate(run_id)

    # Compute stable window
    stable_secs = 0.0
    if cycles:
        last_ended = cycles[-1].get("ended_at", "")
        if last_ended:
            try:
                last_dt = datetime.fromisoformat(last_ended.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                stable_secs = max(0, (now - last_dt).total_seconds())
            except Exception:
                pass

    unresolved_issues = [
        {
            "bug_id": b.get("bug_id"),
            "severity": "P0" if b.get("is_blocked") else "P1",
            "description": f"{b.get('error_class', '')} — {b.get('occurrences', 0)} occurrences",
        }
        for b in bugs
        if b.get("consecutive_failures", 0) > 0
    ]
    flaky_tests = [
        {
            "suite": s,
            "description": "flaky",
            "rate": v.get("flaky_count", 0) / max(v.get("runs", 1), 1) * 100,
        }
        for s, v in ci_summary.items()
        if v.get("flaky_count", 0) > 0
    ]

    summary = OvernightSummary(
        run_id=run_id,
        started_at=started,
        ended_at=ended,
        duration_seconds=duration,
        cycles_completed=len(cycles),
        ci_runs=sum(v.get("runs", 0) for v in ci_summary.values()),
        ci_success_rate=ci_rate,
        bugs_found=len(bugs),
        auto_repairs=len(repairs),
        verified_repairs=sum(1 for r in repairs if r.get("status") == "PASS"),
        rollback_count=sum(1 for r in repairs if r.get("status") == "ROLLBACK"),
        unresolved_issues=unresolved_issues,
        flaky_tests=flaky_tests,
        gpu_memory_leak=gpu_leak,
        cpu_memory_leak=cpu_leak,
        max_gpu_temp_c=max_temp,
        min_disk_free_gb=min_disk if min_disk != float("inf") else 0.0,
        last_stable_seconds=stable_secs,
        verdict=verdict.verdict,
        fast_can_start=verdict.verdict in (_C.VERDICT_SOAK_VERIFIED,),
        strict_can_start=verdict.verdict == _C.VERDICT_SOAK_VERIFIED,
    )

    # Generate all report files
    md_text = generate_markdown_report(summary)
    (output_dir / "overnight_summary.md").write_text(md_text, encoding="utf-8")

    html_text = generate_html_report(summary)
    (output_dir / "overnight_summary.html").write_text(html_text, encoding="utf-8")

    generate_failure_timeline_csv(cycles, bugs, output_dir / "failure_timeline.csv")
    generate_repair_history_csv(repairs, output_dir / "repair_history.csv")
    generate_ci_reliability_csv(ci_summary, output_dir / "ci_reliability.csv")
    generate_resource_trends_csv(state_store.metrics_dir, output_dir / "resource_trends.csv")
    generate_unresolved_issues_md(bugs, output_dir / "unresolved_issues.md")
    generate_final_gate_json(summary, verdict.to_dict(), output_dir / "final_gate.json")

    return {
        "verdict": summary.verdict,
        "run_id": summary.run_id,
        "cycles_completed": summary.cycles_completed,
        "ci_success_rate": summary.ci_success_rate,
        "bugs_found": summary.bugs_found,
        "auto_repairs": summary.auto_repairs,
        "verified_repairs": summary.verified_repairs,
        "duration_seconds": summary.duration_seconds,
        "unresolved_issues": len(summary.unresolved_issues),
        "flaky_tests": len(summary.flaky_tests),
    }
