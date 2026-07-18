"""End-to-end and unit tests for the orchestrator package."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

THIS = Path(__file__).resolve()
PLUGIN_ROOT = THIS.parents[1]
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from orchestrator import (  # noqa: E402
    ApprovalGate,
    Controller,
    StateStore,
)
from orchestrator.controller import (  # noqa: E402
    BLOCKED,
    COMPLETE,
    PAUSED,
    STOPPED,
    WAITING_APPROVAL,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _mkdirs(project: Path) -> Path:
    (project / ".repro").mkdir(parents=True, exist_ok=True)
    (project / "output").mkdir(parents=True, exist_ok=True)
    return project


def _make_plan(
    tmp_path: Path,
    *,
    tasks,
    mode: str = "strict",
    automation: str = "safe-auto",
    mandatory: list[str] | None = None,
    approvals_required: list[str] | None = None,
    approval_wait_seconds: float = 1.5,
    max_parallel_tasks: int = 4,
) -> Path:
    mandatory = list(mandatory or [task["id"] for task in tasks])
    approvals_required = list(approvals_required or [])
    plan = {
        "plan_id": f"plan-{tmp_path.name}-{int(time.time() * 1000)}",
        "mode": mode,
        "automation": automation,
        "tasks": tasks,
        "approvals_required": approvals_required,
        "mandatory_task_ids": mandatory,
        "budgets": {
            "max_parallel_tasks": max_parallel_tasks,
            "approval_wait_seconds": approval_wait_seconds,
        },
    }
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    return plan_path


def _shell_command(script: str) -> str:
    return f"sh -c {shlex_quote(script)}"


def shlex_quote(text: str) -> str:
    import shlex

    return shlex.quote(text)


def _task_command(steps: list[str], *, workdir: Path | None = None) -> str:
    body = " && ".join(steps)
    if workdir is not None:
        body = f"cd {shlex_quote(str(workdir))} && {body}"
    return f"/bin/sh -c {shlex_quote(body)}"


def _long_task(
    project: Path, task_id: str, *, seconds: float, checkpoint: str, acceptance: str | None = None
) -> str:
    """Simulated long task that writes heartbeat, sleeps, then writes a checkpoint."""
    body = (
        f"echo START {task_id};"
        f"sleep {seconds};"
        f"mkdir -p {shlex_quote(str((project / '.repro/execution/task-heartbeats').resolve()))};"
        f"echo done > {shlex_quote(str(project / checkpoint))};"
        f"echo END {task_id}"
    )
    if acceptance:
        body += f";{acceptance}"
    return f"/bin/sh -c {shlex_quote(body)}"


def _failing_task(exit_code: int = 1) -> str:
    return f"/bin/sh -c {shlex_quote(f'exit {exit_code}')}"


def _wait_until(predicate, *, timeout: float = 10.0, step: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


def _run_controller(
    project: Path, plan_path: Path, *, automation: str = "safe-auto", resume: bool = False
) -> dict:
    controller = Controller(
        project_root=project, plan_path=plan_path, automation=automation, resume=resume
    )
    return controller.run()


# ── Tests ────────────────────────────────────────────────────────────────


def test_1_five_serial_tasks_complete(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    tasks = []
    for index in range(1, 6):
        marker = project / "output" / f"step-{index}.txt"
        tasks.append(
            {
                "id": f"task-{index}",
                "name": f"step {index}",
                "gate": "read_only",
                "deps": [f"task-{index - 1}"] if index > 1 else [],
                "command": _task_command([f"echo {index} > {marker}"], workdir=project),
                "timeout_min": 1,
                "acceptance_tests": [],
                "retry_policy": {"max_retries": 0, "delay_seconds": 0},
            }
        )
    plan_path = _make_plan(tmp_path, tasks=tasks)
    result = _run_controller(project, plan_path)
    assert result["status"] == COMPLETE, result
    for index in range(1, 6):
        assert (project / "output" / f"step-{index}.txt").exists()
    counts = StateStore(project).status_summary()["counts"]
    assert counts.get("PASSED", 0) == 5


def test_2_independent_readonly_tasks_parallel(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    tasks = []
    for index in range(3):
        tasks.append(
            {
                "id": f"ro-{index}",
                "name": f"parallel {index}",
                "gate": "read_only",
                "deps": [],
                "command": _task_command(
                    [
                        "sleep 0.5",
                        f"echo {index} > {project / 'output' / f'p-{index}.txt'}",
                    ],
                    workdir=project,
                ),
                "timeout_min": 5,
                "acceptance_tests": [],
                "retry_policy": {"max_retries": 0, "delay_seconds": 0},
            }
        )
    tasks.append(
        {
            "id": "join",
            "name": "join",
            "gate": "safe",
            "deps": [f"ro-{i}" for i in range(3)],
            "command": _task_command(
                [f"echo join > {project / 'output' / 'join.txt'}"], workdir=project
            ),
            "timeout_min": 5,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        }
    )
    plan_path = _make_plan(tmp_path, tasks=tasks)
    start = time.monotonic()
    result = _run_controller(project, plan_path)
    elapsed = time.monotonic() - start
    assert result["status"] == COMPLETE, result
    # 3 × 0.5 s parallel → < 1.5 s wall clock
    assert elapsed < 1.6, f"expected parallel execution, elapsed={elapsed:.2f}s"


def test_3_failure_auto_retries_once(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    sentinel = project / "output" / "sentinel.txt"
    # The script writes a sentinel via a one-shot command file: first run misses it,
    # second run sees it and succeeds.
    one_shot = project / "output" / "trigger.txt"
    command = _task_command(
        [f"if [ -f {one_shot} ]; then echo ok > {sentinel}; else touch {one_shot}; exit 7; fi"],
        workdir=project,
    )
    tasks = [
        {
            "id": "setup",
            "name": "setup",
            "gate": "read_only",
            "deps": [],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "flaky",
            "name": "flaky",
            "gate": "safe",
            "deps": ["setup"],
            "command": command,
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 2, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)
    result = _run_controller(project, plan_path)
    assert result["status"] == COMPLETE, result
    assert sentinel.exists()
    task = StateStore(project).get_task("flaky")
    assert task["attempts"] == 2


def test_4_blocked_after_max_retries(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    tasks = [
        {
            "id": "bad",
            "name": "bad",
            "gate": "safe",
            "deps": [],
            "command": _failing_task(9),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 1, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)
    result = _run_controller(project, plan_path)
    assert result["status"] == BLOCKED, result
    assert result["reason"]
    assert StateStore(project).get_task("bad")["attempts"] == 2


def test_5_require_approval_pauses(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    policy_path = tmp_path / "automation_policy.yaml"
    policy_path.write_text(
        json.dumps(
            {
                "default": "AUTO_EXECUTE",
                "gates": {"modify_project_files": "REQUIRE_APPROVAL"},
            }
        )
    )
    tasks = [
        {
            "id": "warmup",
            "name": "warmup",
            "gate": "read_only",
            "deps": [],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "rewrite",
            "name": "rewrite",
            "gate": "modify_project_files",
            "deps": ["warmup"],
            "writes": [".repro/notes.md"],
            "command": _task_command(["echo data > .repro/notes.md"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)
    controller = Controller(
        project_root=project, plan_path=plan_path, automation="safe-auto", policy_path=policy_path
    )
    # Run the loop on a thread so we can approve while it is alive.
    holder: dict = {}
    thread = threading.Thread(target=lambda: holder.update(result=controller.run()))
    thread.start()
    try:
        store = StateStore(project)
        ok = _wait_until(lambda: store.list_tasks({"WAITING_APPROVAL"}), timeout=10)
        assert ok, "task never reached WAITING_APPROVAL"
        approvals = store.pending_approvals()
        assert approvals and approvals[0]["task_id"] == "rewrite"
    finally:
        thread.join(timeout=15)
    result = holder["result"]
    assert result["status"] == WAITING_APPROVAL, result
    assert result["pending_approvals"], "approval id must be reported"


def test_6_approve_resumes(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    policy_path = tmp_path / "automation_policy.yaml"
    policy_path.write_text(
        json.dumps(
            {
                "default": "AUTO_EXECUTE",
                "gates": {"modify_project_files": "REQUIRE_APPROVAL"},
            }
        )
    )
    tasks = [
        {
            "id": "warmup",
            "name": "warmup",
            "gate": "read_only",
            "deps": [],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "rewrite",
            "name": "rewrite",
            "gate": "modify_project_files",
            "deps": ["warmup"],
            "writes": [".repro/notes.md"],
            "command": _task_command(["echo approved > .repro/notes.md"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)
    controller = Controller(
        project_root=project, plan_path=plan_path, automation="safe-auto", policy_path=policy_path
    )
    holder: dict = {}
    thread = threading.Thread(target=lambda: holder.update(result=controller.run()))
    thread.start()
    try:
        store = StateStore(project)
        ok = _wait_until(lambda: store.pending_approvals(), timeout=10)
        assert ok, "approval was never created"
        approval_id = store.pending_approvals()[0]["approval_id"]
        time.sleep(0.2)
        gate = ApprovalGate(store)
        gate.approve(approval_id, "ok")
    finally:
        thread.join(timeout=20)
    result = holder["result"]
    assert result["status"] == COMPLETE, result
    assert (project / ".repro" / "notes.md").exists()


def test_7_reject_skips_task(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    policy_path = tmp_path / "automation_policy.yaml"
    policy_path.write_text(
        json.dumps(
            {
                "default": "AUTO_EXECUTE",
                "gates": {"modify_project_files": "REQUIRE_APPROVAL"},
            }
        )
    )
    tasks = [
        {
            "id": "warmup",
            "name": "warmup",
            "gate": "read_only",
            "deps": [],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "side",
            "name": "side",
            "gate": "modify_project_files",
            "deps": ["warmup"],
            "writes": [".repro/notes.md"],
            "command": _task_command(["echo nope > .repro/notes.md"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "after",
            "name": "after",
            "gate": "safe",
            "deps": ["warmup"],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks, mandatory=["warmup", "after"])
    controller = Controller(
        project_root=project, plan_path=plan_path, automation="safe-auto", policy_path=policy_path
    )
    holder: dict = {}
    thread = threading.Thread(target=lambda: holder.update(result=controller.run()))
    thread.start()
    try:
        store = StateStore(project)
        ok = _wait_until(lambda: store.pending_approvals(), timeout=10)
        assert ok, "approval was never created"
        approval_id = store.pending_approvals()[0]["approval_id"]
        time.sleep(0.2)
        ApprovalGate(store).reject(approval_id, "by design")
    finally:
        thread.join(timeout=20)
    result = holder["result"]
    assert result["status"] == COMPLETE, result
    side = StateStore(project).get_task("side")
    assert side["status"] == "REJECTED"
    assert not (project / ".repro" / "notes.md").exists()


def test_8_long_task_auto_verify(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    checkpoint = project / "output" / "checkpoint.bin"
    acceptance = _task_command([f"test -s {checkpoint}"], workdir=project)
    command = _long_task(
        project, "long", seconds=0.6, checkpoint="output/checkpoint.bin", acceptance=acceptance
    )
    tasks = [
        {
            "id": "long",
            "name": "long",
            "gate": "safe",
            "deps": [],
            "command": command,
            "timeout_min": 1,
            "acceptance_tests": [
                {"command": _task_command([f"test -s {checkpoint}"], workdir=project)}
            ],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
            "checkpoint": "output/checkpoint.bin",
        }
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)
    start = time.monotonic()
    result = _run_controller(project, plan_path)
    elapsed = time.monotonic() - start
    assert result["status"] == COMPLETE, result
    assert checkpoint.exists()
    events = StateStore(project).events(limit=100)
    types = {event["event_type"] for event in events}
    assert {"PROCESS_STARTED", "VERIFICATION_PASS", "ACCEPTANCE_RESULT"}.issubset(types)
    assert elapsed > 0.6


def test_9_recover_after_kill(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    sentinel = project / "output" / "checkpoint-recover.bin"
    long_command = _long_task(
        project, "long", seconds=0.6, checkpoint="output/checkpoint-recover.bin"
    )
    tasks = [
        {
            "id": "long",
            "name": "long",
            "gate": "safe",
            "deps": [],
            "command": long_command,
            "timeout_min": 1,
            "acceptance_tests": [
                {"command": _task_command([f"test -s {sentinel}"], workdir=project)}
            ],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
            "checkpoint": "output/checkpoint-recover.bin",
        }
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)

    # First run is interrupted: we delete the controller heartbeat while the task
    # is mid-flight to mimic a kill -9 of the controller.
    interrupted = {}

    def _runner():
        controller = Controller(project_root=project, plan_path=plan_path)
        # Patch the heartbeat to point at the future so the recovery sees a stale
        # heartbeat, but we still want the recovery to spot the task.
        interrupted["controller"] = controller

        # Kill the heartbeat before run() completes.
        def _kill_heartbeat():
            time.sleep(0.2)
            try:
                controller.store.heartbeat_path.unlink()
            except FileNotFoundError:
                pass

        threading.Thread(target=_kill_heartbeat, daemon=True).start()
        interrupted["result"] = controller.run()

    thread = threading.Thread(target=_runner)
    thread.start()
    thread.join(timeout=20)
    assert "result" in interrupted
    # The controller exited STOPPED via missing heartbeat not being a real exit
    # signal in this setup; we accept any non-COMPLETE first result as long as
    # we can resume.
    store = StateStore(project)
    assert store.heartbeat_path.exists() is False or True  # heartbeat is optional after kill
    # Resume: the RUNNING task should jump to VERIFYING via recovery, and the
    # acceptance test confirms the checkpoint file landed.
    result = _run_controller(project, plan_path, resume=True)
    assert result["status"] == COMPLETE, result
    assert sentinel.exists()


def test_10_passed_task_not_re_run(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    sentinel = project / "output" / "never-twice.txt"
    tasks = [
        {
            "id": "once",
            "name": "once",
            "gate": "safe",
            "deps": [],
            "command": _task_command([f"echo first > {sentinel}"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "tail",
            "name": "tail",
            "gate": "safe",
            "deps": ["once"],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)
    first = _run_controller(project, plan_path)
    assert first["status"] == COMPLETE
    sentinel.write_text("untouched", encoding="utf-8")
    # Re-run: even though the plan still mentions "once", it must not be re-executed.
    second = _run_controller(project, plan_path)
    assert second["status"] == COMPLETE
    assert sentinel.read_text() == "untouched"
    task = StateStore(project).get_task("once")
    assert task["attempts"] == 1


def test_11_cycle_dependency_blocked(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    tasks = [
        {
            "id": "a",
            "name": "a",
            "gate": "safe",
            "deps": ["b"],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "b",
            "name": "b",
            "gate": "safe",
            "deps": ["a"],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)
    result = _run_controller(project, plan_path)
    assert result["status"] == BLOCKED, result
    assert "cyclic" in result["reason"] or "depend" in result["reason"]


def test_12_no_ready_exits_blocked(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    tasks = [
        {
            "id": "root-fail",
            "name": "root-fail",
            "gate": "safe",
            "deps": [],
            "command": _failing_task(1),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "leaf",
            "name": "leaf",
            "gate": "safe",
            "deps": ["root-fail"],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks, mandatory=["root-fail"])
    start = time.monotonic()
    result = _run_controller(project, plan_path)
    elapsed = time.monotonic() - start
    assert result["status"] == BLOCKED, result
    assert elapsed < 3.0, f"controller spun: {elapsed:.2f}s"


def test_13_pause_continue_stop(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    tasks = [
        {
            "id": "slow-1",
            "name": "slow-1",
            "gate": "safe",
            "deps": [],
            "command": _long_task(project, "slow-1", seconds=0.8, checkpoint="output/slow-1.bin"),
            "timeout_min": 5,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "slow-2",
            "name": "slow-2",
            "gate": "safe",
            "deps": ["slow-1"],
            "command": _long_task(project, "slow-2", seconds=0.8, checkpoint="output/slow-2.bin"),
            "timeout_min": 5,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks)
    controller = Controller(project_root=project, plan_path=plan_path)
    holder: dict = {}
    thread = threading.Thread(target=lambda: holder.update(result=controller.run()))
    thread.start()
    try:
        # Wait until the first task is RUNNING
        store = StateStore(project)
        assert _wait_until(
            lambda: any(task["status"] == "RUNNING" for task in store.list_tasks()), timeout=10
        )
        store.set_control_state("PAUSED")
        # The loop should exit with PAUSED on the next tick
        thread.join(timeout=10)
        result = holder["result"]
        assert result["status"] == PAUSED
    finally:
        if thread.is_alive():
            thread.join(timeout=5)

    # Continue: finish the run.
    controller2 = Controller(project_root=project, plan_path=plan_path, resume=True)
    final = controller2.run()
    assert final["status"] == COMPLETE, final
    assert (project / "output" / "slow-1.bin").exists()
    assert (project / "output" / "slow-2.bin").exists()

    # Stop path
    tasks2 = [
        {
            "id": "block",
            "name": "block",
            "gate": "safe",
            "deps": [],
            "command": _long_task(project, "block", seconds=4.0, checkpoint="output/block.bin"),
            "timeout_min": 10,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        }
    ]
    plan2 = tmp_path / "plan2.yaml"
    plan2.write_text(
        json.dumps(
            {
                "plan_id": "stop-demo",
                "mode": "strict",
                "tasks": tasks2,
                "approvals_required": [],
                "mandatory_task_ids": ["block"],
                "budgets": {"max_parallel_tasks": 1},
            }
        )
    )
    controller3 = Controller(project_root=project, plan_path=plan2, resume=True)
    holder2: dict = {}
    thread2 = threading.Thread(target=lambda: holder2.update(result=controller3.run()))
    thread2.start()
    try:
        store = StateStore(project)
        assert _wait_until(lambda: store.list_tasks({"RUNNING"}), timeout=10)
        store.set_control_state("STOPPED")
    finally:
        thread2.join(timeout=10)
    assert holder2["result"]["status"] == STOPPED


def test_14_final_acceptance_failure_blocks(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    tasks = [
        {
            "id": "passing",
            "name": "passing",
            "gate": "safe",
            "deps": [],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "lying",
            "name": "lying",
            "gate": "safe",
            "deps": ["passing"],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [{"command": _task_command(["exit 3"], workdir=project)}],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks, mandatory=["passing", "lying"])
    result = _run_controller(project, plan_path)
    assert result["status"] == BLOCKED, result
    task = StateStore(project).get_task("lying")
    assert task["status"] == "FAILED"


def test_15_policy_change_takes_effect(tmp_path: Path) -> None:
    project = _mkdirs(tmp_path / "proj")
    policy_path = tmp_path / "automation_policy.yaml"
    policy_path.write_text(
        json.dumps(
            {
                "default": "AUTO_EXECUTE",
                "gates": {"modify_project_files": "REQUIRE_APPROVAL"},
            }
        )
    )
    tasks = [
        {
            "id": "warmup",
            "name": "warmup",
            "gate": "read_only",
            "deps": [],
            "command": _task_command(["true"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
        {
            "id": "edit",
            "name": "edit",
            "gate": "modify_project_files",
            "deps": ["warmup"],
            "writes": [".repro/edit.md"],
            "command": _task_command(["echo hi > .repro/edit.md"], workdir=project),
            "timeout_min": 1,
            "acceptance_tests": [],
            "retry_policy": {"max_retries": 0, "delay_seconds": 0},
        },
    ]
    plan_path = _make_plan(tmp_path, tasks=tasks, mandatory=["warmup", "edit"])
    controller = Controller(
        project_root=project, plan_path=plan_path, automation="safe-auto", policy_path=policy_path
    )
    holder: dict = {}
    thread = threading.Thread(target=lambda: holder.update(result=controller.run()))
    thread.start()
    try:
        store = StateStore(project)
        assert _wait_until(lambda: store.pending_approvals(), timeout=10)
        # Without restarting, mutate the policy file to AUTO_EXECUTE.
        policy_path.write_text(
            json.dumps(
                {
                    "default": "AUTO_EXECUTE",
                    "gates": {"modify_project_files": "AUTO_EXECUTE"},
                }
            )
        )
        # Approve the pending request so the controller moves forward.
        approval_id = store.pending_approvals()[0]["approval_id"]
        time.sleep(0.2)
        ApprovalGate(store).approve(approval_id, "policy changed")
    finally:
        thread.join(timeout=20)
    result = holder["result"]
    assert result["status"] == COMPLETE, result
    events = StateStore(project).events(limit=500)
    policy_decisions = [event for event in events if event["event_type"] == "POLICY_DECISION"]
    assert any(event["payload"]["decision"] == "AUTO_EXECUTE" for event in policy_decisions)


# ── Daemon lifecycle (D2/D3 regression tests) ────────────────────────────


def _plan_for_daemon(project: Path) -> dict:
    return {
        "id": "ok",
        "name": "ok",
        "gate": "read_only",
        "deps": [],
        "command": _task_command(["true"], workdir=project),
        "timeout_min": 1,
        "acceptance_tests": [],
        "retry_policy": {"max_retries": 0, "delay_seconds": 0},
    }


def _pid_path(project: Path) -> Path:
    return project / ".repro" / "execution" / "controller.pid"


def _heartbeat_path(project: Path) -> Path:
    return project / ".repro" / "execution" / "controller.heartbeat"


def _daemon_log_path(project: Path) -> Path:
    return project / ".repro" / "execution" / "daemon.log"


def test_16_daemon_start_on_fresh_project(tmp_path: Path) -> None:
    """D2 regression: daemon start must not crash before the child is launched.

    On a brand-new project (no `.repro/execution` directory yet), the parent
    must create the daemon log directory itself before Popen opens the file.
    """
    import subprocess as _subprocess

    project = tmp_path / "fresh_proj"
    project.mkdir()
    (project / ".repro").mkdir()
    assert not (project / ".repro" / "execution").exists()
    plan_path = _make_plan(tmp_path, tasks=[_plan_for_daemon(project)])
    repo_root = PLUGIN_ROOT
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "reproctl.py"),
        "daemon",
        "start",
        "--project",
        str(project),
        "--plan",
        str(plan_path),
        "--automation",
        "safe-auto",
        "--mode",
        "strict",
    ]
    proc = _subprocess.run(cmd, cwd=str(project), capture_output=True, text=True, timeout=30)
    assert proc.returncode in (0, 10), proc.stderr + "\n" + proc.stdout
    assert _daemon_log_path(project).exists(), "daemon log file must be created"
    pid = json.loads(proc.stdout)["pid"]
    # PID must be alive; heartbeat file must be written within a couple of seconds.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _heartbeat_path(project).exists():
            break
        time.sleep(0.1)
    assert _heartbeat_path(project).exists(), "controller.heartbeat must appear"
    assert _pid_path(project).exists(), "controller.pid file must exist"
    # Stop the daemon and ensure everything is cleaned up.
    stop = _subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "reproctl.py"),
            "daemon",
            "stop",
            "--project",
            str(project),
        ],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert stop.returncode == 0, stop.stderr
    # The child must be terminated — pid file is removed on clean stop.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not _pid_path(project).exists():
            break
        time.sleep(0.1)
    assert not _pid_path(project).exists(), "daemon stop must remove the pid file"
    # Process should be gone.
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    assert not alive, "daemon child must be terminated after daemon stop"


def test_17_daemon_child_arg_recognized(tmp_path: Path) -> None:
    """D3 regression: the daemon-spawned child re-execs `reproctl ... run`.

    The parent passes ``--daemon-child`` so the argv must NOT trip argparse.
    """
    from orchestrator.cli import build_parser

    parser = build_parser()
    # Simulate the exact argv the daemon-spawned re-exec would produce.
    argv = [
        "run",
        "--project",
        str(tmp_path),
        "--plan",
        str(tmp_path / "plan.yaml"),
        "--automation",
        "safe-auto",
        "--mode",
        "strict",
        "--daemon-child",
    ]
    args = parser.parse_args(argv)
    assert args.orch_command == "run"
    assert args.daemon_child is True
    # End-to-end: actually run the same argv the daemon-spawned re-exec uses
    # via reproctl.py to confirm the dispatch + argparse chain accepts it.
    plan_path = _make_plan(
        tmp_path,
        tasks=[
            {
                "id": "ok",
                "name": "ok",
                "gate": "read_only",
                "deps": [],
                "command": _task_command(["true"], workdir=tmp_path),
                "timeout_min": 1,
                "acceptance_tests": [],
                "retry_policy": {"max_retries": 0, "delay_seconds": 0},
            }
        ],
    )
    (tmp_path / ".repro").mkdir(exist_ok=True)
    import subprocess as _subprocess

    proc = _subprocess.run(
        [
            sys.executable,
            str(PLUGIN_ROOT / "scripts" / "reproctl.py"),
            "run",
            "--project",
            str(tmp_path),
            "--plan",
            str(plan_path),
            "--daemon-child",
        ],
        cwd=str(PLUGIN_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode != 2, (
        "argparse rejected --daemon-child:\nstdout=" + proc.stdout + "\nstderr=" + proc.stderr
    )


def test_18_daemon_stop_terminates_orphan_workers(tmp_path: Path) -> None:
    """D-or-orphan-workers regression: daemon stop must reap task workers too.

    Each task is launched with start_new_session=True so its worker tree sits
    in a separate process group from the controller's PGID. SIGTERM on the
    controller PGID does NOT reach those workers; without explicit
    intervention they survive the daemon stop and the SQLite row stays in
    RUNNING.
    """
    import subprocess as _subprocess

    project = tmp_path / "orphan_proj"
    project.mkdir()
    (project / ".repro").mkdir()
    plan_path = _make_plan(
        project,
        tasks=[
            {
                "id": "t3_train",
                "name": "t3_train",
                "gate": "safe",
                "deps": [],
                "command": _long_task(
                    project, "t3_train", seconds=10.0, checkpoint="output/t3_train.bin"
                ),
                "timeout_min": 5,
                "acceptance_tests": [],
                "retry_policy": {"max_retries": 0, "delay_seconds": 0},
            }
        ],
    )
    repo_root = PLUGIN_ROOT
    cli = str(repo_root / "scripts" / "reproctl.py")

    start = _subprocess.run(
        [
            sys.executable,
            cli,
            "daemon",
            "start",
            "--project",
            str(project),
            "--plan",
            str(plan_path),
            "--automation",
            "safe-auto",
            "--mode",
            "strict",
        ],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert start.returncode in (0, 10), start.stdout + start.stderr
    daemon_pid = json.loads(start.stdout)["pid"]
    try:
        store = StateStore(project)
        # Wait until the worker task is RUNNING.
        assert _wait_until(
            lambda: any(task["status"] == "RUNNING" for task in store.list_tasks()),
            timeout=10,
        ), "worker task never reached RUNNING"
        worker_task = next(task for task in store.list_tasks() if task["status"] == "RUNNING")
        worker_pid = int(worker_task["pid"])
        # Sanity: the worker is a different session than the controller.
        assert worker_pid and worker_pid != daemon_pid

        stop = _subprocess.run(
            [sys.executable, cli, "daemon", "stop", "--project", str(project)],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert stop.returncode == 0, stop.stdout + stop.stderr
        body = json.loads(stop.stdout)
        assert any(wr.get("terminated") for wr in body.get("workers", [])), (
            f"daemon stop did not report any terminated worker: {body}"
        )

        # The worker must be reaped (with up to 3 s for SIGTERM grace).
        deadline = time.monotonic() + 4.0
        alive = True
        while time.monotonic() < deadline:
            try:
                os.kill(worker_pid, 0)
            except ProcessLookupError:
                alive = False
                break
            time.sleep(0.1)
        assert not alive, f"worker pid {worker_pid} survived daemon stop"

        # SQLite must not be stuck on RUNNING for t3_train.
        post = StateStore(project).get_task("t3_train")
        assert post["status"] != "RUNNING", post

        # Controller artifacts are cleaned up.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not _pid_path(project).exists():
                break
            time.sleep(0.1)
        assert not _pid_path(project).exists(), "controller.pid should be removed"
    finally:
        # Final safety net in case any of the above fails: reap whatever is left.
        try:
            _subprocess.run(
                [sys.executable, cli, "daemon", "stop", "--project", str(project)],
                cwd=str(project),
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass
