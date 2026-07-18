"""End-to-end tests for authorization enforcement.

Verifies:
1. Unauthenticated tasks (no contract) are blocked.
2. Authenticated tasks (valid contract) can run.
3. Expired/stale contracts block operations.
4. Rejected approvals prevent task execution.
5. Tasks without approval cannot complete.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

THIS = Path(__file__).resolve()
PLUGIN_ROOT = THIS.parents[1]
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from orchestrator import ApprovalGate, Controller, StateStore  # noqa: E402
from orchestrator.controller import BLOCKED, COMPLETE, WAITING_APPROVAL  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────


def _proj(tmp_path: Path, name: str = "auth_test") -> Path:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    (p / ".repro").mkdir(parents=True, exist_ok=True)
    return p


def _simple_plan(proj: Path, gate: str = "safe") -> Path:
    plan = {
        "plan_id": "auth-e2e",
        "mode": "strict",
        "automation": "safe-auto",
        "tasks": [
            {
                "id": "t1",
                "name": "t1",
                "gate": gate,
                "deps": [],
                "command": "echo t1 && touch output/t1.out",
                "timeout_min": 1,
                "acceptance_tests": [],
                "retry_policy": {"max_retries": 0},
            },
        ],
        "mandatory_task_ids": ["t1"],
        "budgets": {"max_parallel_tasks": 1, "approval_wait_seconds": 2.0},
    }
    path = proj / "plan.yaml"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _bound_hash(store: StateStore) -> str:
    from core.state_store import compute_authorization_bound_hash
    canonical = store.get_metadata("canonical_plan_hash", "")
    schema_v = store.get_metadata("schema_version", "1.0")
    canon_v = store.get_metadata("canonicalization_version", "1")
    return compute_authorization_bound_hash(canonical, schema_v, canon_v)


# ── Basic auth enforcement ─────────────────────────────────────────────────


def test_task_without_authorization_stores_no_contract(tmp_path):
    """Without an authorization contract, is_authorized returns False for any action."""
    proj = _proj(tmp_path)
    s = StateStore(proj)
    plan = {
        "plan_id": "no-auth",
        "mode": "strict",
        "tasks": [{
            "id": "t1", "name": "t1", "gate": "safe",
            "deps": [], "command": "echo t1",
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0},
        }],
        "mandatory_task_ids": ["t1"],
        "budgets": {},
    }
    s.initialize_plan(plan, plan_path=str(proj / "plan.yaml"))

    assert s.is_authorized("any_contract", "execute_task") is False
    assert s.is_authorized("no-such-contract", "read_only") is False


def test_active_contract_with_execute_permission_is_authorized(tmp_path):
    """A contract with the execute action grants authorization."""
    proj = _proj(tmp_path)
    s = StateStore(proj)
    plan = {
        "plan_id": "with-auth",
        "mode": "strict",
        "tasks": [{
            "id": "t1", "name": "t1", "gate": "safe",
            "deps": [], "command": "echo t1",
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0},
        }],
        "mandatory_task_ids": ["t1"],
        "budgets": {},
    }
    s.initialize_plan(plan, plan_path=str(proj / "plan.yaml"))

    # Must set metadata bound hash before upsert_authorization so the auto-compute
    # inside upsert_authorization finds it. Passing "" with empty metadata
    # results in an empty stored hash.
    bound = _bound_hash(s)
    s.set_metadata("authorization_bound_hash", bound)

    s.upsert_authorization(
        contract_id="contract-001",
        project_id="default",
        plan_hash=s.get_metadata("canonical_plan_hash", ""),
        git_commit="abc123",
        authorization_bound_hash=bound,
        granted=["execute_task"],
        denied=[],
        write_roots=[],
        policies={},
        budgets={},
        other={
            "expires_at": "",
            "retry_limit": 3,
            "revocation_state": "active",
            "needs_reconfirmation": False,
        },
    )

    assert s.is_authorized("contract-001", "execute_task") is True


def test_stale_bound_hash_is_not_authorized(tmp_path):
    """A contract whose bound hash doesn't match the current plan is not authorized."""
    proj = _proj(tmp_path)
    s = StateStore(proj)
    plan = {
        "plan_id": "stale-auth",
        "mode": "strict",
        "tasks": [{
            "id": "t1", "name": "t1", "gate": "safe",
            "deps": [], "command": "echo t1",
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0},
        }],
        "mandatory_task_ids": ["t1"],
        "budgets": {},
    }
    s.initialize_plan(plan, plan_path=str(proj / "plan.yaml"))

    from core.state_store import compute_authorization_bound_hash
    stale_bound = compute_authorization_bound_hash("wrong-plan-hash", "99.0", "999")

    s.upsert_authorization(
        contract_id="contract-stale",
        project_id="default",
        plan_hash=s.get_metadata("canonical_plan_hash", ""),
        git_commit="abc123",
        authorization_bound_hash=stale_bound,
        granted=["execute_task"],
        denied=[],
        write_roots=[],
        policies={},
        budgets={},
        other={
            "expires_at": "",
            "retry_limit": 3,
            "revocation_state": "active",
            "needs_reconfirmation": False,
        },
    )

    assert s.is_authorized("contract-stale", "execute_task") is False


