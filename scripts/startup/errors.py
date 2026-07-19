"""Startup error codes — single source of truth for error codes that the
CLI surfaces to callers, CI, and the human operator.

These are referenced by:
  * ``scripts.startup.migration`` (BLOCKED_STATE_CONFLICT)
  * ``scripts.core.state_store`` (single-state-authority self-check)
  * ``scripts.startup.cli`` (machine-readable error codes)
"""

from __future__ import annotations

from typing import Any


class StartupError(Exception):
    """Raised when a startup-time invariant is violated.

    Attributes:
        code: short machine-readable error code (e.g. ``BLOCKED_STATE_CONFLICT``).
        message: human-readable explanation.
        ctx: optional structured context (paths, IDs, counts).
    """

    code: str
    message: str
    ctx: dict[str, Any]

    def __init__(self, *, code: str, message: str, ctx: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.ctx = ctx or {}
        super().__init__(f"[{code}] {message}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "ctx": self.ctx}


# Error codes that callers may branch on.
BLOCKED_STATE_CONFLICT = "BLOCKED_STATE_CONFLICT"
BLOCKED_PLAN_INVALID = "BLOCKED_PLAN_INVALID"
BLOCKED_AUTH_REQUIRED = "BLOCKED_AUTH_REQUIRED"
BLOCKED_LEGACY_UNVERIFIED = "BLOCKED_LEGACY_UNVERIFIED"
BLOCKED_MIGRATION_FAILED = "BLOCKED_MIGRATION_FAILED"
