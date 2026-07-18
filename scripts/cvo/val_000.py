"""
VAL-000 BOOTSTRAP — Confirm project root, create audit directory, check disk space,
                     check git status, create audit_id.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


def run(project_root=None):
    # Resolve project root.
    # When called from reproctl.py via subprocess: cwd may be anywhere.
    # We detect the plugin root from __file__ (this script lives in scripts/cvo/).
    if project_root is None:
        # Default: plugin root (where the .repro/audit dir lives)
        project = Path(__file__).resolve().parents[1]  # cvo/ → scripts/ → plugin/
    else:
        project = Path(project_root).resolve()

    audit_dir = project / ".repro" / "audit"

    audit_id = str(uuid.uuid4())

    for subdir in [
        "nodes",
        "state/heartbeats",
        "locks",
        "logs",
        "evidence",
        "checkpoints",
        "reports",
    ]:
        (audit_dir / subdir).mkdir(parents=True, exist_ok=True)

    # disk space
    try:
        stat = os.statvfs(project)
        disk_free_gb = round(stat.f_bavail * stat.f_frsize / 1e9, 2)
    except Exception:
        disk_free_gb = None

    # git status
    git_commit = ""
    git_dirty = False
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project),
            timeout=10,
        )
        if r.returncode == 0:
            git_commit = r.stdout.strip()[:12]
        r2 = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(project),
            timeout=10,
        )
        git_dirty = bool(r2.stdout.strip())
    except Exception:
        pass

    manifest = {
        "audit_id": audit_id,
        "project_root": str(project),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cvo_version": "0.1.0",
        "disk_free_gb": disk_free_gb,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "audit_dir": str(audit_dir),
    }

    manifest_path = audit_dir / "audit_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    node_state = {
        "node_id": "VAL-000",
        "status": "PASSED",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "evidence_files": [str(manifest_path.relative_to(project))],
        "output_hashes": {
            "audit_manifest": hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:16],
        },
        "extra": manifest,
    }
    node_path = audit_dir / "nodes" / "VAL-000.json"
    node_path.write_text(json.dumps(node_state, indent=2), encoding="utf-8")

    return {
        "status": "PASSED",
        "audit_id": audit_id,
        "disk_free_gb": disk_free_gb,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "audit_dir": str(audit_dir),
        "evidence_files": [str(manifest_path)],
    }


if __name__ == "__main__":
    import sys

    result = run()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "PASSED" else 1)
