"""Backup, restore, and integrity-check for reproctl projects."""

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def backup_project(project_root: Path, output_dir: Path | None = None,
                   include_checkpoints: bool = False) -> dict:
    """Create a backup snapshot of a project.

    Args:
        project_root: project directory
        output_dir: where to write the backup zip; defaults to .repro/backups/
        include_checkpoints: if True, include checkpoint files (can be large)

    Returns dict with backup_id, created_at, files, total_size.
    """
    output_dir = output_dir or (project_root / ".repro" / "backups")
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"snapshot_{ts}"
    snapshot_dir = output_dir / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    files_backed_up: list[dict] = []
    total_size = 0

    # Core state files (always include)
    core_patterns = [
        ".repro/state.json",
        ".repro/state.sqlite3",
        ".repro/state.snapshot.json",
        ".execution/execution_state.json",
        ".execution/task_graph.yaml",
        ".repro/config.yaml",
        "repro.yaml",
    ]

    for pattern in core_patterns:
        p = project_root / pattern
        if p.exists():
            _backup_file(p, snapshot_dir / p.name, files_backed_up)
            total_size += p.stat().st_size

    # Checkpoint index (no actual data unless include_checkpoints)
    ckpt_index = project_root / ".repro" / "checkpoint_index.json"
    if ckpt_index.exists():
        index = json.loads(ckpt_index.read_text())
        # Record each checkpoint path + hash without copying large files
        ckpt_records: list[dict] = []
        for entry in index.get("checkpoints", []):
            ckpt_path = project_root / entry["path"]
            if ckpt_path.exists():
                if include_checkpoints:
                    _backup_file(ckpt_path, snapshot_dir / f"ckpt_{entry['id']}.pt", files_backed_up)
                    total_size += ckpt_path.stat().st_size
                ckpt_records.append({
                    "id": entry["id"],
                    "path": entry["path"],
                    "sha256": hashlib.sha256(ckpt_path.read_bytes()).hexdigest()[:16],
                    "size": ckpt_path.stat().st_size,
                    "included": include_checkpoints,
                })
            else:
                ckpt_records.append({
                    "id": entry["id"], "path": entry["path"],
                    "sha256": "MISSING", "size": 0, "included": False,
                })
        (snapshot_dir / "checkpoint_index.json").write_text(
            json.dumps({"checkpoints": ckpt_records, "included_data": include_checkpoints}, indent=2))

    # Run manifest index
    run_manifest = project_root / ".repro" / "run_manifest.json"
    if run_manifest.exists():
        _backup_file(run_manifest, snapshot_dir / "run_manifest.json", files_backed_up)
        total_size += run_manifest.stat().st_size

    # Evidence index
    evidence_dir = project_root / ".execution" / "evidence"
    if evidence_dir.exists():
        evidence_index = _build_evidence_index(evidence_dir)
        (snapshot_dir / "evidence_index.json").write_text(
            json.dumps(evidence_index, indent=2))

    # Backup manifest
    manifest: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "files": files_backed_up,
        "total_size_bytes": total_size,
        "schema_version": "1.0.0",
    }
    (snapshot_dir / "snapshot_manifest.json").write_text(
        json.dumps(manifest, indent=2))

    return manifest


