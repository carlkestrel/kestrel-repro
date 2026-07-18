#!/usr/bin/env python3
"""
artifact_verify.py

Verifies the completeness and integrity of the evidence chain for a paper reproduction:
- Commit traceability
- Config traceability
- Data manifest
- Seed recording
- Command recording
- Checkpoint availability and integrity
- Raw metrics preservation

Usage:
    python artifact_verify.py verify-chain --run_id=<uuid>
    python artifact_verify.py verify-checkpoints --run_dir=<path>
    python artifact_verify.py verify-metrics --run_id=<uuid>
"""

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class VerificationResult:
    check: str
    status: str  # "passed", "failed", "skipped"
    message: str = ""
    details: dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


def verify_commit(repo_path: Path) -> VerificationResult:
    """Verify commit traceability."""
    result = VerificationResult(check="commit_traceability", status="unknown")

    if not repo_path.exists():
        result.status = "failed"
        result.message = f"Repository path not found: {repo_path}"
        return result

    # Get current commit
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        is_dirty = bool(subprocess.call(["git", "diff", "--quiet"], stderr=subprocess.DEVNULL))

        result.status = "passed"
        result.details = {
            "commit": commit,
            "branch": branch,
            "is_dirty": is_dirty,
        }
        result.message = f"Commit {commit[:8]} on {branch}" + (" (dirty)" if is_dirty else "")

        if is_dirty:
            result.status = "failed"
            result.message += " — uncommitted changes may affect reproducibility"
    except subprocess.CalledProcessError:
        result.status = "failed"
        result.message = "Could not determine git commit"

    return result


def verify_config(config_path: Path) -> VerificationResult:
    """Verify config file exists and is recorded."""
    result = VerificationResult(check="config_traceability", status="unknown")

    if not config_path:
        result.status = "skipped"
        result.message = "No config path provided"
        return result

    if not config_path.exists():
        result.status = "failed"
        result.message = f"Config file not found: {config_path}"
    else:
        result.status = "passed"
        result.message = f"Config found: {config_path}"
        result.details = {
            "size_bytes": config_path.stat().st_size,
            "exists": True,
        }

    return result


def verify_checkpoint_dir(run_dir: Path) -> VerificationResult:
    """Verify checkpoint directory and integrity."""
    result = VerificationResult(check="checkpoint_availability", status="unknown")

    checkpoint_dir = run_dir / "checkpoints"
    if not checkpoint_dir.exists():
        result.status = "failed"
        result.message = f"Checkpoint directory not found: {checkpoint_dir}"
        return result

    checkpoints = sorted(checkpoint_dir.glob("*.pth")) + sorted(checkpoint_dir.glob("*.pt"))
    if not checkpoints:
        result.status = "failed"
        result.message = f"No checkpoints found in {checkpoint_dir}"
        return result

    # Check if checkpoints can be loaded
    loadable = 0
    corrupt = 0
    for ckpt in checkpoints:
        try:
            import torch

            state = torch.load(ckpt, map_location="cpu", weights_only=False)
            loadable += 1
            # Verify checkpoint has expected keys
            expected_keys = ["epoch", "model_state_dict", "optimizer_state_dict"]
            has_keys = any(k in state for k in expected_keys)
            if not has_keys:
                result.details.setdefault("incomplete", []).append(str(ckpt.name))
        except Exception:
            corrupt += 1

    result.details = {
        "total": len(checkpoints),
        "loadable": loadable,
        "corrupt": corrupt,
        "paths": [str(c.relative_to(run_dir)) for c in checkpoints],
    }

    if corrupt > 0:
        result.status = "failed"
        result.message = f"{corrupt} corrupt checkpoint(s) found"
    elif loadable == len(checkpoints):
        result.status = "passed"
        result.message = f"All {len(checkpoints)} checkpoints are loadable"

    return result


def verify_raw_metrics(run_dir: Path) -> VerificationResult:
    """Verify raw metrics are preserved."""
    result = VerificationResult(check="raw_metrics_preservation", status="unknown")

    metrics_dir = run_dir / "metrics"
    if not metrics_dir.exists():
        result.status = "failed"
        result.message = f"Metrics directory not found: {metrics_dir}"
        return result

    # Look for raw metric files
    raw_files = []
    for ext in [".json", ".csv", ".log"]:
        raw_files.extend(metrics_dir.glob(f"*{ext}"))

    if not raw_files:
        result.status = "failed"
        result.message = "No raw metric files found"
        return result

    result.status = "passed"
    result.message = f"Found {len(raw_files)} raw metric file(s)"
    result.details = {
        "files": [str(f.relative_to(run_dir)) for f in raw_files],
        "total_size_bytes": sum(f.stat().st_size for f in raw_files),
    }

    return result


