"""Continuous auto-execution controller package."""

from .approval_gate import ApprovalGate
from .controller import (
    BLOCKED,
    COMPLETE,
    PAUSED,
    STOPPED,
    WAITING_APPROVAL,
    Controller,
)
from .event_journal import EventJournal
from .policy_engine import (
    AUTO_EXECUTE,
    REJECT,
    REQUIRE_APPROVAL,
    PolicyEngine,
)
from .process_manager import ProcessManager
from .recovery import RecoveryManager
from .scheduler import CycleDependencyError, Scheduler
from .state_store import StateStore
from .task_executor import TaskExecutor
from .verifier import Verifier
from .watchdog import Watchdog

__all__ = [
    "ApprovalGate",
    "BLOCKED",
    "COMPLETE",
    "Controller",
    "EventJournal",
    "PAUSED",
    "PolicyEngine",
    "ProcessManager",
    "REJECT",
    "RecoveryManager",
    "REQUIRE_APPROVAL",
    "AUTO_EXECUTE",
    "Scheduler",
    "StateStore",
    "STOPPED",
    "TaskExecutor",
    "Verifier",
    "WAITING_APPROVAL",
    "Watchdog",
    "CycleDependencyError",
]