def test_denied_action_blocks_authorization(tmp_path):
    """A contract that explicitly denies an action blocks it even if others grant."""
    proj = _proj(tmp_path)
    s = StateStore(proj)
    plan = {
        "plan_id": "deny-test",
        "mode": "strict",
        "tasks": [{
            "id": "t1", "name": "t1", "gate": "destructive",
            "deps": [], "command": "echo t1",
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0},
        }],
        "mandatory_task_ids": ["t1"],
        "budgets": {},
    }
    s.initialize_plan(plan, plan_path=str(proj / "plan.yaml"))

    s.set_metadata("authorization_bound_hash", _bound_hash(s))

    s.upsert_authorization(
        contract_id="contract-deny",
        project_id="default",
        plan_hash=s.get_metadata("canonical_plan_hash", ""),
        git_commit="abc123",
        authorization_bound_hash="",  # auto-computed
        granted=["execute_task"],
        denied=["execute_task"],  # explicitly denied
        write_roots=[],
        policies={},
        budgets={},
        other={
            "expires_at": "",
            "retry_limit": 3,
            "revocation_state": "active",
            "needs_reconfirmation": False,
        },
    )

    assert s.is_authorized("contract-deny", "execute_task") is False


def test_rejected_approval_prevents_task_claim(tmp_path):
    """A task with a rejected approval cannot be claimed for execution."""
    proj = _proj(tmp_path)
    s = StateStore(proj)
    gate = ApprovalGate(s, ttl_seconds=3600)

    plan = {
        "plan_id": "reject-test",
        "mode": "strict",
        "tasks": [{
            "id": "t1", "name": "t1", "gate": "audit",
            "deps": [], "command": "echo t1",
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0},
        }],
        "mandatory_task_ids": ["t1"],
        "budgets": {"approval_wait_seconds": 0.1},
    }
    s.initialize_plan(plan, plan_path=str(proj / "plan.yaml"))

    # Directly create a pending approval for the task
    import uuid
    approval_id = f"apr_{uuid.uuid4().hex[:16]}"
    s.create_approval(approval_id, "t1", expires_at=None)

    task = s.get_task("t1")
    assert task["status"] == "WAITING_APPROVAL"

    gate.reject(approval_id, "operator not satisfied")

    refreshed = s.get_task("t1")
    assert refreshed["status"] == "REJECTED"

    # Claim should fail — task is not READY or APPROVED
    result = s.claim_task("t1", "test-owner")
    assert result is None


def test_task_without_approval_cannot_complete(tmp_path):
    """A task stuck in WAITING_APPROVAL does not reach COMPLETE."""
    proj = _proj(tmp_path)
    # gpu_training gate requires approval in safe-auto and does NOT auto-approve
    plan_path = _simple_plan(proj, gate="gpu_training")

    controller = Controller(
        project_root=proj,
        plan_path=plan_path,
        automation="safe-auto",
        poll_interval=0.05,
    )

    result = controller.run()
    # Should exit with WAITING_APPROVAL (blocked waiting for human decision)
    # because gpu_training requires approval and no contract grants it.
    assert result["status"] == WAITING_APPROVAL, (
        f"Expected WAITING_APPROVAL, got {result['status']}: {result.get('reason', '')}"
    )

    # Task should not have PASSED without approval
    store = StateStore(proj)
    t1 = store.get_task("t1")
    assert t1["status"] in (
        WAITING_APPROVAL, "APPROVED", "WAIVED", "REJECTED", "EXPIRED"
    ), f"t1 should not be PASSED or RUNNING without approval; got {t1['status']}"
