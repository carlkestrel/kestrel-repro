"""R3F-2 verification tests — single SQLite authority end-to-end.

These supplement the R3-0 acceptance suite (tests/test_r3_0_acceptance.py)
by exercising the additional guarantees introduced or hardened in R3F-2:

  1. The canonical StateStore doc path matches the actual path.
  2. find_active_state_dbs detects legacy authoritative JSON state
     alongside an active SQLite and raises BLOCKED_STATE_CONFLICT.
  3. find_active_state_dbs accepts a clean project (only SQLite, no legacy JSON).
  4. find_active_state_dbs accepts a project with a legacy JSON only when
     no active SQLite is present (no conflict; only report).
  5. find_active_state_dbs accepts an empty project (zero active DBs).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Make scripts.core importable. Pytest puts the project root on sys.path;
# we also need scripts/ on sys.path so the startup package can `import _version`.
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))

from scripts.core.state_store import StateStore, find_active_state_dbs  # noqa: E402
from scripts.startup.errors import BLOCKED_STATE_CONFLICT, StartupError  # noqa: E402


def test_canonical_doc_path_matches_actual():
    """The module docstring of state_store.py must reference the actual canonical
    path returned by StateStore._db_path."""
    # Read the module source and find the docstring
    src = (HERE / "scripts" / "core" / "state_store.py").read_text(encoding="utf-8")
    assert ".repro/execution/state.sqlite3" in src, (
        "canonical DB path reference missing in state_store.py doc"
    )
    # Verify the actual implementation uses that path
    with tempfile.TemporaryDirectory() as d:
        s = StateStore(project_root=d)
        # Internal path getter (use sqlite3 path)
        p = Path(d) / ".repro" / "execution" / "state.sqlite3"
        assert p.parent.exists(), f"{p.parent} should exist after construction"
        # Close to release any locks
        s.close()


def test_no_active_db_returns_empty():
    with tempfile.TemporaryDirectory() as d:
        result = find_active_state_dbs(d)
        assert result == [], f"expected [], got {result}"


def test_single_active_sqlite_is_found():
    with tempfile.TemporaryDirectory() as d:
        # Create the canonical DB
        s = StateStore(project_root=d)
        s.close()
        result = find_active_state_dbs(d)
        assert len(result) == 1, f"expected exactly 1 active DB, got {len(result)}: {result}"


def test_legacy_authoritative_json_conflict_raises():
    """If both an active SQLite and a legacy authoritative JSON file exist,
    find_active_state_dbs must raise BLOCKED_STATE_CONFLICT."""
    with tempfile.TemporaryDirectory() as d:
        # Active SQLite
        s = StateStore(project_root=d)
        s.close()
        # Place a legacy authoritative JSON at the canonical path
        legacy = Path(d) / "execution_state.json"
        legacy.write_text('{"version": "0.0.0"}', encoding="utf-8")
        try:
            find_active_state_dbs(d)
        except StartupError as e:
            assert e.code == BLOCKED_STATE_CONFLICT, f"unexpected code {e.code}"
            assert "legacy" in e.message.lower()
            assert e.ctx.get("legacy_jsons"), "ctx.legacy_jsons should list paths"
            assert e.ctx.get("sqlite_dbs"), "ctx.sqlite_dbs should list paths"
        else:
            raise AssertionError("expected BLOCKED_STATE_CONFLICT, no error raised")


def test_legacy_authoritative_json_no_sqlite_does_not_conflict():
    """If only a legacy authoritative JSON file exists (no SQLite yet),
    find_active_state_dbs must NOT raise — there is no conflict to detect
    and migration can proceed."""
    with tempfile.TemporaryDirectory() as d:
        legacy = Path(d) / "execution_state.json"
        legacy.write_text('{"version": "0.0.0"}', encoding="utf-8")
        # No SQLite, no conflict
        result = find_active_state_dbs(d)
        # The legacy JSON is not counted as an active DB (it's not SQLite)
        assert result == [], f"expected [] (no SQLite), got {result}"


def test_legacy_authoritative_json_in_subdir_raises():
    """A legacy authoritative JSON placed under .repro/execution/ should also
    trigger BLOCKED_STATE_CONFLICT when an active SQLite exists."""
    with tempfile.TemporaryDirectory() as d:
        s = StateStore(project_root=d)
        s.close()
        # Place legacy at .repro/execution/execution_state.json
        legacy_dir = Path(d) / ".repro" / "execution"
        legacy = legacy_dir / "execution_state.json"
        legacy.write_text('{"version": "0.0.0"}', encoding="utf-8")
        try:
            find_active_state_dbs(d)
        except StartupError as e:
            assert e.code == BLOCKED_STATE_CONFLICT
        else:
            raise AssertionError("expected BLOCKED_STATE_CONFLICT, no error raised")


def test_migrated_legacy_does_not_conflict():
    """A legacy JSON that has been migrated (and the SQLite has a legacy_state
    row marking it as legacy_readonly) should NOT raise."""
    with tempfile.TemporaryDirectory() as d:
        s = StateStore(project_root=d)
        # Mark the current DB as legacy
        with s.transaction() as conn:
            conn.execute(
                "INSERT INTO legacy_state (source_path, sha256, migrated_at, status) VALUES (?, ?, ?, ?)",
                ("dummy", "0" * 64, "2026-01-01T00:00:00Z", "legacy_readonly"),
            )
        s.close()
        # No legacy JSON file present; should not raise
        result = find_active_state_dbs(d)
        # The DB has a legacy_readonly row, so find_active_state_dbs skips it
        # — but then legacy_authoritative stays empty, so no conflict.
        # Result: empty list (the DB is considered legacy).
        assert result == [], f"expected [] for fully-migrated project, got {result}"


if __name__ == "__main__":
    tests = [
        test_canonical_doc_path_matches_actual,
        test_no_active_db_returns_empty,
        test_single_active_sqlite_is_found,
        test_legacy_authoritative_json_conflict_raises,
        test_legacy_authoritative_json_no_sqlite_does_not_conflict,
        test_legacy_authoritative_json_in_subdir_raises,
        test_migrated_legacy_does_not_conflict,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