def _backup_file(src: Path, dst: Path, records: list[dict]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    records.append({
        "name": src.name,
        "path": str(src),
        "size": src.stat().st_size,
        "sha256": hashlib.sha256(src.read_bytes()).hexdigest()[:16],
    })


def _build_evidence_index(evidence_dir: Path) -> dict:
    index: dict[str, Any] = {"entries": [], "total_size": 0}
    for f in evidence_dir.rglob("*"):
        if f.is_file():
            index["entries"].append({
                "name": f.name,
                "path": str(f.relative_to(evidence_dir)),
                "size": f.stat().st_size,
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest()[:16],
            })
            index["total_size"] += f.stat().st_size
    return index


def restore_project(project_root: Path, snapshot_id: str,
                    output_dir: Path | None = None) -> dict:
    """Restore a project from a backup snapshot."""
    output_dir = output_dir or (project_root / ".repro" / "backups")
    snapshot_dir = output_dir / snapshot_id
    if not snapshot_dir.exists():
        return {"status": "error", "reason": f"Snapshot not found: {snapshot_id}"}

    manifest_path = snapshot_dir / "snapshot_manifest.json"
    if not manifest_path.exists():
        return {"status": "error", "reason": "Invalid snapshot: no manifest"}

    manifest = json.loads(manifest_path.read_text())

    # Verify integrity before restoring
    errors = []
    for rec in manifest.get("files", []):
        p = snapshot_dir / rec["name"]
        if not p.exists():
            errors.append(f"Missing: {rec['name']}")
        elif hashlib.sha256(p.read_bytes()).hexdigest()[:16] != rec["sha256"]:
            errors.append(f"Checksum mismatch: {rec['name']}")

    if errors:
        return {"status": "error", "reason": "Integrity check failed", "errors": errors}

    restored = []
    for rec in manifest.get("files", []):
        src = snapshot_dir / rec["name"]
        if rec["name"] == "state.sqlite3":
            dst = project_root / ".repro" / "execution" / "state.sqlite3"
        elif rec["name"] == "state.json":
            dst = project_root / ".repro" / "state.json"
        elif rec["name"] == "execution_state.json":
            dst = project_root / ".execution" / "execution_state.json"
        else:
            dst = project_root / ".repro" / rec["name"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(rec["name"])

    return {
        "status": "restored",
        "snapshot_id": snapshot_id,
        "restored_files": restored,
        "verified": True,
    }


def integrity_check(project_root: Path) -> dict:
    """Run full integrity checks on a project."""
    issues: list[str] = []
    warnings: list[str] = []
    checks_passed: list[str] = []

    # 1. SQLite integrity
    db_path = project_root / ".repro" / "execution" / "state.sqlite3"
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result is not None and result[0] == "ok":
                checks_passed.append("sqlite_integrity")
            else:
                issues.append(f"SQLite integrity: {result}")
            conn.close()
        except Exception as e:
            issues.append(f"SQLite: {e}")
    else:
        warnings.append("No state.sqlite3 found (may be a fresh project)")

    # 2. State.json schema (if exists)
    state_json = project_root / ".repro" / "state.json"
    if state_json.exists():
        try:
            state = json.loads(state_json.read_text())
            if "gates" not in state:
                issues.append("state.json missing 'gates' key")
            else:
                checks_passed.append("state_json_schema")
        except json.JSONDecodeError as e:
            issues.append(f"state.json parse error: {e}")

    # 3. Check for orphaned RUNNING tasks
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            running = conn.execute(
                "SELECT id, name, pid, started_at FROM tasks WHERE status='RUNNING'"
            ).fetchall()
            for row in running:
                pid = row["pid"]
                if pid:
                    try:
                        os.kill(pid, 0)  # check if process exists
                    except OSError:
                        issues.append(
                            f"Orphaned RUNNING task '{row['name']}' (pid={pid}) — "
                            f"process dead but state RUNNING"
                        )
            conn.close()
        except Exception as e:
            issues.append(f"Orphan check: {e}")

    # 4. PASS tasks without evidence
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            passed = conn.execute(
                "SELECT id, name, finished_at FROM tasks WHERE status='PASS'"
            ).fetchall()
            for row in passed:
                if not row["finished_at"]:
                    issues.append(f"Task '{row['name']}' is PASS but finished_at is null")
            conn.close()
            checks_passed.append("pass_tasks_have_finished_at")
        except Exception as e:
            issues.append(f"Pass evidence check: {e}")

    # 5. Check for truncated logs (empty final line)
    log_dir = project_root / ".repro" / "logs"
    if log_dir.exists():
        for log in log_dir.rglob("*.log"):
            try:
                content = log.read_text(errors="replace")
                if content and not content.endswith("\n"):
                    warnings.append(f"Log may be truncated (no final newline): {log.name}")
            except Exception:
                pass

    # 6. Plan hash validation (if plan_path in metadata)
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            plan_path_val = conn.execute(
                "SELECT value FROM metadata WHERE key='plan_path'"
            ).fetchone()
            plan_hash_val = conn.execute(
                "SELECT value FROM metadata WHERE key='plan_hash'"
            ).fetchone()
            if plan_path_val and plan_hash_val:
                plan_path = json.loads(plan_path_val[0])
                expected_hash = json.loads(plan_hash_val[0])
                if Path(plan_path).exists():
                    actual = hashlib.sha256(Path(plan_path).read_bytes()).hexdigest()[:16]
                    if actual != expected_hash:
                        issues.append(
                            f"Plan hash mismatch: plan on disk differs from recorded hash"
                        )
                    else:
                        checks_passed.append("plan_hash_verified")
                else:
                    warnings.append(f"Plan file not found: {plan_path}")
            conn.close()
        except Exception as e:
            warnings.append(f"Plan hash check: {e}")

    # 7. Check for tasks without acceptance_tests
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            no_acceptance = conn.execute(
                "SELECT id, name, acceptance_json FROM tasks WHERE acceptance_json='[]'"
            ).fetchall()
            for row in no_acceptance:
                issues.append(
                    f"Task '{row['name']}' has empty acceptance_tests — "
                    f"may cause false completion"
                )
            conn.close()
            checks_passed.append("tasks_have_acceptance")
        except Exception:
            pass

    return {
        "project_root": str(project_root),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks_passed": checks_passed,
        "warnings": warnings,
        "issues": issues,
        "summary": "PASS" if not issues else "FAIL",
    }
