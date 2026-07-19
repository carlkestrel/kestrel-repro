"""Single source of truth for the kestrel-repro plugin version.

This module is intentionally trivial: it must import cleanly without
any non-stdlib dependency, and must be loadable from any of the
following contexts:

  * the editable install (developer mode, plugin source on disk)
  * the wheel install (installed into site-packages)
  * the legacy CLI file (``scripts/reproctl.py``) which adds
    ``scripts/`` to ``sys.path`` before doing ``from _version import
    __version__``
  * unit tests under ``tests/`` (they add the plugin root to
    ``sys.path`` only because of the package layout below; the
    helper at the bottom of this file detects the install metadata
    via ``importlib.metadata`` when available and falls back to the
    hard-coded default).

The hard-coded value MUST stay in lockstep with
``[project].version`` in ``pyproject.toml`` and
``.cursor-plugin/plugin.json``'s ``version`` field. The CI suite
(asserted by ``tests/test_plugin_discovery.py`` and the new
``tests/test_version_sync.py``) enforces this synchronisation at
test time.

Why not just use ``importlib.metadata.version("kestrel-repro")``?
The plugin can also be run directly from the source tree without a
build step (for example, while iterating in the editor). Falling
back to the literal keeps the file useful in that mode.
"""

from __future__ import annotations

__version__ = "0.2.0"

# Lazy-resolved at import-time of the package, not at module import.
# See the helper below.
__all__ = ["__version__", "get_version"]


def get_version() -> str:
    """Return the canonical version string.

    Prefers the installed distribution metadata when available
    (this is the source of truth for a wheel install). Falls back
    to the hard-coded ``__version__`` when the plugin is being run
    directly from the source tree.
    """
    try:
        from importlib import metadata as _md

        return _md.version("kestrel-repro")
    except Exception:
        return __version__
