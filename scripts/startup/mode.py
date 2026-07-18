"""R2 mode model: three-dimensional research purpose × execution track × automation.

This module provides:
  * Canonical three-field mode representation.
  * Legacy-mode migration table (R2 §3).
  * Validation helpers for mode combinations.
  * Documentation of all allowed values.

Usage::

    from scripts.startup.mode import parse_mode, NEEDS_MODE_REVIEW
    result = parse_mode("strict_repro")   # returns ModeTriple or NEEDS_MODE_REVIEW
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ─── Value sets ────────────────────────────────────────────────────────

ResearchPurpose = Literal["audit", "reproduce", "extend", "takeover"]
ExecutionTrack = Literal["smoke", "fast", "strict", "statistical"]
AutomationLevel = Literal["manual", "gated-autopilot"]

RESEARCH_PURPOSE: set[str] = {"audit", "reproduce", "extend", "takeover"}
EXECUTION_TRACK: set[str] = {"smoke", "fast", "strict", "statistical"}
AUTOMATION_LEVEL: set[str] = {"manual", "gated-autopilot"}

# Sentinel for ambiguous/unrecognised legacy modes
NEEDS_MODE_REVIEW = "__NEEDS_MODE_REVIEW__"


@dataclass(frozen=True, slots=True)
class ModeTriple:
    """Canonical three-dimensional mode representation."""
    research_purpose: str
    execution_track: str
    automation_level: str

    def __str__(self) -> str:
        return (
            f"purpose={self.research_purpose} "
            f"track={self.execution_track} "
            f"automation={self.automation_level}"
        )

    def to_legacy_string(self) -> str:
        """Return a human-readable legacy-style mode string."""
        return f"{self.research_purpose}_{self.execution_track}_{self.automation_level}"

    def is_strict(self) -> bool:
        return self.execution_track == "strict"

    def is_gated(self) -> bool:
        return self.automation_level == "gated-autopilot"

    def is_smoke_only(self) -> bool:
        return self.execution_track == "smoke"


# ─── Legacy migration table ────────────────────────────────────────────

# Keys = canonicalised legacy mode strings (lowercase, stripped)
# Values = ModeTriple or NEEDS_MODE_REVIEW
_LEGACY_MAP: dict[str, ModeTriple | str] = {
    # ── strict_repro variants ──────────────────────────────────────────
    "strict_repro":        ModeTriple("reproduce", "strict",  "gated-autopilot"),
    "strict_repro_manual": ModeTriple("reproduce", "strict",  "manual"),
    # ── optimized / fast variants ──────────────────────────────────────
    "optimized_repro_safe": ModeTriple("reproduce", "fast",   "gated-autopilot"),
    "experimental_fast":    ModeTriple("reproduce", "fast",   "gated-autopilot"),
    "optimized":           ModeTriple("reproduce", "fast",   "manual"),
    "optimized_manual":    ModeTriple("reproduce", "fast",   "manual"),
    # ── strict (purpose-agnostic) ────────────────────────────────────
    "strict":              ModeTriple("reproduce", "strict",  "manual"),
    "strict_gated":       ModeTriple("reproduce", "strict",  "gated-autopilot"),
    # ── reproduce ─────────────────────────────────────────────────────
    "reproduce":           ModeTriple("reproduce", "strict",  "gated-autopilot"),
    "reproduce_strict_gated":  ModeTriple("reproduce", "strict", "gated-autopilot"),
    "reproduce_strict_manual": ModeTriple("reproduce", "strict", "manual"),
    "reproduce_fast_gated":    ModeTriple("reproduce", "fast",   "gated-autopilot"),
    # ── audit ─────────────────────────────────────────────────────────
    "diagnose":            ModeTriple("audit",     "strict",  "gated-autopilot"),
    "audit_smoke":        ModeTriple("audit",     "smoke",   "gated-autopilot"),
    "audit_fast":         ModeTriple("audit",     "fast",    "gated-autopilot"),
    "audit_manual":       ModeTriple("audit",     "strict",  "manual"),
    # ── extend ────────────────────────────────────────────────────────
    "evolve":             ModeTriple("extend",    "fast",    "gated-autopilot"),
    "extend":             ModeTriple("extend",    "fast",    "gated-autopilot"),
    "extend_strict":     ModeTriple("extend",    "strict",  "gated-autopilot"),
    # ── takeover ─────────────────────────────────────────────────────
    "takeover":           ModeTriple("takeover",  "strict",  "gated-autopilot"),
    "takeover_fast":     ModeTriple("takeover",  "fast",    "gated-autopilot"),
}


def _canonicalise(key: str) -> str:
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def parse_mode(mode_raw: str | None) -> ModeTriple | str:
    """Parse a mode string into a canonical ModeTriple.

    Arguments:
      mode_raw: a legacy single-string mode (e.g. "strict_repro") or
                a three-field dict with keys ``research_purpose``,
                ``execution_track``, ``automation_level``.

    Returns:
      * A ``ModeTriple`` when the mode is valid.
      * ``NEEDS_MODE_REVIEW`` when the legacy mode is ambiguous or
        unrecognised and requires human review.

    R2 acceptance:
      #6 — unambiguous legacy modes auto-migrate
      #7 — ambiguous legacy modes → NEEDS_MODE_REVIEW
    """
    if mode_raw is None:
        return NEEDS_MODE_REVIEW

    if isinstance(mode_raw, dict):
        purpose = mode_raw.get("research_purpose", "")
        track = mode_raw.get("execution_track", "")
        automation = mode_raw.get("automation_level", "")
        if (purpose in RESEARCH_PURPOSE
                and track in EXECUTION_TRACK
                and automation in AUTOMATION_LEVEL):
            return ModeTriple(purpose, track, automation)
        return NEEDS_MODE_REVIEW

    key = _canonicalise(str(mode_raw))

    # Exact match in legacy table
    if key in _LEGACY_MAP:
        result = _LEGACY_MAP[key]
        return result  # type: ignore[return-value]

    # In legacy string format, a single research purpose or execution track
    # is AMBIGUOUS — the user must specify all three fields.
    if key in RESEARCH_PURPOSE:
        return NEEDS_MODE_REVIEW
    if key in EXECUTION_TRACK:
        return NEEDS_MODE_REVIEW
    if key in AUTOMATION_LEVEL:
        return NEEDS_MODE_REVIEW

    # Unknown string
    return NEEDS_MODE_REVIEW


def is_needs_review(result: ModeTriple | str) -> bool:
    return result is NEEDS_MODE_REVIEW


def describe_mode(mode_raw: str | None) -> str:
    """Return a human-readable description of the parsed mode."""
    result = parse_mode(mode_raw)
    if result is NEEDS_MODE_REVIEW:
        return (
            f"Mode {mode_raw!r} is ambiguous or unrecognised. "
            "Please specify three fields explicitly: "
            "research_purpose (audit/reproduce/extend/takeover), "
            "execution_track (smoke/fast/strict/statistical), "
            "automation_level (manual/gated-autopilot)."
        )
    assert isinstance(result, ModeTriple)
    return str(result)


__all__ = [
    "ModeTriple", "NEEDS_MODE_REVIEW",
    "ResearchPurpose", "ExecutionTrack", "AutomationLevel",
    "RESEARCH_PURPOSE", "EXECUTION_TRACK", "AUTOMATION_LEVEL",
    "parse_mode", "is_needs_review", "describe_mode",
]
