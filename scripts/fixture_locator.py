"""Locator helpers for runtime data files shipped with the package.

R1 INVARIANT: tests and runtime code MUST NOT use absolute paths or
``Path(__file__).resolve().parents[N]`` to find fixtures/templates/
commands/skills/rules. Instead they call into the helpers here,
which use :mod:`importlib.resources` and locate files relative to
the installed package root.

Locators are deliberately thin: they return either a
:class:`importlib.resources.abc.Traversable` (zero-copy, works for
wheels and zip installs) or a :class:`pathlib.Path` (when the host
filesystem allows it, used by tests that need a real path).

Resolution order:

1. If the package is importable under the canonical names
   (``scripts.fixtures``, ``scripts.templates``, etc.), locate data
   relative to the installed ``scripts`` package.
2. Fall back to the legacy on-disk layout where ``fixtures/``,
   ``templates/`` etc. live as siblings of the ``scripts/``
   directory (the pre-R1 layout). This lets existing developer
   checkouts keep working while the wheel path is exercised by CI.
3. Finally, fall back to ``<plugin_root>/fixtures`` derived from
   ``__file__``-based introspection — but ONLY for development
   convenience, never as the primary lookup.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib import resources as _resources
from pathlib import Path
from typing import Union

TraversableOrPath = Union[_resources.abc.Traversable, Path]

# Canonical package-data anchors. Keep in sync with
# ``[tool.setuptools.package-data]`` in pyproject.toml.
_PACKAGE_ANCHORS = {
    "fixtures": "scripts.fixtures",
    "templates": "scripts.templates",
    "commands": "scripts.commands",
    "agents": "scripts.agents",
    "skills": "scripts.skills",
    "rules": "scripts.rules",
}


def data_root(kind: str) -> TraversableOrPath:
    """Return a Traversable or Path for the given data directory.

    ``kind`` must be one of: ``fixtures``, ``templates``, ``commands``,
    ``agents``, ``skills``, ``rules``.

    Resolution order:

      1. The installed ``scripts.<kind>`` package (wheel + editable).
      2. The on-disk sibling of the installed ``scripts`` package
         (development fallback).
      3. ``Path(__file__).resolve().parents[N]`` walk toward the
         repo root (legacy fallback).

    The returned object supports ``/`` (path-style joins) regardless
    of whether it is a Traversable or a Path.
    """
    if kind not in _PACKAGE_ANCHORS:
        raise ValueError(f"unknown data kind: {kind!r}")
    pkg = _PACKAGE_ANCHORS[kind]

    # 1. Importable package — works in editable install and wheel.
    try:
        anchor = _resources.files(pkg)
        if anchor is not None:
            return anchor
    except (ImportError, ModuleNotFoundError):
        pass

    # 2. Walk up to find scripts/ on the filesystem, then locate the
    # sibling data directory. This handles the case where the
    # package was installed from a checkout but the data dirs were
    # not packaged (older wheels).
    try:
        anchor_pkg = _resources.files("scripts")
    except (ImportError, ModuleNotFoundError):
        anchor_pkg = None

    if anchor_pkg is not None and hasattr(anchor_pkg, "_paths"):
        # Older API: traverse the on-disk sibling directly.
        for p in anchor_pkg._paths:  # type: ignore[attr-defined]
            sibling = Path(p).parent / kind
            if sibling.exists():
                return sibling

    # 3. Last-resort: walk up from this file to find ``scripts``'s
    # parent in the source tree. Used when running tests directly
    # from the source checkout without an install step.
    here = Path(__file__).resolve().parent
    for ancestor in (here, *here.parents):
        candidate = ancestor / kind
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"data directory {kind!r} not found via importlib.resources "
        f"and not present on disk near scripts/."
    )


def fixture_path(*parts: str) -> Path:
    """Return a real :class:`pathlib.Path` for a fixture file.

    Tests should use this when they need to read a fixture file
    with the standard library. The function materialises the
    Traversable into a filesystem path; callers should not assume
    the path is writable.
    """
    root = data_root("fixtures")
    joined = root
    for p in parts:
        joined = joined / p  # type: ignore[operator]

    # If we got a Traversable, convert. importlib.resources.files on
    # a regular install returns a MultiplexedPath or a real Path; in
    # either case ``as_file`` is the safe path to a usable Path.
    if isinstance(joined, Path):
        return joined

    # Traversable → Materialise via importlib.resources.as_file
    import tempfile

    # as_file returns a context manager but we want a stable path.
    # For read-only access, copy the resource to a tempdir that
    # lives for the rest of the process.
    cache_dir = Path(tempfile.gettempdir()) / "kestrel_repro_fixtures"
    cache_dir.mkdir(parents=True, exist_ok=True)
    rel = Path(*parts)
    target = cache_dir / rel
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with _resources.as_file(joined) as src:  # type: ignore[arg-type]
            target.write_bytes(src.read_bytes())
    return target


def list_fixtures() -> Iterable[str]:
    """Yield the names of all top-level fixture entries.

    Used by ``test_plugin_discovery`` to confirm fixtures actually
    travel with the wheel. Returns POSIX-style relative names.
    """
    root = data_root("fixtures")
    for entry in root.iterdir():  # type: ignore[attr-defined]
        yield entry.name  # type: ignore[union-attr]


__all__ = ["data_root", "fixture_path", "list_fixtures"]
