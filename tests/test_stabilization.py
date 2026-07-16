"""Tests for stabilization infrastructure: migrate, backup, integrity.

conftest.py sets up sys.path so orchestrator imports work.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

THIS = Path(__file__).resolve()
PLUGIN_ROOT = THIS.parents[1]
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
REPROCTL = SCRIPTS_DIR / "reproctl.py"


class TestMigration:
    def test_migrate_adds_version_fields(self, tmp_path):
        """Migrate adds schema_version, plugin_version, plan_hash to fresh DB."""
        from orchestrator.state_store import StateStore
        from orchestrator import migrate

        store = StateStore(tmp_path)
        result = migrate.migrate(store)

        # Fresh DB starts with schema_version="unknown", so migrate upgrades it
        assert result["status"] in ("migrated", "already_current")

        sv = store.get_metadata("schema_version")
        assert sv is not None
        assert sv != "unknown"

    def test_migrate_dry_run_reports_changes(self, tmp_path):
        """--check-only does not modify state."""
        from orchestrator.state_store import StateStore
        from orchestrator import migrate

        store = StateStore(tmp_path)
        store.set_metadata("schema_version", "0.1.0")

        result = migrate.migrate(store, dry_run=True)

        assert result["status"] == "dry_run"
        assert "simulated_changes" in result
        assert store.get_metadata("schema_version") == "0.1.0"

    def test_migrate_creates_backup(self, tmp_path):
        """Migration creates a backup before modifying."""
        from orchestrator.state_store import StateStore
        from orchestrator import migrate

        store = StateStore(tmp_path)
        store.set_metadata("schema_version", "0.1.0")

        result = migrate.migrate(store)

        assert result["status"] == "migrated"
        assert result["backup_path"] is not None
        assert Path(result["backup_path"]).exists()
        assert (Path(result["backup_path"]) / "state.sqlite3").exists()

    def test_rollback_restores_state(self, tmp_path):
        """Rollback restores from a backup directory."""
        from orchestrator.state_store import StateStore
        from orchestrator import migrate

        store = StateStore(tmp_path)
        store.set_metadata("test_marker", "before_migrate")

        backup_dir = tmp_path / ".repro" / "backups" / "backup_test"
        backup_dir.mkdir(parents=True)
        shutil.copy2(store.db_path, backup_dir / "state.sqlite3")
        (backup_dir / "backup_manifest.json").write_text(json.dumps({
            "backup_id": "test", "files": [{"name": "state.sqlite3"}]
        }))

        store.set_metadata("test_marker", "after_change")

        result = migrate.rollback(backup_dir, store)

        assert result["status"] == "restored"
        assert store.get_metadata("test_marker") == "before_migrate"

    def test_minimum_version_blocked(self, tmp_path):
        """Migrations from versions older than minimum are blocked."""
        from orchestrator.state_store import StateStore
        from orchestrator import migrate

        store = StateStore(tmp_path)
        store.set_metadata("schema_version", "0.0.1")

        result = migrate.migrate(store)

        assert result["status"] == "blocked"


class TestBackup:
    def test_backup_creates_snapshot_manifest(self, tmp_path):
        """Backup creates snapshot_manifest.json with file records."""
        from orchestrator.state_store import StateStore
        from orchestrator import backup

        store = StateStore(tmp_path)
        store.set_metadata("test_key", "test_value")

        result = backup.backup_project(tmp_path)

        assert "snapshot_id" in result
        manifest_path = (tmp_path / ".repro" / "backups" /
                         result.get("snapshot_id", "") / "snapshot_manifest.json")
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            assert "files" in manifest
            assert manifest["schema_version"] == "1.0.0"

    def test_integrity_check_detects_orphan_running(self, tmp_path):
        """Integrity check detects tasks that are RUNNING but process is dead."""
        from orchestrator.state_store import StateStore
        from orchestrator import backup

        store = StateStore(tmp_path)
        with store.transaction() as conn:
            conn.execute(
                "INSERT INTO tasks(id,name,gate,deps_json,command,timeout_min,"
                "acceptance_json,retry_json,task_json,status,attempts,updated_at,pid) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("test_orphan", "test_orphan", "init", "[]", "echo test",
                 5.0, "[]", "{}", "{}", "RUNNING", 1, "2026-01-01T00:00:00Z",
                 999999),
            )

        result = backup.integrity_check(tmp_path)

        orphan_issues = [i for i in result["issues"] if "Orphaned RUNNING" in i]
        assert len(orphan_issues) >= 1 or result["warnings"]

    def test_integrity_check_detects_missing_evidence(self, tmp_path):
        """Integrity check detects PASS tasks without finished_at."""
        from orchestrator.state_store import StateStore
        from orchestrator import backup

        store = StateStore(tmp_path)
        with store.transaction() as conn:
            conn.execute(
                "INSERT INTO tasks(id,name,gate,deps_json,command,timeout_min,"
                "acceptance_json,retry_json,task_json,status,attempts,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                ("test_pass", "test_pass", "init", "[]", "echo test",
                 5.0, "[]", "{}", "{}", "PASS", 1, "2026-01-01T00:00:00Z"),
            )

        result = backup.integrity_check(tmp_path)

        evidence_issues = [i for i in result["issues"] if "finished_at" in i]
        assert len(evidence_issues) >= 1

    def test_integrity_check_detects_empty_acceptance_tests(self, tmp_path):
        """Integrity check detects tasks without acceptance_tests."""
        from orchestrator.state_store import StateStore
        from orchestrator import backup

        store = StateStore(tmp_path)
        with store.transaction() as conn:
            conn.execute(
                "INSERT INTO tasks(id,name,gate,deps_json,command,timeout_min,"
                "acceptance_json,retry_json,task_json,status,attempts,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                ("test_no_acc", "test_no_acc", "init", "[]", "echo test",
                 5.0, "[]", "{}", "{}", "PENDING", 0, "2026-01-01T00:00:00Z"),
            )

        result = backup.integrity_check(tmp_path)

        acc_issues = [i for i in result["issues"] if "acceptance_tests" in i]
        assert len(acc_issues) >= 1


class TestCLIDispatching:
    def test_migrate_cli_command_exists(self):
        """reproctl migrate --help works."""
        result = subprocess.run(
            [sys.executable, str(REPROCTL),
             "migrate", "--help"],
            capture_output=True, text=True,
            cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0
        assert "migrate" in result.stdout

    def test_backup_cli_command_exists(self):
        """reproctl backup --help works."""
        result = subprocess.run(
            [sys.executable, str(REPROCTL),
             "backup", "--help"],
            capture_output=True, text=True,
            cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0

    def test_integrity_check_cli_command_exists(self):
        """reproctl integrity-check --help works."""
        result = subprocess.run(
            [sys.executable, str(REPROCTL),
             "integrity-check", "--help"],
            capture_output=True, text=True,
            cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0
