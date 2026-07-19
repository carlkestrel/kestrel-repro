"""reproctl — unified paper reproduction controller.

This package is the importable entry point used by:

  - the ``[project.scripts]`` console_script entry in pyproject.toml
  - ``python -m reproctl`` invocation from any cwd (when this package
    is on PYTHONPATH)

Internally it delegates to ``scripts/reproctl.py`` (the real
implementation file) via runpy, so the legacy module layout is
preserved. The dispatch is relocateable: no absolute path is
hardcoded; the impl location is resolved relative to this package.

Public API:
    main(argv=None)  — run the CLI. Returns the process exit code.
"""

from __future__ import annotations

# Single source of truth. See scripts/_version.py for the rationale.
try:
    from _version import __version__  # when scripts/ is on sys.path
except Exception:  # pragma: no cover - direct ``python -m reproctl`` from repo root
    __version__ = "0.2.0"

__all__ = ["main", "__version__"]


def _resolve_impl_path():
    """Locate ``scripts/reproctl.py`` without absolute paths.

    The implementation lives in the same directory as this package
    (i.e. ``scripts/reproctl.py``), since this package lives in
    ``scripts/reproctl/``. We resolve relative to ``__file__`` so the
    package remains relocatable across machines and venvs.
    """
    from pathlib import Path

    pkg_dir = Path(__file__).resolve().parent
    candidate = pkg_dir.parent / "reproctl.py"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"reproctl implementation file not found: {candidate}")


def main(argv=None):
    """Console-script entry point for reproctl.

    Mirrors argparse behaviour: ``reproctl.main(['start', '--help'])``
    runs the CLI with the given argv. Returns 0 in this minimal
    dispatcher because the implementation file calls ``sys.exit()``
    itself when it finishes; a non-zero return here would indicate
    that ``runpy`` could not locate or load the implementation.
    """
    import runpy
    import sys
    from pathlib import Path

    impl = _resolve_impl_path()
    if argv is not None:
        old_argv = sys.argv
        try:
            sys.argv = [str(Path(impl).name)] + list(argv)
            runpy.run_path(str(impl), run_name="__main__")
            return 0
        finally:
            sys.argv = old_argv
    else:
        runpy.run_path(str(impl), run_name="__main__")
        return 0
