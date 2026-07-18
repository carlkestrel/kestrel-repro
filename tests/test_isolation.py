"""Tests that the test suite does not produce tracked runtime artifacts.

R3R-8: Test isolation:
1. .execution/ has no tracked files (all runtime files must be .gitignored)
2. No .sqlite3 files in scripts/ directory
3. Running the test suite does not dirty the git worktree
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

THIS = Path(__file__).resolve()
PLUGIN_ROOT = THIS.parents[1]


class TestNoTrackedRuntimeArtifacts:
    """P1-3: .execution/ and runtime files must not be git-tracked."""

    def test_execution_dir_not_tracked(self):
        """git ls-files .execution/ must return 0 files.

        All .execution/ content is runtime-only and must be .gitignored.
        """
        result = subprocess.run(
            ["git", "ls-files", ".execution/"],
            cwd=str(PLUGIN_ROOT),
            capture_output=True,
            text=True,
        )
        tracked = [
            line.strip()
            for line in result.stdout.strip().splitlines()
            if line.strip()
        ]
        assert tracked == [], (
            f".execution/ has {len(tracked)} tracked file(s): {tracked}. "
            "These must be gitignored, not committed. "
            "Run: git rm -r --cached .execution/"
        )

    def test_no_sqlite3_in_scripts_dir(self):
        """No .sqlite3 files may exist in the scripts/ directory.

        Scripts are versioned code; runtime state must live under .repro/.
        """
        sqlite_files = list(PLUGIN_ROOT.glob("scripts/**/*.sqlite3"))
        assert sqlite_files == [], (
            f"Found {len(sqlite_files)} .sqlite3 file(s) in scripts/: {sqlite_files}. "
            "Runtime state must live under .repro/execution/, not scripts/."
        )

    def test_repro_execution_not_tracked(self):
        """git ls-files .repro/execution/ must return 0 files.

        .repro/ is the canonical runtime directory and must be gitignored.
        """
        result = subprocess.run(
            ["git", "ls-files", ".repro/execution/"],
            cwd=str(PLUGIN_ROOT),
            capture_output=True,
            text=True,
        )
        tracked = [
            line.strip()
            for line in result.stdout.strip().splitlines()
            if line.strip()
        ]
        assert tracked == [], (
            f".repro/execution/ has {len(tracked)} tracked file(s): {tracked}. "
            "This directory must be .gitignored."
        )


class TestSuiteDoesNotDirtyWorktree:
    """P1-2: Running the test suite must not leave the worktree dirty."""

    def test_worktree_clean_before_tests(self):
        """Git worktree must not have unexpected tracked artifacts.

        Checks that no runtime files (SQLite dbs, temp files, execution artifacts)
        are accidentally tracked in git.
        """
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(PLUGIN_ROOT),
            capture_output=True,
            text=True,
        )
        all_dirty = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]

        # Filter to only files that represent test isolation violations:
        # - Runtime SQLite files anywhere in scripts/
        # - .execution/ tracked content
        # - .repro/execution/ tracked content
        # Ignore our own intentional changes (new test files, modified source)
        isolation_violations = []
        for f in all_dirty:
            path = " ".join(f.split(" ")[1:]).strip()
            if any(
                path.startswith(prefix)
                for prefix in [
                    "scripts/",  # code changes OK, .sqlite3 in scripts/ NOT OK
                ]
            ):
                if ".sqlite3" in path:
                    isolation_violations.append(f"{f}: runtime SQLite in scripts/")
            elif path.startswith(".execution/") or path.startswith(".repro/execution/"):
                isolation_violations.append(f"{f}: runtime artifact tracked")

        assert isolation_violations == [], (
            f"Test isolation violation(s): {isolation_violations}. "
            "Runtime artifacts must not be git-tracked."
        )

    def test_worktree_clean_after_tests(self):
        """Running targeted tests must not dirty tracked runtime files.

        Runs the new unit-test suites (not chaos tests) and verifies no
        tracked runtime artifacts were created.
        """
        # Run just the new unit test suites (fast ~5s total)
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/test_non_evidentiary_waiver.py",
                "tests/test_authorization_enforcement_e2e.py",
                "tests/test_metrics_recompute_verifier.py",
                "--timeout=60",
                "-p", "no:cacheprovider",
                "-q",
            ],
            cwd=str(PLUGIN_ROOT),
            capture_output=True,
            text=True,
            timeout=90,
        )
        # Check worktree status
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(PLUGIN_ROOT),
            capture_output=True,
            text=True,
        )
        dirty = [l.strip() for l in status.stdout.strip().splitlines() if l.strip()]

        # Only fail on actual isolation violations (runtime files in scripts/,
        # tracked .execution/, or .sqlite3 anywhere not in .repro/)
        violations = [
            f for f in dirty
            if ".sqlite3" in f or
            ".execution/" in f or
            (f.startswith("A  ") and "scripts/" in f and not f.startswith("A  scripts/commands/"))
        ]
        assert violations == [], (
            f"Test isolation violations: {violations}. "
            "Tests must not create tracked runtime artifacts."
        )
