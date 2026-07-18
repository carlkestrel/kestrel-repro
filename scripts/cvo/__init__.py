"""CVO — Checkpointed Validation Orchestrator for dl-paper-repro."""
from __future__ import annotations

__version__ = "0.1.0"

from .nodes import (
    ALL_NODES,
    NODE_MAP,
    STAGE_LABELS,
    STAGE_NODES,
    ValidationNode,
    get_next_ready,
    get_node,
    get_stage,
)
from .runner import CVORunner
from .state import CVOStateStore
from .val_000 import run as val_000_run
from .val_010 import run as val_010_run

__all__ = [
    "CVORunner",
    "CVOStateStore",
    "ValidationNode",
    "get_node",
    "get_next_ready",
    "get_stage",
    "NODE_MAP",
    "STAGE_LABELS",
    "STAGE_NODES",
    "ALL_NODES",
    "val_000_run",
    "val_010_run",
    "__version__",
]
