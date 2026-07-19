"""Marker package — provides a stable import anchor for Cursor
plugin asset directories.

``scripts.commands`` ships the ``commands/*.md`` files as package
data so that
``importlib.resources.files("scripts.commands").joinpath("repro-start.md")``
works both from an editable install and a wheel install.

The module itself contains no runtime code; only a docstring is
allowed so that the namespace is not empty.
"""

__all__: list[str] = []