def verify_logs(run_dir: Path) -> VerificationResult:
    """Verify training logs are preserved."""
    result = VerificationResult(check="logs_preservation", status="unknown")

    log_dir = run_dir / "logs"
    if not log_dir.exists():
        result.status = "failed"
        result.message = f"Log directory not found: {log_dir}"
        return result

    log_files = list(log_dir.glob("*.log")) + list(log_dir.glob("*.txt"))
    if not log_files:
        result.status = "failed"
        result.message = "No log files found"
        return result

    result.status = "passed"
    result.message = f"Found {len(log_files)} log file(s)"
    result.details = {
        "files": [str(f.relative_to(run_dir)) for f in log_files],
    }

    return result


def verify_environment_snapshot(run_dir: Path) -> VerificationResult:
    """Verify environment snapshot exists."""
    result = VerificationResult(check="environment_snapshot", status="unknown")

    env_file = run_dir / "artifacts" / "environment.txt"
    if not env_file.exists():
        result.status = "failed"
        result.message = f"Environment snapshot not found: {env_file}"
        return result

    content = env_file.read_text()
    # Check for key environment info
    has_python = "Python" in content
    has_pytorch = "PyTorch" in content
    has_cuda = "CUDA" in content

    result.status = "passed"
    result.message = "Environment snapshot found"
    result.details = {
        "has_python": has_python,
        "has_pytorch": has_pytorch,
        "has_cuda": has_cuda,
        "size_bytes": env_file.stat().st_size,
    }

    return result


def verify_command_record(run_dir: Path) -> VerificationResult:
    """Verify command record exists."""
    result = VerificationResult(check="command_record", status="unknown")

    cmd_file = run_dir / "artifacts" / "command.sh"
    if not cmd_file.exists():
        result.status = "failed"
        result.message = f"Command record not found: {cmd_file}"
        return result

    result.status = "passed"
    result.message = "Command record found"
    result.details = {
        "command": cmd_file.read_text().strip().split("\n")[-1],
    }

    return result


def verify_chain(run_dir: Path, repo_path: Path) -> list[VerificationResult]:
    """Run full evidence chain verification."""
    results = []

    results.append(verify_commit(repo_path))
    results.append(verify_checkpoint_dir(run_dir))
    results.append(verify_raw_metrics(run_dir))
    results.append(verify_logs(run_dir))
    results.append(verify_environment_snapshot(run_dir))
    results.append(verify_command_record(run_dir))


# ── Search-result verification (P10_T06) ────────────────────────────────────────
#
# Four new functions, each verifying one claim from a candidate paper/repo/dataset
# returned by /repro-discover or /geoai-discover.

PERMISSIVE_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MPL-2.0",
    "LGPL-2.1",
    "LGPL-3.0",
    "CC-BY-4.0",
    "CC0-1.0",
    "Unlicense",
    "Zlib",
}


def verify_paper_identity(paper_record: dict) -> VerificationResult:
    """Cross-validate a paper record by comparing 3+ identity fields.

    paper_record keys: title, authors (list), arxiv_id, doi, year, venue, url.
    PASS requires ≥3 of (title, authors, arxiv_id, doi, year, url) to be
    non-empty AND consistent (e.g., arxiv_id regex match).
    """
    present = []
    if paper_record.get("title"):
        present.append("title")
    if paper_record.get("authors"):
        present.append("authors")
    arxiv = paper_record.get("arxiv_id", "")
    if arxiv and re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", str(arxiv)):
        present.append("arxiv_id")
    elif arxiv:
        return VerificationResult(
            check="paper_identity", passed=False, message=f"arxiv_id {arxiv!r} malformed"
        )
    if paper_record.get("doi") and str(paper_record["doi"]).startswith("10."):
        present.append("doi")
    if paper_record.get("year") and 1990 <= int(paper_record["year"]) <= 2030:
        present.append("year")
    if paper_record.get("url"):
        present.append("url")
    if len(present) < 3:
        return VerificationResult(
            check="paper_identity",
            passed=False,
            message=f"only {len(present)} identity fields: {present}",
        )
    return VerificationResult(
        check="paper_identity", passed=True, message=f"identity verified across {present}"
    )


