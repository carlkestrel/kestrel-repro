from __future__ import annotations

import time
import uuid
from typing import Any

from .state_store import StateStore


class ApprovalGate:
    """Persist approval requests and explicit decisions in the state store.
    
    NORA-style enhancements:
    - Human checkpoint support
    - Auto-approval for low-risk operations
    - Checkpoint-aware decision logic
    """

    def __init__(self, store, ttl_seconds: float = 86400):
        self.store = store
        self.ttl_seconds = ttl_seconds

    def request(self, task: dict, reason: str = "", checkpoint: str | None = None) -> str:
        """Request approval for a task.
        
        Args:
            task: Task dictionary
            reason: Reason for the approval request
            checkpoint: Optional human checkpoint name
        """
        existing = [approval for approval in self.store.pending_approvals()
                    if approval["task_id"] == task["id"]]
        if existing:
            return existing[0]["approval_id"]
        if task["status"] not in {"READY", "APPROVED"}:
            return ""
        approval_id = f"apr_{uuid.uuid4().hex[:16]}"
        expires_at = time.time() + self.ttl_seconds if self.ttl_seconds else None
        try:
            self.store.create_approval(approval_id, task["id"], expires_at)
        except ValueError:
            current = self.store.get_task(task["id"])
            if current is None or current["status"] == "WAITING_APPROVAL":
                pending = [a["approval_id"] for a in self.store.pending_approvals()
                           if a["task_id"] == task["id"]]
                return pending[0] if pending else ""
            raise
        if reason:
            self.store.record_event("APPROVAL_REASON", task["id"], {
                "approval_id": approval_id, "reason": reason
            })
        if checkpoint:
            self.store.record_event("HUMAN_CHECKPOINT", task["id"], {
                "checkpoint": checkpoint,
                "approval_id": approval_id,
            })
        return approval_id

    def approve(self, approval_id: str, reason: str = "") -> dict:
        return self.store.decide_approval(approval_id, "APPROVED", reason)

    def reject(self, approval_id: str, reason: str = "") -> dict:
        return self.store.decide_approval(approval_id, "REJECTED", reason)

    def cleanup_expired(self) -> list[str]:
        now = time.time()
        expired: list[str] = []
        for approval in self.store.pending_approvals():
            expires_at = approval.get("expires_at")
            if expires_at is not None and expires_at <= now:
                self.reject(approval["approval_id"], "approval expired")
                expired.append(approval["approval_id"])
        return expired

    def auto_approve_low_risk(self, task: dict) -> bool:
        """Auto-approve low-risk tasks if conditions are met.
        
        Returns True if the task was auto-approved, False otherwise.
        """
        gate = task.get("gate", "")
        low_risk_gates = {"read_only", "safe", "compute_metrics", "generate_report",
                         "mini_benchmark", "small_download"}
        
        if gate in low_risk_gates:
            # Auto-approve low-risk tasks
            approval_id = self.request(task, reason=f"Auto-approved low-risk gate: {gate}")
            if approval_id:
                self.approve(approval_id, "Auto-approved (AUTO_PROCEED or low-risk)")
                return True
        return False

    def get_checkpoints(self) -> list[dict[str, Any]]:
        """Get all human checkpoints from events."""
        events = self.store.events(limit=10000)
        checkpoints = []
        for event in events:
            if event.get("event_type") == "HUMAN_CHECKPOINT":
                checkpoints.append(event.get("payload", {}))
        return checkpoints
