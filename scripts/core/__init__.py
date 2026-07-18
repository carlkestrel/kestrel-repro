"""R3-0 canonical core package.

This package holds the SINGLE canonical implementation of cross-cutting
infrastructure (state store, etc.). Both `scripts.startup` and
`scripts.orchestrator` re-export from here — see ADR-001.

No module under `scripts.core` may itself import from `scripts.startup`
or `scripts.orchestrator` (no circular dependencies).
"""
