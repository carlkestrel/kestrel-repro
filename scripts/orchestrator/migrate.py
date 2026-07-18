"""State migration engine for reproctl."""

import json
import re
import shutil
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
MIN_SUPPORTED_VERSION = "0.1.0"

# R1 INVARIANT: this single literal MUST match scripts/_version.py and
# pyproject.toml's [project].version. Tests/test_version_sync.py
# cross-checks them at run time.
try:
    from _version import __version__ as _DEFAULT_PLUGIN_VERSION
except Exception:  # pragma: no cover
    _DEFAULT_PLUGIN_VERSION = "0.2.0"


def get_current_versions(store: Any) -> dict:
    """Read schema_version, plugin_version, plan_hash from state store."""
    return {
        "schema_version": store.get_metadata("schema_version", "unknown"),
        "plugin_version": store.get_metadata("plugin_version", "unknown"),
        "plan_hash": store.get_metadata("plan_hash", "unknown"),
        "project_id": store.get_metadata("project_id", "unknown"),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upgrade_to_1_0_0(store: Any, backup_dir: Path) -> dict:
    """Add schema_version, plugin_version, plan_hash, project_id to metadata."""
    changes = []
    with store.transaction() as conn:
        for key, value in {
            "schema_version": SCHEMA_VERSION,
            "plugin_version": store.get_metadata("plugin_version", _DEFAULT_PLUGIN_VERSION),
            "project_id": store.get_metadata("project_id", str(
                hashlib.sha256(str(store.project_root).encode()).hexdigest()[:16])),
        }.items():
            existing = conn.execute(
                "SELECT value FROM metadata WHERE key=?", (key,)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO metadata(key,value) VALUES(?,?)",
                    (key, json.dumps(value)),
                )
                changes.append(f"added {key}={value}")
            elif key == "schema_version" and json.loads(existing[0]) != SCHEMA_VERSION:
                conn.execute("UPDATE metadata SET value=? WHERE key=?",
                           (json.dumps(value), key))
                changes.append(f"upgraded {key} to {value}")

    plan_path_str = store.get_metadata("plan_path", "")
    plan_hash = ""
    if plan_path_str:
        try:
            plan_hash = hashlib.sha256(Path(plan_path_str).read_bytes()).hexdigest()[:16]
        except Exception:
            plan_hash = "unknown"
    with store.transaction() as conn:
        existing = conn.execute(
            "SELECT value FROM metadata WHERE key='plan_hash'"
        ).fetchone()
        if not existing:
            conn.execute("INSERT INTO metadata(key,value) VALUES(?,?)",
                        ("plan_hash", json.dumps(plan_hash)))
            changes.append(f"added plan_hash={plan_hash}")

    return {"changes": changes, "from_version": "pre-1.0", "to_version": SCHEMA_VERSION}


def migrate(store: Any, target: str | None = None, dry_run: bool = False,
            backup: bool = True) -> dict:
    """Run migrations.

    Args:
        store: StateStore instance
        target: target version string, or None for latest
        dry_run: if True, only check and report
        backup: if True, create backup before migrating

    Returns dict with status, changes, backup_path.
    """
    current = get_current_versions(store)

    if current["schema_version"] == SCHEMA_VERSION:
        return {
            "status": "already_current",
            "current": current,
            "target": target or SCHEMA_VERSION,
            "changes": [],
        }

    if current["schema_version"] != "unknown" and \
       _version_tuple(current["schema_version"]) < _version_tuple(MIN_SUPPORTED_VERSION):
        return {
            "status": "blocked",
            "current": current,
            "reason": f"schema_version {current['schema_version']} is older than "
                     f"minimum supported {MIN_SUPPORTED_VERSION}",
        }

    backup_path = None
    if backup and not dry_run:
        backup_path = _create_backup(store)

    if dry_run:
        changes = _simulate_migration(store, current, target)
        return {
            "status": "dry_run",
            "current": current,
            "target": target or SCHEMA_VERSION,
            "simulated_changes": changes,
            "backup_required": str(backup_path) if backup_path else None,
        }

    changes = upgrade_to_1_0_0(store, backup_path or Path("/tmp"))

    return {
        "status": "migrated",
        "current": get_current_versions(store),
        "previous": current,
        "changes": changes.get("changes", []),
        "backup_path": str(backup_path) if backup_path else None,
    }


def _version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.sub(r"[^\d.]", "", v).split(".")[:3])


def _create_backup(store: Any) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_root = store.project_root / ".repro" / "backups"
    backup_dir = backup_root / f"backup_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup state database
    if store.db_path.exists():
        shutil.copy2(store.db_path, backup_dir / "state.sqlite3")

    # Backup state.json (legacy)
    state_json = store.project_root / ".repro" / "state.json"
    if state_json.exists():
        shutil.copy2(state_json, backup_dir / "state.json")

    # Backup execution state
    exec_state = store.project_root / ".execution" / "execution_state.json"
    if exec_state.exists():
        shutil.copy2(exec_state, backup_dir / "execution_state.json")

    # Write backup manifest
    manifest: dict[str, Any] = {
        "backup_id": ts,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema_version_before": "pre-1.0",
        "files": [],
        "project_root": str(store.project_root),
    }
    for f in backup_dir.iterdir():
        if f.is_file():
            manifest["files"].append({
                "name": f.name,
                "size": f.stat().st_size,
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
            })
    (backup_dir / "backup_manifest.json").write_text(
        json.dumps(manifest, indent=2))
    return backup_dir


def _simulate_migration(store: Any, current: dict, target: str | None) -> list[dict]:
    """Return what would change without actually changing."""
    return [{
        "from": current["schema_version"],
        "to": SCHEMA_VERSION,
        "operation": "upgrade_to_1_0_0",
        "description": "Add schema_version, plugin_version, plan_hash, project_id to metadata"
    }]


def rollback(backup_dir: Path, store: Any) -> dict:
    """Restore from a backup directory."""
    manifest_path = backup_dir / "backup_manifest.json"
    if not manifest_path.exists():
        return {"status": "error", "reason": "Not a valid backup directory"}

    restored = []
    for f in backup_dir.iterdir():
        if f.is_file() and f.suffix in (".sqlite3", ".json"):
            dest = store.project_root
            if f.name == "state.sqlite3":
                dest = store.db_path
            elif f.name == "state.json":
                dest = store.project_root / ".repro" / "state.json"
            elif f.name == "execution_state.json":
                dest = store.project_root / ".execution" / "execution_state.json"
            shutil.copy2(f, dest)
            restored.append(str(f.name))

    return {"status": "restored", "restored_files": restored, "backup_id": backup_dir.name}


def list_backups(store: Any) -> list[dict]:
    """List all backups for a project."""
    backup_root = store.project_root / ".repro" / "backups"
    if not backup_root.exists():
        return []
    backups = []
    for d in sorted(backup_root.iterdir()):
        if d.is_dir() and d.name.startswith("backup_"):
            manifest_path = d / "backup_manifest.json"
            if manifest_path.exists():
                m = json.loads(manifest_path.read_text())
                backups.append(m)
            else:
                backups.append({
                    "backup_id": d.name,
                    "created_at": str(d.stat().st_mtime),
                    "files": [f.name for f in d.iterdir() if f.is_file()],
                })
    return backups
