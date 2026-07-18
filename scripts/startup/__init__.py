"""Unified startup system for dl-paper-repro.

Subcommands: start | doctor | status | resume | stop | verify | version.

Exposes the BOOTSTRAP → DISCOVER → PREFLIGHT → STATE_CHECK → LOCK →
PLAN_VALIDATE → READY → EXECUTE_NEXT state machine that the user spec
requires. All public helpers are pure-Python and side-effect-light so
the unit tests can exercise them directly.
"""

# Single source of truth. See scripts/_version.py for the rationale.
from _version import __version__  # noqa: F401  (re-exported)

__all__ = [
    "cli",
    "config",
    "doctor",
    "lock",
    "log_setup",
    "plan_validate",
    "recovery",
    "secrets_redactor",
    "state_machine",
    "stop",
    # R2 modules — imported lazily so tests can import them individually
    # without triggering startup-level circular dependencies.
]
