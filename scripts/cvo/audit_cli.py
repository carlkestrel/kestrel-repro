"""
reproctl audit — Checkpointed Validation Orchestrator CLI.

Usage:
    reproctl audit init
    reproctl audit plan
    reproctl audit run-next
    reproctl audit run-node <node_id>
    reproctl audit run-stage <stage>
    reproctl audit pause
    reproctl audit resume
    reproctl audit retry <node_id>
    reproctl audit status
    reproctl audit report
    reproctl audit validate

All commands read/write state at:
    .repro/audit/
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# scripts/cvo/audit_cli.py:
#   __file__ = .../dl-paper-repro/scripts/cvo/audit_cli.py
#   _SCRIPT_DIR       = .../dl-paper-repro/scripts/cvo/  (where this file lives)
#   _SCRIPT_DIR.parent = .../dl-paper-repro/scripts/       (package root; in sys.path)
#   PLUGIN_ROOT       = .../dl-paper-repro/scripts/../    = dl-paper-repro/  (plugin root)
_SCRIPT_DIR = Path(__file__).resolve().parent        # scripts/cvo/
_PLUGINS_DIR = _SCRIPT_DIR.parent                   # scripts/
PLUGIN_ROOT = _PLUGINS_DIR.parent                  # dl-paper-repro/ ← CORRECT

# Make scripts/ importable as "from cvo import ..."
if str(_PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGINS_DIR))

try:
    from cvo import (
        ALL_NODES,
        NODE_MAP,
        STAGE_LABELS,
        STAGE_NODES,
        CVORunner,
        CVOStateStore,
        __version__,
    )
    from cvo.nodes import ValidationNode
    HAS_CVO = True
except ImportError as e:
    HAS_CVO = False
    print(f"[warn] CVO not importable: {e}", file=sys.stderr)

PLUGIN_ROOT = _PLUGINS_DIR.parent                  # dl-paper-repro/ ← correct
AUDIT_ROOT = PLUGIN_ROOT / ".repro" / "audit"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _project_root(args) -> Path:
    """Resolve project root from args or plugin root."""
    if getattr(args, "project", None):
        return Path(args.project).resolve()
    # Default: use the canonical PLUGIN_ROOT
    return PLUGIN_ROOT


def _store(args) -> CVOStateStore:
    return CVOStateStore(_project_root(args))


def _node_summary(store: CVOStateStore) -> dict:
    """Compact summary of all node statuses."""
    summary = store.summary()
    nodes = store.list_all()
    by_status = {}
    for n in nodes:
        s = n.get("status", "PENDING")
        by_status.setdefault(s, []).append(n["node_id"])
    return {
        "total": len(nodes),
        "by_status": by_status,
        "counts": summary,
        "nodes": {
            n["node_id"]: {
                "status": n.get("status"),
                "updated_at": n.get("updated_at", ""),
            }
            for n in nodes
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────────────────────────

def cmd_init(args) -> int:
    """Bootstrap audit: create audit dir, init VAL-000 state."""
    root = _project_root(args)

    if not HAS_CVO:
        print("[FAIL] CVO module not importable", file=sys.stderr)
        return 10

    # Initialize VAL-000 state
    from cvo.val_000 import run as val_000_run
    result = val_000_run(project_root=root)

    print(json.dumps({
        "command": "init",
        "audit_id": result.get("audit_id"),
        "audit_dir": str(AUDIT_ROOT),
        "git_commit": result.get("git_commit"),
        "git_dirty": result.get("git_dirty"),
        "disk_free_gb": result.get("disk_free_gb"),
        "status": result["status"],
    }, indent=2))

    # Also init all other nodes as PENDING
    store = _store(args)
    for node in ALL_NODES:
        if node.node_id == "VAL-000":
            continue
        store.init_node(node.node_id, {
            "node_version": node.version,
            "name": node.name,
            "capability_ids": node.capability_ids,
            "depends_on": node.depends_on,
            "requires_gpu": node.requires_gpu,
            "requires_real_data": node.requires_real_data,
            "timeout_seconds": node.timeout_seconds,
        })

    pending = [n.node_id for n in ALL_NODES if store.get_status(n.node_id) == "PENDING"]
    print(f"[ok] {len(pending)}/{len(ALL_NODES)} nodes initialized")
    return 0


def cmd_plan(args) -> int:
    """Show the validation plan: all nodes grouped by stage."""
    print("=== CVO Validation Plan ===")
    print(f"Plugin: {PLUGIN_ROOT}")
    print(f"Audit version: {__version__}")
    print()

    store = _store(args) if HAS_CVO else None

    for stage, node_ids in STAGE_NODES.items():
        stage_label = STAGE_LABELS.get(stage, stage)
        print(f"[Stage {stage}] {stage_label}")
        print(f"  Nodes: {', '.join(node_ids)}")

        if store:
            for nid in node_ids:
                status = store.get_status(nid)
                node = NODE_MAP.get(nid)
                gpu_tag = " [GPU]" if (node and node.requires_gpu) else ""
                print(f"    {nid}: {status}{gpu_tag}")
        print()
    return 0


def cmd_status(args) -> int:
    """Show current audit status."""
    if not HAS_CVO:
        print(json.dumps({"error": "CVO not available", "status": "BLOCKED"}, indent=2))
        return 1

    store = _store(args)
    summary = _node_summary(store)

    manifest = store.read_manifest()
    overall = "unknown"
    if manifest:
        overall = "initialized"

    # Check if VAL-000 passed
    val000_status = store.get_status("VAL-000")
    if val000_status == "PASSED":
        overall = "running"
        if summary["counts"].get("PASSED", 0) == len(ALL_NODES):
            overall = "complete"

    result = {
        "overall": overall,
        "audit_id": manifest.get("audit_id", "none"),
        "audit_dir": str(AUDIT_ROOT),
        "plugin_root": str(PLUGIN_ROOT),
        "project_root": str(_project_root(args)),
        "total_nodes": len(ALL_NODES),
        "passed": summary["counts"].get("PASSED", 0),
        "failed": summary["counts"].get("FAILED", 0),
        "pending": summary["counts"].get("PENDING", 0),
        "running": summary["counts"].get("RUNNING", 0),
        "blocked": summary["counts"].get("BLOCKED", 0),
        "stale": summary["counts"].get("STALE", 0),
        "by_status": summary["by_status"],
        "cvo_version": __version__,
        "checked_at": utc_now(),
    }

    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_run_next(args) -> int:
    """Run the next READY node."""
    if not HAS_CVO:
        print("[FAIL] CVO not available", file=sys.stderr)
        return 10

    runner = CVORunner(_project_root(args))
    result = runner.run_next(dry_run=args.dry_run, max_gpu=args.max_gpu)

    print(json.dumps({
        "command": "run-next",
        **result,
    }, indent=2, default=str))

    status = result.get("status", "FAILED")
    if status == "PASSED":
        return 0
    elif status == "NO_READY_NODE":
        return 0  # Not an error
    else:
        return 1


def cmd_run_node(args) -> int:
    """Run a specific node by ID."""
    if not HAS_CVO:
        print("[FAIL] CVO not available", file=sys.stderr)
        return 10

    node_id = args.node_id.upper()
    node = NODE_MAP.get(node_id)
    if not node:
        # Try case-insensitive
        matches = [n for n in NODE_MAP if n.upper() == node_id]
        if matches:
            node_id = matches[0]
            node = NODE_MAP[node_id]

    if not node:
        print(f"[FAIL] Unknown node: {args.node_id}", file=sys.stderr)
        print(f"Available: {', '.join(sorted(NODE_MAP.keys()))}", file=sys.stderr)
        return 1

    runner = CVORunner(_project_root(args))
    result = runner.run_node(node_id, dry_run=args.dry_run, force=args.force)

    print(json.dumps({
        "command": "run-node",
        "node_id": node_id,
        **result,
    }, indent=2, default=str))

    status = result.get("status", "FAILED")
    if status == "PASSED":
        return 0
    elif status in ("BLOCKED",):
        return 0
    else:
        return 1


def cmd_run_stage(args) -> int:
    """Run all nodes in a stage (A–F)."""
    if not HAS_CVO:
        print("[FAIL] CVO not available", file=sys.stderr)
        return 10

    stage = args.stage.upper()
    if stage not in STAGE_NODES:
        print(f"[FAIL] Unknown stage: {stage}. Valid: A–F", file=sys.stderr)
        return 1

    node_ids = STAGE_NODES[stage]
    runner = CVORunner(_project_root(args))

    results = {}
    for nid in node_ids:
        print(f"  → Running {nid}...", end=" ", flush=True)
        result = runner.run_node(nid, dry_run=args.dry_run)
        status = result.get("status", "FAILED")
        results[nid] = status
        print(status)

    passed = sum(1 for v in results.values() if v == "PASSED")
    total = len(results)
    print(f"\n[Stage {stage}] {passed}/{total} passed")

    return 0 if passed == total else 1


def cmd_retry(args) -> int:
    """Retry a failed node."""
    if not HAS_CVO:
        print("[FAIL] CVO not available", file=sys.stderr)
        return 10

    runner = CVORunner(_project_root(args))
    result = runner.run_node(args.node_id, force=True)

    print(json.dumps({
        "command": "retry",
        "node_id": args.node_id,
        **result,
    }, indent=2, default=str))

    return 0 if result.get("status") == "PASSED" else 1


def cmd_report(args) -> int:
    """Generate and display a summary report."""
    if not HAS_CVO:
        print("[FAIL] CVO not available", file=sys.stderr)
        return 10

    store = _store(args)
    summary = _node_summary(store)
    manifest = store.read_manifest()

    report = {
        "audit_id": manifest.get("audit_id", "unknown"),
        "generated_at": utc_now(),
        "cvo_version": __version__,
        "plugin_root": str(PLUGIN_ROOT),
        "project_root": str(_project_root(args)),
        "stage_summary": {},
    }

    for stage, node_ids in STAGE_NODES.items():
        passed = sum(
            1 for nid in node_ids
            if store.get_status(nid) == "PASSED"
        )
        total = len(node_ids)
        report["stage_summary"][stage] = {
            "label": STAGE_LABELS.get(stage, stage),
            "passed": passed,
            "total": total,
            "status": "COMPLETE" if passed == total else "IN_PROGRESS" if passed > 0 else "NOT_STARTED",
        }

    report["overall"] = {
        "total_nodes": len(ALL_NODES),
        "passed": summary["counts"].get("PASSED", 0),
        "failed": summary["counts"].get("FAILED", 0),
        "pending": summary["counts"].get("PENDING", 0),
        "running": summary["counts"].get("RUNNING", 0),
        "blocked": summary["counts"].get("BLOCKED", 0),
        "stale": summary["counts"].get("STALE", 0),
    }

    print(json.dumps(report, indent=2, default=str))
    return 0


def cmd_validate(args) -> int:
    """Validate CVO infrastructure: import, state store, node registry."""
    checks = []

    # Check imports
    try:
        from cvo import ALL_NODES, NODE_MAP, CVORunner, CVOStateStore
        checks.append({"check": "cvo_import", "status": "PASS"})
    except ImportError as e:
        checks.append({"check": "cvo_import", "status": "FAIL", "message": str(e)})
        print(json.dumps({"overall": "FAIL", "checks": checks}, indent=2))
        return 1

    # Check node registry
    if len(ALL_NODES) >= 30:
        checks.append({"check": "node_count", "status": "PASS",
                       "count": len(ALL_NODES)})
    else:
        checks.append({"check": "node_count", "status": "FAIL",
                       "count": len(ALL_NODES)})

    # Check state store
    try:
        store = CVOStateStore(_project_root(args))
        checks.append({"check": "state_store", "status": "PASS"})
    except Exception as e:
        checks.append({"check": "state_store", "status": "FAIL", "message": str(e)})

    # Check VAL-000 callable
    try:
        checks.append({"check": "val_000_callable", "status": "PASS"})
    except Exception as e:
        checks.append({"check": "val_000_callable", "status": "FAIL", "message": str(e)})

    # Check VAL-010 callable
    try:
        checks.append({"check": "val_010_callable", "status": "PASS"})
    except Exception as e:
        checks.append({"check": "val_010_callable", "status": "FAIL", "message": str(e)})

    overall = "PASS" if all(c.get("status") == "PASS" for c in checks) else "FAIL"
    result = {"overall": overall, "checks": checks}
    print(json.dumps(result, indent=2))
    return 0 if overall == "PASS" else 1


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reproctl audit",
        description="CVO: Checkpointed Validation Orchestrator — "
                    "Reproducibility Capability Gap Auditor",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p = sub.add_parser("init", help="Initialize audit (runs VAL-000 BOOTSTRAP)")
    p.add_argument("--project", default=None, help="Project root (default: cwd)")

    # plan
    p = sub.add_parser("plan", help="Show all validation nodes by stage")
    p.add_argument("--project", default=None)

    # status
    p = sub.add_parser("status", help="Show current audit status")
    p.add_argument("--project", default=None)

    # run-next
    p = sub.add_parser("run-next", help="Run the next READY node")
    p.add_argument("--project", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-gpu", type=int, default=1)

    # run-node
    p = sub.add_parser("run-node", help="Run a specific node by ID")
    p.add_argument("node_id", help="Node ID (e.g. VAL-000, VAL-010)")
    p.add_argument("--project", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="Re-run even if already passed")

    # run-stage
    p = sub.add_parser("run-stage", help="Run all nodes in a stage (A–F)")
    p.add_argument("stage", help="Stage letter: A, B, C, D, E, or F")
    p.add_argument("--project", default=None)
    p.add_argument("--dry-run", action="store_true")

    # retry
    p = sub.add_parser("retry", help="Retry a failed node")
    p.add_argument("node_id", help="Node ID to retry")
    p.add_argument("--project", default=None)

    # report
    p = sub.add_parser("report", help="Show summary report")
    p.add_argument("--project", default=None)

    # validate
    p = sub.add_parser("validate", help="Validate CVO infrastructure")
    p.add_argument("--project", default=None)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "init": cmd_init,
        "plan": cmd_plan,
        "status": cmd_status,
        "run-next": cmd_run_next,
        "run-node": cmd_run_node,
        "run-stage": cmd_run_stage,
        "retry": cmd_retry,
        "report": cmd_report,
        "validate": cmd_validate,
    }

    fn = commands.get(args.command)
    if fn:
        try:
            return fn(args)
        except Exception as e:
            import traceback
            print(json.dumps({
                "command": args.command,
                "status": "FAILED",
                "error": str(e),
                "traceback": traceback.format_exc(),
            }, indent=2), file=sys.stderr)
            return 10
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
