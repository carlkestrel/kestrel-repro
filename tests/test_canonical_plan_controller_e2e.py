"""R3R-2: Canonical PlanSchema → Controller E2E tests.

These tests verify that:
1. A YAML-frontmatter plan (canonical format) loads through the Controller
   without AttributeError (the PlanSchema.to_runtime_dict() bridge).
2. The retry semantics are unified: canonical max_attempts → legacy max_retries.
3. All required fields are accessible via dict interface.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve()
PLUGIN_ROOT = THIS.parents[1]
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from orchestrator import Controller, StateStore  # noqa: E402
from orchestrator.controller import BLOCKED  # noqa: E402


def _mkdirs(project: Path) -> Path:
    (project / ".repro").mkdir(parents=True, exist_ok=True)
    (project / "output").mkdir(parents=True, exist_ok=True)
    return project


def _make_canonical_plan(
    tmp_path: Path,
    *,
    tasks,
    execution_track: str = "strict",
    automation_level: str = "gated-autopilot",
    max_attempts: int = 1,
    mandatory_task_ids: list[str] | None = None,
) -> Path:
    """Create a canonical YAML-frontmatter plan (not legacy JSON).

    R3R-2: Tests the canonical path (PlanSchema) rather than legacy fallback.
    """
    mandatory = mandatory_task_ids or [task["id"] for task in tasks]
    plan_body = (
        f"# Canonical plan for {tmp_path.name}\n"
        f"# Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
    )
    # Canonical YAML frontmatter
    import yaml

    fm = {
        "schema_version": "2.0",
        "plan_id": f"canonical-{tmp_path.name}-{int(time.time() * 1000)}",
        "execution_track": execution_track,
        "automation_level": automation_level,
        "research_purpose": "reproduce",
        "mandatory_task_ids": mandatory,
        "budgets": {
            "max_retries": 3,
            "approval_wait_seconds": 2.0,
        },
        "tasks": [],
    }
    for t in tasks:
        task_dict = dict(t)
        # R3R-2: canonical retry_policy uses max_attempts (not max_retries)
        if "retry_policy" not in task_dict:
            task_dict["retry_policy"] = {}
        if "max_attempts" not in task_dict["retry_policy"]:
            task_dict["retry_policy"]["max_attempts"] = max_attempts
        task_dict.setdefault("writes", [])
        task_dict.setdefault("deps", [])
        task_dict.setdefault("gate", "default")
        fm["tasks"].append(task_dict)

    yaml_content = yaml.safe_dump(fm, default_flow_style=False)
    content = "---\n" + yaml_content + "---\n" + plan_body
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(content, encoding="utf-8")
    return plan_path


class TestCanonicalPlanSchemaController:
    """R3R-2: PlanSchema enters Controller without AttributeError."""

    def test_canonical_yaml_plan_loads_without_attributeerror(self, tmp_path: Path) -> None:
        """Canonical YAML-frontmatter plan: Controller loads PlanSchema, converts to dict.

        Before R3R-2: controller.load_plan() returned PlanSchema on canonical path,
        Controller did self.plan["mode"] = mode and self.plan.get("mandatory_task_ids")
        which raised AttributeError.
        After R3R-2: to_runtime_dict() converts PlanSchema → dict, no AttributeError.
        """
        project = _mkdirs(tmp_path / "project")
        tasks = [
            {
                "id": "T1_echo",
                "name": "Echo test",
                "command": "echo hello",
                "gate": "safe",
                "deps": [],
                "timeout_min": 1.0,
                "acceptance_tests": ["echo passed"],
                "retry_policy": {"max_attempts": 1},
            },
        ]
        plan_path = _make_canonical_plan(
            tmp_path / "project",
            tasks=tasks,
            mandatory_task_ids=["T1_echo"],
        )

        # This must not raise AttributeError: 'PlanSchema' object has no attribute 'get'
        controller = Controller(
            project_root=str(project),
            plan_path=str(plan_path),
            mode="strict",
        )
        # Verify self.plan is a plain dict
        assert isinstance(controller.plan, dict)
        # Verify required keys are accessible
        assert controller.plan.get("mode") == "strict"
        assert "mandatory_task_ids" in controller.plan
        assert controller.plan.get("mandatory_task_ids") == ["T1_echo"]
        # Verify tasks are accessible
        tasks_loaded = controller.store.list_tasks()
        assert len(tasks_loaded) == 1
        assert tasks_loaded[0]["id"] == "T1_echo"

    def test_retry_max_attempts_semantics(self, tmp_path: Path) -> None:
        """Canonical max_attempts=N means N total attempts (including first).

        R3R-2: to_runtime_dict() converts max_attempts → max_retries = max_attempts - 1.
        Controller._fail() reads max_retries with <= comparison.
        max_attempts=3 → max_retries=2 → allows 2 retries (3 total attempts).
        """
        project = _mkdirs(tmp_path / "project")
        tasks = [
            {
                "id": "T1_failing",
                "name": "Failing task",
                "command": "exit 1",
                "gate": "safe",
                "deps": [],
                "timeout_min": 1.0,
                "acceptance_tests": ["echo passed"],
                # R3R-2: canonical field is max_attempts
                "retry_policy": {"max_attempts": 3},
            },
        ]
        plan_path = _make_canonical_plan(
            tmp_path / "project",
            tasks=tasks,
            max_attempts=3,
            mandatory_task_ids=["T1_failing"],
        )

        controller = Controller(
            project_root=str(project),
            plan_path=str(plan_path),
            mode="strict",
        )

        # Run controller; it should fail T1 once, retry twice, then BLOCK
        result = controller.run()
        assert result["status"] == BLOCKED, f"Expected BLOCKED, got {result['status']}"

        # Check retry count: max_attempts=3 → allows 2 retries → attempts should be 3
        store = StateStore(project)
        t1 = store.get_task("T1_failing")
        assert t1["attempts"] == 3, f"Expected 3 attempts (max_attempts=3), got {t1['attempts']}"

    def test_retry_max_attempts_one_no_retry(self, tmp_path: Path) -> None:
        """max_attempts=1 means exactly one attempt, no retries."""
        project = _mkdirs(tmp_path / "project")
        tasks = [
            {
                "id": "T1_failing",
                "name": "Failing task",
                "command": "exit 1",
                "gate": "safe",
                "deps": [],
                "timeout_min": 1.0,
                "acceptance_tests": ["echo passed"],
                "retry_policy": {"max_attempts": 1},
            },
        ]
        plan_path = _make_canonical_plan(
            tmp_path / "project",
            tasks=tasks,
            max_attempts=1,
            mandatory_task_ids=["T1_failing"],
        )

        controller = Controller(
            project_root=str(project),
            plan_path=str(plan_path),
            mode="strict",
        )

        result = controller.run()
        assert result["status"] == BLOCKED, f"Expected BLOCKED, got {result['status']}"

        store = StateStore(project)
        t1 = store.get_task("T1_failing")
        # max_attempts=1 → 1 total attempt, no retries
        assert t1["attempts"] == 1, f"Expected 1 attempt, got {t1['attempts']}"

    def test_canonical_plan_with_non_evidentiary(self, tmp_path: Path) -> None:
        """Canonical plan: non_evidentiary task is recorded correctly.

        R3R-2: to_runtime_dict() preserves non_evidentiary from TaskDef.
        """
        project = _mkdirs(tmp_path / "project")
        tasks = [
            {
                "id": "T1_explore",
                "name": "Explore task",
                "command": "echo exploring",
                "gate": "safe",
                "deps": [],
                "timeout_min": 1.0,
                "acceptance_tests": ["echo passed"],  # intentionally empty
                "non_evidentiary": True,
                "retry_policy": {"max_attempts": 1},
            },
        ]
        plan_path = _make_canonical_plan(
            tmp_path / "project",
            tasks=tasks,
            mandatory_task_ids=["T1_explore"],
        )

        controller = Controller(
            project_root=str(project),
            plan_path=str(plan_path),
            mode="strict",
        )

        store = StateStore(project)
        t1 = store.get_task("T1_explore")
        assert t1.get("non_evidentiary") is True

    def test_mode_override_on_canonical_plan(self, tmp_path: Path) -> None:
        """Controller(mode='optimized') overrides canonical execution_track."""
        project = _mkdirs(tmp_path / "project")
        tasks = [
            {
                "id": "T1_echo",
                "name": "Echo test",
                "command": "echo hello",
                "gate": "safe",
                "deps": [],
                "timeout_min": 1.0,
                "acceptance_tests": ["echo passed"],
                "retry_policy": {"max_attempts": 1},
            },
        ]
        plan_path = _make_canonical_plan(
            tmp_path / "project",
            tasks=tasks,
            execution_track="strict",
            mandatory_task_ids=["T1_echo"],
        )

        controller = Controller(
            project_root=str(project),
            plan_path=str(plan_path),
            mode="optimized",
        )
        # mode override must work without error
        assert controller.plan.get("mode") == "optimized"
