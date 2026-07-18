"""conftest.py — pytest hooks for kestrel-repro.

R1 INVARIANTS (do not regress):
  * No `sys.path.insert` / `sys.path.append` here. If a test cannot
    import without it, fix the package, not the path.
  * No hard-coded absolute paths (e.g. /home/<user>/...). Tests use
    ``scripts.fixture_locator`` to find fixture files.
  * Imports work because the project is installed (`pip install -e .`)
    and the ``scripts`` package is importable.

This conftest provides ONLY:
  1. A ``plugin_root`` fixture (Path-like) that locates the plugin
     checkout — useful for tests that need to invoke a subprocess
     against the source tree (for example, to call ``smoke_test.py``
     or ``reproctl.py`` as a script). The location is discovered via
     ``importlib.resources`` and the installed ``scripts`` package,
     NOT via cwd.
  2. A ``fixtures_dir`` fixture that returns a Path-like to the
     ``fixtures`` directory via ``scripts.fixture_locator``.
  3. A ``repo_root`` session fixture that, when editable-install
     tests are running, points at the on-disk checkout so that
     subprocess invocations of legacy scripts (``reproctl.py`` etc.)
     still resolve. Falls back gracefully when the package is not
     installed editable.
"""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest


def _discover_plugin_root() -> Path | None:
    """Locate the on-disk plugin checkout root, or None when not
    editable-installed.

    Walks parents of the installed ``scripts`` package until it finds
    a directory that contains ``pyproject.toml`` and ``fixtures/``.
    This is the only place we touch Path-from-__file__; tests should
    never call it directly.
    """
    try:
        spec = importlib.util.find_spec("scripts")
    except (ImportError, ValueError):
        return None
    if spec is None or spec.origin is None:
        return None
    scripts_dir = Path(spec.origin).resolve().parent
    for ancestor in (scripts_dir, *scripts_dir.parents):
        if (ancestor / "pyproject.toml").exists() and (ancestor / "fixtures").exists():
            return ancestor
    return None


@pytest.fixture(scope="session")
def plugin_root() -> Path | None:
    """Return the plugin checkout root for subprocess invocations.

    Returns None when running against a wheel install with no source
    tree present, in which case subprocess tests that need the
    source tree should be skipped.
    """
    return _discover_plugin_root()


@pytest.fixture(scope="session")
def fixtures_dir():
    """Return the ``fixtures`` directory via scripts.fixture_locator.

    Returns a Path on disk when the package is editable-installed,
    or an importlib.resources Traversable otherwise.
    """
    from scripts.fixture_locator import data_root

    return data_root("fixtures")
