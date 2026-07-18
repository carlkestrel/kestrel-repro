"""Marker package — see ``scripts/commands/__init__.py`` for the
rationale. This package ships the ``fixtures/`` tree (small
Python, JSON, YAML files used by the regression and plugin tests)
as package data so the test suite can locate them via
``importlib.resources.files("scripts.fixtures")`` regardless of
the current working directory.
"""
__all__: list[str] = []