def verify_commit_sha_pinned(repo_meta: dict) -> VerificationResult:
    """A repo candidate must have a pinned commit SHA (not just a branch name).

    repo_meta keys: repo_url, commit_sha, branch.
    PASS requires commit_sha to be a 7–40 char hex string.
    """
    sha = repo_meta.get("commit_sha", "")
    if not sha:
        return VerificationResult(
            check="commit_sha", passed=False, message="no commit_sha recorded"
        )
    if not re.match(r"^[0-9a-f]{7,40}$", str(sha)):
        return VerificationResult(
            check="commit_sha", passed=False, message=f"commit_sha {sha!r} not a valid hex string"
        )
    return VerificationResult(check="commit_sha", passed=True, message=f"pinned to {sha[:7]}")


def verify_license(repo_meta: dict) -> VerificationResult:
    """Repo license must be in PERMISSIVE_LICENSES (or 'other-permissive' if user-approved)."""
    license_id = (repo_meta.get("license") or "").strip()
    if not license_id:
        return VerificationResult(check="license", passed=False, message="no license recorded")
    if license_id in PERMISSIVE_LICENSES:
        return VerificationResult(check="license", passed=True, message=f"permissive: {license_id}")
    if license_id.lower() in {"gpl-3.0", "gpl-2.0", "agpl-3.0"}:
        return VerificationResult(
            check="license", passed=False, message=f"copyleft forbids derivative: {license_id}"
        )
    return VerificationResult(
        check="license", passed=False, message=f"unknown / non-permissive: {license_id}"
    )


def verify_checkpoint_source(ckpt_meta: dict) -> VerificationResult:
    """A checkpoint must trace to either: (a) paper-author release, or
    (b) a verified re-run (with run_id + commit_sha)."""
    source = ckpt_meta.get("source", "")
    if source == "paper_release":
        return VerificationResult(
            check="checkpoint_source", passed=True, message="from paper-author release"
        )
    if source == "rerun":
        run_id = ckpt_meta.get("run_id")
        commit = ckpt_meta.get("commit_sha", "")
        if run_id and re.match(r"^[0-9a-f]{7,40}$", str(commit)):
            return VerificationResult(
                check="checkpoint_source",
                passed=True,
                message=f"verified rerun {run_id}@{commit[:7]}",
            )
        return VerificationResult(
            check="checkpoint_source",
            passed=False,
            message="rerun source missing run_id or valid commit_sha",
        )
    return VerificationResult(
        check="checkpoint_source", passed=False, message=f"unknown checkpoint source: {source!r}"
    )


def format_results(results: list[VerificationResult]) -> str:
    """Format verification results as Markdown."""
    lines = ["# Evidence Chain Verification Report", ""]

    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")

    lines.append(f"## Summary: {passed} passed, {failed} failed, {skipped} skipped")
    lines.append("")

    for r in results:
        icon = "✅" if r.status == "passed" else "❌" if r.status == "failed" else "⏭️"
        lines.append(f"### {icon} {r.check}")
        lines.append(f"- Status: `{r.status}`")
        lines.append(f"- {r.message}")
        if r.details:
            for k, v in r.details.items():
                lines.append(f"  - {k}: `{v}`")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    p_chain = sub.add_parser("verify-chain", help="Verify full evidence chain")
    p_chain.add_argument("--run-dir", type=Path, required=True)
    p_chain.add_argument("--repo-path", type=Path, default=Path("primary"))

    p_ckpt = sub.add_parser("verify-checkpoints", help="Verify checkpoints")
    p_ckpt.add_argument("--run-dir", type=Path, required=True)

    p_metric = sub.add_parser("verify-metrics", help="Verify raw metrics")
    p_metric.add_argument("--run-dir", type=Path, required=True)

    p_all = sub.add_parser("verify-all", help="Verify all runs")
    p_all.add_argument("--runs-dir", type=Path, default=Path("experiments"))

    args = parser.parse_args()

    if args.command == "verify-chain":
        results = verify_chain(args.run_dir, args.repo_path)
        print(format_results(results))
    elif args.command == "verify-checkpoints":
        result = verify_checkpoint_dir(args.run_dir)
        print(json.dumps(asdict(result), indent=2))
    elif args.command == "verify-metrics":
        result = verify_raw_metrics(args.run_dir)
        print(json.dumps(asdict(result), indent=2))
    elif args.command == "verify-all":
        all_results = []
        for run_dir in sorted(args.runs_dir.iterdir()):
            if run_dir.is_dir():
                results = verify_chain(run_dir, Path("primary"))
                all_results.append(
                    {"run_id": run_dir.name, "results": [asdict(r) for r in results]}
                )
        print(json.dumps(all_results, indent=2, default=str))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
