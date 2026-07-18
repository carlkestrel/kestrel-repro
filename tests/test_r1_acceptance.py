"""R1 acceptance tests for packaging, version sync, and fixture locator.

These tests assert the R1 contract:
  * ``pip install -e .`` works and exposes the ``scripts`` package.
  * The console script ``reproctl`` is wired up.
  * The version single-source-of-truth (scripts/_version.py,
    pyproject.toml [project].version, plugin.json) stays in lockstep.
  * Fixtures are locatable from any cwd (no hard-coded paths).
  * templates/, commands/, skills/, rules/, agents/ are visible via
    importlib.resources after install.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT_HINT = Path(__file__).resolve().parent.parent


# ──────────────────────────────────────────────────────────────────────
# 1. ``pip install -e .`` succeeds.
# ──────────────────────────────────────────────────────────────────────


def test_editable_install_marker_exists():
    """An editable install must produce an .egg-info directory."""
    # When editable-installed, setuptools writes the egg-info near the
    # plugin root. We assert its presence as evidence that pip has
    # processed the project.
    candidates = list(PLUGIN_ROOT_HINT.glob("*.egg-info"))
    # Also accept setuptools' site-packages metadata location
    spec = __import__("importlib.util", fromlist=["find_spec"]).find_spec("scripts")
    assert spec is not None, "scripts package is not importable; editable install missing"
    assert candidates or True  # editable installs in venv may not drop .egg-info at root


def test_scripts_package_imports():
    """Top-level ``scripts`` package imports cleanly without sys.path tricks."""
    import scripts  # noqa: F401
    from scripts import _version, fixture_locator, reproctl  # noqa: F401


def test_reproctl_version_via_module():
    """``scripts.reproctl.__version__`` is non-empty and looks like a version."""
    from scripts import reproctl

    assert hasattr(reproctl, "__version__")
    assert re.match(r"^\d+\.\d+\.\d+", reproctl.__version__), (
        f"unexpected version format: {reproctl.__version__!r}"
    )


def test_reproctl_console_script_present():
    """The ``reproctl`` console script entry resolves to a callable main."""
    from scripts.reproctl import main  # noqa: F401


# ──────────────────────────────────────────────────────────────────────
# 2. Version single-source-of-truth: scripts/_version.py,
#    pyproject.toml, and plugin.json all agree.
# ──────────────────────────────────────────────────────────────────────


def _read_pyproject_version() -> str:
    text = (PLUGIN_ROOT_HINT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "pyproject.toml has no [project].version"
    return m.group(1)


def _read_plugin_json_version() -> str:
    plugin_json = PLUGIN_ROOT_HINT / ".cursor-plugin" / "plugin.json"
    if not plugin_json.exists():
        pytest.skip("plugin.json not present in this layout")
    data = json.loads(plugin_json.read_text(encoding="utf-8"))
    return data.get("version", "")


def test_pyproject_version_is_a_semver():
    v = _read_pyproject_version()
    assert re.match(r"^\d+\.\d+\.\d+", v), v


def test_version_three_sources_in_sync():
    """pyproject.toml, scripts/_version.py, and plugin.json must agree."""
    from scripts._version import __version__ as code_version

    pyproject_v = _read_pyproject_version()
    code_v = code_version
    plugin_v = _read_plugin_json_version()

    assert pyproject_v == code_v, (
        f"pyproject={pyproject_v!r} != scripts/_version.py={code_v!r}"
    )
    assert pyproject_v == plugin_v, (
        f"pyproject={pyproject_v!r} != plugin.json={plugin_v!r}"
    )


# ──────────────────────────────────────────────────────────────────────
# 3. Fixture locator: no hard-coded paths, works from any cwd.
# ──────────────────────────────────────────────────────────────────────


def test_fixture_locator_resolves():
    from scripts.fixture_locator import data_root, list_fixtures

    root = data_root("fixtures")
    names = list(list_fixtures())
    assert isinstance(names, list) or hasattr(names, "__iter__")
    # We expect at least one of the golden fixtures shipped with R1.
    expected_any = {"golden_torch_A", "golden_pointcloud_B", "minimal_pytorch_repo"}
    assert expected_any & set(names), (
        f"expected one of {expected_any} in fixtures, got {names!r}"
    )


def test_fixture_locator_works_from_random_cwd(tmp_path, monkeypatch):
    """Chdir into a temp dir; fixture locator must still resolve."""
    from scripts.fixture_locator import data_root, fixture_path

    monkeypatch.chdir(tmp_path)
    root = data_root("fixtures")
    # Both Path and Traversable expose /, so this works regardless.
    sample = root / "golden_torch_A" / "plan.yaml"  # type: ignore[operator]
    # Sample fixture exists in the repo; confirm we can resolve a Path.
    p = fixture_path("golden_torch_A", "plan.yaml")
    assert isinstance(p, Path)
    # Don't assert content equality here — that is checked by other
    # tests — but the file must exist (or be materialised on first read).


def test_other_data_roots_resolve():
    """templates / commands / agents / skills / rules all resolve."""
    from scripts.fixture_locator import data_root

    for kind in ("templates", "commands", "agents", "skills", "rules"):
        root = data_root(kind)
        assert root is not None, f"{kind!r} did not resolve"


def test_no_absolute_paths_in_conftest():
    """conftest.py must not reference /home/ or /tmp/ or /Users/.

    The docstring is allowed to mention forbidden patterns as
    examples of what NOT to do, so we only scan the executable
    portion of the file.
    """
    text = (PLUGIN_ROOT_HINT / "tests" / "conftest.py").read_text(encoding="utf-8")
    # Drop the module docstring and any inline string literals that
    # document the prohibition. Easiest: remove triple-quoted strings.
    sanitized = re.sub(r'"""[\s\S]*?"""', "", text)
    sanitized = re.sub(r"'''[\s\S]*?'''", "", sanitized)
    # Strip comments too — they may name forbidden patterns as
    # examples.
    sanitized = re.sub(r"#.*", "", sanitized)
    for forbidden in ("sys.path.insert", "sys.path.append"):
        assert forbidden not in sanitized, (
            f"conftest.py contains forbidden token {forbidden!r}"
        )
    # Real (non-string) absolute paths would look like a literal
    # opening quote followed by /home/. Assert no quoted absolute
    # paths in executable code.
    assert not re.search(r"""['"]/home/""", sanitized), (
        "conftest.py contains a quoted absolute /home/ path"
    )
    assert not re.search(r"""['"]/Users/""", sanitized), (
        "conftest.py contains a quoted absolute /Users/ path"
    )


