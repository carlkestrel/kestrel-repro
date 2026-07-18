"""Tests for non_evidentiary waiver and expired-approval semantics.

R3R-4: P0-5 + P0-6 fixes:
- P0-5: non_evidentiary tasks must transition to WAITING_APPROVAL (not PASSED)
  after verification. A human must explicitly waive them.
- P0-6: expired approvals transition to REJECTED (not WAIVED), since the
  human never reviewed them in time.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

THIS = Path(__file__).resolve()
PLUGIN_ROOT = THIS.parents[1]
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from orchestrator import ApprovalGate, StateStore  # noqa: E402

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path):
    proj = tmp_path / "ne_wavier"
    proj.mkdir()
    (proj / ".repro").mkdir(parents=True, exist_ok=True)
    s = StateStore(proj)
    s.initialize_plan(
        {
            "plan_id": "ne-test",
            "mode": "strict",
            "tasks": [
                {
                    "id": "t_ne",
                    "name": "non-evidentiary task",
                    "gate": "audit",
                    "deps": [],
                    "command": "echo hello",
                    "timeout_min": 1,
                    "acceptance_tests": [],
                    "retry_policy": {"max_retries": 0},
                    "non_evidentiary": True,
                },
                {
                    "id": "t_ev",
                    "name": "evidentiary task",
                    "gate": "safe",
                    "deps": [],
                    "command": "echo world",
                    "timeout_min": 1,
                    "acceptance_tests": [{"type": "file_exists", "path": "README.md"}],
                    "retry_policy": {"max_retries": 0},
                    "non_evidentiary": False,
                },
            ],
            "mandatory_task_ids": ["t_ne", "t_ev"],
            "budgets": {"max_parallel_tasks": 1, "approval_wait_seconds": 2.0},
        },
        plan_path=str(proj / "plan.yaml"),
    )
    return proj, s


# ── P0-5: non_evidentiary → WAITING_APPROVAL ───────────────────────────────


def test_non_evidentiary_verifier_returns_needs_waiver_marker(store):
    """Verifier returns (True, '_NEEDS_WAIVER_') for non_evidentiary tasks."""
    proj, s = store
    from orchestrator import ProcessManager, Verifier

    v = Verifier(proj, s, ProcessManager())
    task = s.get_task("t_ne")
    assert task["non_evidentiary"] is True

    ok, detail = v.verify(task)
    assert ok is True
    assert detail == "_NEEDS_WAIVER_"


def test_non_evidentiary_verifier_does_not_record_pass(store):
    """VERIFICATION_PASS is NOT emitted for non_evidentiary tasks."""
    proj, s = store
    from orchestrator import ProcessManager, Verifier

    v = Verifier(proj, s, ProcessManager())
    task = s.get_task("t_ne")
    seq_before = s.events()[-1]["seq"] if s.events() else 0

    v.verify(task)

    events_after = list(s.events(after_seq=seq_before))
    event_types = {e["event_type"] for e in events_after}
    assert "VERIFICATION_PASS" not in event_types
    assert "VERIFICATION_BYPASS" in event_types


def test_controller_transitions_ne_task_to_waiting_approval(store):
    """Controller._run_verifications transitions non_evidentiary → WAITING_APPROVAL.

    Simulates the exact logic in Controller._run_verifications when the verifier
    returns '_NEEDS_WAIVER_'.
    """
    proj, s = store

    # Scheduler promotes PENDING → READY
    s.transition("t_ne", "READY", expected="PENDING")

    # Controller would claim → launch → poll → VERIFYING
    # READY → RUNNING → VERIFYING (using transition() wrapper)
    s.transition("t_ne", "RUNNING", expected="READY", fields={"pid": 12345})
    s.transition("t_ne", "VERIFYING", expected="RUNNING", fields={"pid": None})

    # Controller._run_verifications sees _NEEDS_WAIVER_ and transitions to WAITING_APPROVAL.
    # Note: use transition_task() directly (not the wrapper transition()) since
    # transition_task() uses expect_from= whereas transition() uses expected=.
    s.transition_task(
        "t_ne",
        "WAITING_APPROVAL",
        expect_from="VERIFYING",
        fields={"finished_at": "2026-01-01T00:00:00Z"},
        event_type="WAIVER_REQUIRED",
    )

    refreshed = s.get_task("t_ne")
    assert refreshed["status"] == "WAITING_APPROVAL"

    # Verify WAIVER_REQUIRED event was emitted
    events = s.events(limit=100)
    waiver_events = [e for e in events if e["event_type"] == "WAIVER_REQUIRED"]
    assert len(waiver_events) == 1
    assert waiver_events[0]["task_id"] == "t_ne"


def test_waive_non_evidentiary_task_puts_task_in_waived_state(store):
    """Explicit waiver via ApprovalGate.waive() transitions task to WAIVED."""
    proj, s = store
    gate = ApprovalGate(s, ttl_seconds=3600)

    # Build up: PENDING → READY → create_approval → WAITING_APPROVAL
    s.transition("t_ne", "READY", expected="PENDING")
    task = s.get_task("t_ne")
    assert task["status"] == "READY"

    # gate.request() works for READY tasks and creates PENDING approval + transitions
    approval_id = gate.request(task, reason="human-reviewed")
    assert approval_id, "gate.request should return a non-empty approval_id"

    # The task should now be in WAITING_APPROVAL
    refreshed = s.get_task("t_ne")
    assert refreshed["status"] == "WAITING_APPROVAL"

    # Waive it
    gate.waive(approval_id, "human accepts non-evidentiary outcome")

    final_state = s.get_task("t_ne")
    assert final_state["status"] == "WAIVED"


def test_reject_approval_transitions_to_rejected(store):
    """Explicit rejection transitions task to REJECTED."""
    proj, s = store
    gate = ApprovalGate(s, ttl_seconds=3600)

    s.transition("t_ne", "READY", expected="PENDING")
    task = s.get_task("t_ne")
    approval_id = gate.request(task)
    assert approval_id

    gate.reject(approval_id, "not satisfied")

    refreshed = s.get_task("t_ne")
    assert refreshed["status"] == "REJECTED"


# ── P0-6: expired → REJECTED (not WAIVED) ─────────────────────────────────


def test_expired_approval_goes_to_rejected_not_waived(store):
    """cleanup_expired transitions expired approvals to REJECTED, not WAIVED."""
    proj, s = store
    # ttl_seconds=0 is falsy → expires_at=None (never expires).
    # Use -1 so expires_at = now - 1 (already expired).
    gate = ApprovalGate(s, ttl_seconds=-1)

    # Build up: PENDING → READY → create approval
    s.transition("t_ne", "READY", expected="PENDING")
    task = s.get_task("t_ne")  # re-fetch so status is current

    approval_id = gate.request(task, reason="needs waiver")
    assert approval_id, "gate.request should return a non-empty approval_id"

    expired = gate.cleanup_expired()
    assert approval_id in expired

    refreshed = s.get_task("t_ne")
    assert refreshed["status"] == "REJECTED", (
        f"Expected REJECTED for expired approval, got {refreshed['status']}"
    )


def test_expired_approval_not_waived(store):
    """Expired approvals must NOT end up in WAIVED state."""
    proj, s = store
    gate = ApprovalGate(s, ttl_seconds=-1)  # already expired

    s.transition("t_ne", "READY", expected="PENDING")
    task = s.get_task("t_ne")
    approval_id = gate.request(task)
    assert approval_id

    gate.cleanup_expired()

    refreshed = s.get_task("t_ne")
    assert refreshed["status"] != "WAIVED"


def test_expired_approval_emits_rejected_event_not_waived(store):
    """Expired approvals emit APPROVAL_REJECTED event (not APPROVAL_WAIVED)."""
    proj, s = store
    gate = ApprovalGate(s, ttl_seconds=-1)  # already expired

    s.transition("t_ne", "READY", expected="PENDING")
    task = s.get_task("t_ne")
    seq_before = s.events()[-1]["seq"] if s.events() else 0

    approval_id = gate.request(task)
    assert approval_id
    gate.cleanup_expired()

    events_after = list(s.events(after_seq=seq_before))
    event_types = {e["event_type"] for e in events_after}
    assert "APPROVAL_REJECTED" in event_types
    assert "APPROVAL_WAIVED" not in event_types


def test_decide_approval_accepts_rejected(store):
    """decide_approval accepts REJECTED as a valid decision."""
    proj, s = store
    gate = ApprovalGate(s)

    s.transition("t_ne", "READY", expected="PENDING")
    task = s.get_task("t_ne")
    approval_id = gate.request(task)
    assert approval_id

    gate.reject(approval_id, "human said no")

    refreshed = s.get_task("t_ne")
    assert refreshed["status"] == "REJECTED"
