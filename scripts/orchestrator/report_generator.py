"""
Report Generator - Generate reproduction reports from verified evidence.

This module generates:
- Machine-readable JSON/CSV reports
- Human-readable Markdown reports
- Go/Pivot/No-Go verdicts
- Claim-to-evidence mapping
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReportGenerator:
    """Generate reproduction reports from evidence."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.reports_dir = self.project_root / ".repro" / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_summary_report(self, task_results: list[dict]) -> dict:
        """Generate a summary report from task results."""
        report = {
            "generated_at": utc_now(),
            "project_root": str(self.project_root),
            "total_tasks": len(task_results),
            "passed": sum(1 for t in task_results if t.get("status") == "PASS"),
            "failed": sum(1 for t in task_results if t.get("status") == "FAIL"),
            "blocked": sum(1 for t in task_results if t.get("status") == "BLOCKED"),
            "tasks": [],
        }

        for task in task_results:
            task_summary = {
                "id": task.get("id"),
                "name": task.get("name"),
                "status": task.get("status"),
                "attempts": task.get("attempts", 0),
                "failure_reason": task.get("failure_reason"),
            }
            report["tasks"].append(task_summary)

        # Save JSON report
        json_path = self.reports_dir / "summary_report.json"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        # Save CSV report
        csv_path = self.reports_dir / "summary_report.csv"
        if task_results:
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "id", "name", "status", "attempts", "failure_reason"
                ])
                writer.writeheader()
                for task in task_results:
                    writer.writerow({
                        "id": task.get("id", ""),
                        "name": task.get("name", ""),
                        "status": task.get("status", ""),
                        "attempts": task.get("attempts", 0),
                        "failure_reason": task.get("failure_reason", ""),
                    })

        return report

    def generate_markdown_report(
        self,
        task_results: list[dict],
        title: str = "Paper Reproduction Report",
        paper_info: dict | None = None,
    ) -> str:
        """Generate a human-readable Markdown report."""
        
        md = f"""# {title}

**Generated**: {utc_now()}  
**Project**: {self.project_root.name}

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | {len(task_results)} |
| Passed | {sum(1 for t in task_results if t.get('status') == 'PASS')} |
| Failed | {sum(1 for t in task_results if t.get('status') == 'FAIL')} |
| Blocked | {sum(1 for t in task_results if t.get('status') == 'BLOCKED')} |

"""

        if paper_info:
            md += """## Paper Information

"""
            for key, value in paper_info.items():
                md += f"- **{key}**: {value}\n"
            md += "\n"

        md += """## Task Results

"""
        
        # Group tasks by status
        passed = [t for t in task_results if t.get("status") == "PASS"]
        failed = [t for t in task_results if t.get("status") == "FAIL"]
        blocked = [t for t in task_results if t.get("status") == "BLOCKED"]
        
        if passed:
            md += "### Passed Tasks\n\n"
            for task in passed:
                md += f"- [x] **{task.get('name', task.get('id'))}**\n"
            md += "\n"
        
        if failed:
            md += "### Failed Tasks\n\n"
            for task in failed:
                reason = task.get("failure_reason", "Unknown")
                md += f"- [ ] **{task.get('name', task.get('id'))}**\n"
                md += f"  - Reason: {reason}\n"
            md += "\n"
        
        if blocked:
            md += "### Blocked Tasks\n\n"
            for task in blocked:
                md += f"- [ ] **{task.get('name', task.get('id'))}**\n"
            md += "\n"

        # Add evidence section
        md += """## Evidence Chain

All reproduction evidence is stored in `artifacts/runs/` with the following structure:

```
artifacts/runs/<run_id>/
├── run_manifest.json    # Run metadata
├── command.txt          # Exact command executed
├── config_resolved.yaml # Resolved configuration
├── environment.json     # Python environment
├── hardware.json        # Hardware info
├── stdout.log          # Standard output
├── stderr.log          # Standard error
├── metrics.csv         # Training metrics
├── checkpoints/        # Model checkpoints
├── predictions/         # Model predictions
├── confmat/            # Confusion matrices
├── figures/            # Generated figures
└── verification.json   # Verification results
```

"""

        # Add claim-to-evidence mapping
        md += self._generate_claim_table()
        
        # Add verdict
        verdict = self._determine_verdict(task_results)
        md += f"""---

## Verdict

{verdict}

---

*Report generated by dl-paper-repro autopilot*
"""

        # Save Markdown report
        md_path = self.reports_dir / "reproduction_report.md"
        md_path.write_text(md, encoding="utf-8")

        return md

    def _generate_claim_table(self) -> str:
        """Generate claim-to-evidence table."""
        table = """## Claim-to-Evidence Mapping

| Claim | Evidence | Source |
|-------|----------|--------|
"""
        # Try to read metrics from artifacts
        from .evidence_manager import EvidenceManager
        em = EvidenceManager(self.project_root)
        runs = em.list_runs()
        
        if runs:
            for run in runs[:10]:  # Limit to 10 most recent
                run_id = run.get("run_id", "unknown")
                task_id = run.get("task_id", "unknown")
                status = run.get("status", "unknown")
                table += f"| {task_id} | {status} | `artifacts/runs/{run_id}/` |\n"
        else:
            table += "| No evidence yet | - | - |\n"
        
        return table + "\n"

    def _determine_verdict(self, task_results: list[dict]) -> str:
        """Determine Go/Pivot/No-Go verdict."""
        passed = sum(1 for t in task_results if t.get("status") == "PASS")
        failed = sum(1 for t in task_results if t.get("status") == "FAIL")
        total = len(task_results)
        
        if total == 0:
            return "⚪ **INCONCLUSIVE**: No tasks executed"
        
        pass_rate = passed / total if total > 0 else 0
        
        if pass_rate >= 0.9:
            return "🟢 **GO**: High reproduction success rate"
        elif pass_rate >= 0.7:
            return "🟡 **GO with CAVEATS**: Partial reproduction achieved"
        elif pass_rate >= 0.5:
            return "🟠 **PIVOT**: Significant deviations detected"
        else:
            return "🔴 **NO-GO**: Reproduction failed"

    def generate_go_pivot_nogo(self, task_results: list[dict]) -> dict:
        """Generate Go/Pivot/No-Go report."""
        
        passed = sum(1 for t in task_results if t.get("status") == "PASS")
        failed = sum(1 for t in task_results if t.get("status") == "FAIL")
        total = len(task_results)
        pass_rate = passed / total if total > 0 else 0
        
        # Determine verdict
        if pass_rate >= 0.9:
            verdict = "GO"
            summary = "High reproduction success rate achieved"
        elif pass_rate >= 0.7:
            verdict = "GO"
            summary = "Partial reproduction with minor deviations"
        elif pass_rate >= 0.5:
            verdict = "PIVOT"
            summary = "Significant deviations require investigation"
        else:
            verdict = "NO-GO"
            summary = "Insufficient reproduction success"
        
        report = {
            "verdict": verdict,
            "summary": summary,
            "pass_rate": round(pass_rate * 100, 1),
            "passed_tasks": passed,
            "failed_tasks": failed,
            "total_tasks": total,
            "failed_task_details": [
                {"id": t.get("id"), "reason": t.get("failure_reason")}
                for t in task_results if t.get("status") == "FAIL"
            ],
            "recommendations": self._get_recommendations(verdict, task_results),
            "generated_at": utc_now(),
        }
        
        # Save report
        report_path = self.reports_dir / "go_pivot_nogo.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        
        return report

    def _get_recommendations(self, verdict: str, task_results: list[dict]) -> list[str]:
        """Get recommendations based on verdict."""
        recommendations = []
        
        if verdict == "GO":
            recommendations.append("Proceed with full paper writeup")
            recommendations.append("Document any minor deviations in the report")
        elif verdict == "PIVOT":
            recommendations.append("Investigate failed tasks in detail")
            recommendations.append("Consider requesting more compute resources")
            recommendations.append("Review data preprocessing pipeline")
        else:  # NO-GO
            recommendations.append("Review original paper claims")
            recommendations.append("Check for missing dependencies")
            recommendations.append("Verify dataset integrity")
            recommendations.append("Consider alternative implementations")
        
        # Add task-specific recommendations
        for task in task_results:
            if task.get("status") == "FAIL":
                task_id = task.get("id", "unknown")
                reason = task.get("failure_reason", "Unknown error")
                
                if "OOM" in str(reason):
                    recommendations.append(f"{task_id}: Consider reducing batch size or using gradient accumulation")
                elif "timeout" in str(reason).lower():
                    recommendations.append(f"{task_id}: Increase timeout or optimize training loop")
                elif "verification" in str(reason).lower():
                    recommendations.append(f"{task_id}: Review verification criteria and metrics")
        
        return recommendations

    def generate_metric_report(self, metrics_data: list[dict]) -> dict:
        """Generate detailed metric report."""
        
        report = {
            "generated_at": utc_now(),
            "total_runs": len(metrics_data),
            "metrics": {},
        }
        
        if not metrics_data:
            return report
        
        # Aggregate metrics
        all_keys = set()
        for run in metrics_data:
            all_keys.update(run.keys())
        
        for key in all_keys:
            values = [r.get(key) for r in metrics_data if r.get(key) is not None]
            if values and all(isinstance(v, (int, float)) for v in values):
                report["metrics"][key] = {
                    "mean": round(sum(values) / len(values), 4),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }
        
        # Save report
        report_path = self.reports_dir / "metric_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        
        return report

    def generate_paper_comparison(self, paper_metrics: dict, reproduction_metrics: dict) -> dict:
        """Generate comparison between paper claims and reproduction results."""
        
        comparison = {
            "generated_at": utc_now(),
            "paper_metrics": paper_metrics,
            "reproduction_metrics": reproduction_metrics,
            "differences": {},
            "verdict": "INCONCLUSIVE",
        }
        
        # Calculate differences
        for key in paper_metrics:
            if key in reproduction_metrics:
                paper_val = paper_metrics[key]
                repro_val = reproduction_metrics[key]
                
                if isinstance(paper_val, (int, float)) and isinstance(repro_val, (int, float)):
                    diff = abs(paper_val - repro_val)
                    pct_diff = (diff / paper_val * 100) if paper_val != 0 else 0
                    
                    comparison["differences"][key] = {
                        "paper": paper_val,
                        "reproduction": repro_val,
                        "absolute_difference": round(diff, 4),
                        "percentage_difference": round(pct_diff, 2),
                        "within_tolerance": pct_diff < 5,  # 5% tolerance
                    }
        
        # Determine overall verdict
        if comparison["differences"]:
            within_tolerance = sum(
                1 for d in comparison["differences"].values() 
                if d.get("within_tolerance", False)
            )
            total = len(comparison["differences"])
            
            if within_tolerance == total:
                comparison["verdict"] = "SUCCESS"
            elif within_tolerance >= total * 0.5:
                comparison["verdict"] = "PARTIAL"
            else:
                comparison["verdict"] = "FAILURE"
        
        # Save report
        report_path = self.reports_dir / "paper_comparison.json"
        report_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        
        return comparison