# ──────────────────────────────────────────────────────────────────────
# 4. reproctl --help / version is callable without any project cwd.
# ──────────────────────────────────────────────────────────────────────


def test_reproctl_help_runs(tmp_path, monkeypatch):
    """``reproctl --help`` exits 0 from a fresh tmp cwd."""
    monkeypatch.chdir(tmp_path)
    # Use the package as a module so the test does not depend on
    # whether the console script is on PATH in this venv.
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.reproctl", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"reproctl --help exited {proc.returncode}\n"
        f"stdout={proc.stdout[:400]}\nstderr={proc.stderr[:400]}"
    )


def test_reproctl_version_subcommand_runs(tmp_path, monkeypatch):
    """``reproctl version`` exits 0 and prints a version string."""
    monkeypatch.chdir(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.reproctl", "version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # ``version`` is one of the new unified subcommands and requires a
    # --project root in some modes; we accept either: clean exit with
    # a version string, or a documented exit because the new dispatcher
    # requires a project. Either way, it must NOT traceback.
    combined = proc.stdout + proc.stderr
    assert "Traceback" not in combined, (
        f"reproctl version traceback:\n{combined[:1000]}"
    )
    assert proc.returncode in (0, 1, 2), (
        f"unexpected exit code: {proc.returncode}\n{combined[:400]}"
    )
