from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from .approval_gate import ApprovalGate
from .event_journal import EventJournal
from .policy_engine import AUTO_EXECUTE, REJECT, REQUIRE_APPROVAL, PolicyEngine
from .process_manager import ProcessManager
from .recovery import RecoveryManager
from .scheduler import CycleDependencyError, Scheduler
from .state_store import StateStore, utc_now
from .stop_hook import StopHook
from .task_executor import TaskExecutor
from .verifier import Verifier
from .watchdog import Watchdog

COMPLETE = "COMPLETE"
BLOCKED = "BLOCKED"
WAITING_APPROVAL = "WAITING_APPROVAL"
PAUSED = "PAUSED"
STOPPED = "STOPPED"
EXIT_STATES = {COMPLETE, BLOCKED, WAITING_APPROVAL, PAUSED, STOPPED}


def load_plan(path: str | Path) -> dict:
    """R3F-4: delegate to the canonical plan schema loader, with legacy
    fallback.

    The Controller used to parse the plan file with a hand-rolled YAML/JSON
    loader that accepted arbitrary dicts and could pass malformed plans to
    the orchestrator. The canonical ``scripts.startup.plan_schema`` module
    enforces schema validation, dependency-cycle detection, mode migration
    (legacy → canonical), and ``NEEDS_MODE_REVIEW`` for ambiguous cases.

    Behaviour:
      1. Try canonical load first. If it succeeds, return the canonical dict.
      2. If canonical fails because the file is in legacy JSON / non-frontmatter
         format, attempt ``migrate_legacy_plan`` and re-validate.
      3. If migration also fails, raise ``ValueError`` listing the validation
         errors. (Earlier we returned early on missing frontmatter; this
         preserves test-style plans while still enforcing the schema.)
    """
    from startup.plan_schema import (
        load_plan as _canonical_load,
        validate_plan,
        migrate_legacy_plan,
        _dict_to_plan,
    )
    from pathlib import Path as _P

    p = _P(path)
    try:
        return _canonical_load(p)
    except SystemExit as exc:
        # _canonical_load sys.exits with code 5 on validation/format errors.
        # We catch it here and attempt legacy migration.
        if exc.code != 5:
            raise
    except Exception:
        # Any other error: re-raise; we only swallow the legacy-format case.
        raise

    # Legacy fallback: read raw, attempt migration, re-validate.
    text = p.read_text(encoding="utf-8")
    try:
        import json as _json
        legacy = _json.loads(text)
    except Exception:
        import yaml as _yaml
        legacy = _yaml.safe_load(text)
    if not isinstance(legacy, dict):
        raise ValueError(f"plan must be a mapping; got {type(legacy).__name__}")
    migrated = migrate_legacy_plan(legacy)
    # Schema-level validation: enforce mode, schema_version, mode review,
    # acceptance_tests (with non_evidentiary opt-out). Cycle and unknown-dep
    # detection is the Controller's job — see ``scheduler.detect_cycles`` —
    # so we filter those out here to keep responsibility split.
    plan = _dict_to_plan(migrated, text.encode("utf-8"), loaded_from=p)
    errors = [e for e in validate_plan(plan)
              if e.field != "tasks" or "circular" not in e.message]
    errors = [e for e in errors if not (e.field == "deps" and "unknown task" in e.message)]
    if errors:
        raise ValueError(
            "plan validation failed (legacy migration did not produce a valid plan): "
            + "; ".join(str(e) for e in errors)
        )
    return migrated


class Controller:
    """Persistent blocked-or-complete run loop over explicit task transitions."""

    def __init__(self, *, project_root: str | Path, plan_path: str | Path,
                 mode: str | None = None, automation: str = "safe-auto",
                 policy_path: str | Path | None = None, resume: bool = False,
                 poll_interval: float = 0.05,
                 process_manager: ProcessManager | None = None,
                 clear_control_state_on_resume: bool = True):
        self.project_root = Path(project_root).resolve()
        self.plan_path = Path(plan_path).resolve()
        self.plan = load_plan(self.plan_path)
        if mode is not None:
            self.plan["mode"] = mode
        if self.plan.get("mode") not in {"strict", "optimized"}:
            raise ValueError("plan mode must be strict or optimized")
        self.execution_dir = self.project_root / ".repro" / "execution"
        self.journal = EventJournal(self.execution_dir / "events.jsonl")
        self.store = StateStore(self.project_root, journal=self.journal)
        self.store.initialize_plan(self.plan, self.plan_path, automation)
        if resume and clear_control_state_on_resume:
            self.store.set_control_state("RUNNING")
        self.policy = PolicyEngine(self.project_root, policy_path, automation)
        self.process_manager = process_manager or ProcessManager()
        self.scheduler = Scheduler(self.store)
        self.executor = TaskExecutor(self.project_root, self.store, self.process_manager)
        self.verifier = Verifier(self.project_root, self.store, self.process_manager)
        self.approvals = ApprovalGate(self.store)
        self.watchdog = Watchdog(self.store, self.process_manager, project_root=self.project_root)
        self.recovery = RecoveryManager(
            self.project_root, self.store, self.journal, self.process_manager
        )
        self.stop_hook = StopHook(self.project_root, self.store, self.journal)
        self.owner = f"controller-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.poll_interval = max(0.01, poll_interval)
        self.max_parallel = max(1, int(self.plan.get("budgets", {}).get(
            "max_parallel_tasks", 4
        )))
        self.resume_requested = resume
        self.approval_wait_seconds = float(
            (self.plan.get("budgets") or {}).get("approval_wait_seconds", 30.0)
        )
        self._waiting_since: float | None = None

    def run(self) -> dict:
        self.stop_hook.register()
        recovery = self.recovery.recover()
        try:
            self.scheduler.detect_cycles()
        except CycleDependencyError as exc:
            self.store.record_event("SCHEDULER_BLOCKED", payload={"reason": str(exc)})
            return self._exit(BLOCKED, str(exc), recovery)

        while True:
            self.store.heartbeat("controller", os.getpid(), {"owner": self.owner})
            self.approvals.cleanup_expired()
            control = self.store.control_state()
            if control == PAUSED:
                return self._exit(PAUSED, "controller paused", recovery)
            if control == STOPPED:
                self.watchdog.terminate_running()
                return self._exit(STOPPED, "controller stopped", recovery)

            progressed = self._collect_processes()
            progressed = self._run_verifications() or progressed
            progressed = self.scheduler.refresh() or progressed
            tasks = self.store.list_tasks()

            active = sum(task["status"] in {"RUNNING", "VERIFYING"} for task in tasks)
            capacity = max(0, self.max_parallel - active)
            if capacity:
                progressed = self._schedule(capacity) or progressed
                tasks = self.store.list_tasks()

            result = self._terminal_result(tasks, recovery)
            if result is not None:
                return result

            # Wait for VERIFYING tasks — the controller must not exit while any
            # verification is in-flight.  This is the "stay alive" guard that
            # prevents the orchestrator from exiting before acceptance tests run.
            if not progressed:
                verifying = [t["id"] for t in self.store.list_tasks({"VERIFYING"})]
                if not verifying:
                    self._wait_without_spinning(tasks)

    def _collect_processes(self) -> bool:
        progressed = False
        for task in self.store.list_tasks({"RUNNING"}):
            if not task.get("pid"):
                continue
            diagnosis = self.watchdog.inspect(task)
            code = self.executor.poll(task)
            if code is None and not diagnosis["timed_out"]:
                continue
            if diagnosis["timed_out"]:
                self._fail(task, "task timeout")
            elif code == 0:
                self.store.transition(
                    task["id"], "VERIFYING", expected="RUNNING",
                    fields={"pid": None, "finished_at": utc_now()},
                )
            else:
                self._fail(task, f"command exited with code {code}")
            progressed = True
        return progressed

    def _run_verifications(self) -> bool:
        progressed = False
        for task in self.store.list_tasks({"VERIFYING"}):
            passed, detail = self.verifier.verify(task)
            if passed:
                self.store.transition(
                    task["id"], "PASSED", expected="VERIFYING",
                    fields={"finished_at": utc_now(), "failure_reason": None},
                )
            else:
                self._fail(task, detail)
            progressed = True
        return progressed

    def _fail(self, task: dict, reason: str) -> None:
        current = self.store.get_task(task["id"])
        if current is None or current["status"] not in {"RUNNING", "VERIFYING"}:
            return
        failed = self.store.transition(
            task["id"], "FAILED", expected=current["status"],
            fields={"pid": None, "finished_at": utc_now(), "failure_reason": reason},
        )
        retry = failed.get("retry_policy") or {}
        max_retries = int(retry.get("max_retries", 0))
        if int(failed["attempts"]) <= max_retries:
            delay = float(retry.get("delay_seconds", retry.get("backoff_seconds", 0)))
            self.store.transition(
                task["id"], "RETRY_WAIT", expected="FAILED",
                fields={"retry_at": time.time() + max(0.0, delay)},
                event_type="TASK_RETRY_SCHEDULED",
            )

    def _schedule(self, capacity: int) -> bool:
        candidates = self.scheduler.select_ready(capacity)
        progressed = False
        for task in candidates:
            decision, reason = self.policy.evaluate(task)
            self.store.record_event("POLICY_DECISION", task["id"], {
                "decision": decision, "reason": reason
            })
            if task["status"] == "APPROVED":
                decision = "AUTO_EXECUTE"
                reason = f"{reason} (already approved)"
            if decision == REQUIRE_APPROVAL:
                self.approvals.request(task, reason)
                progressed = True
                continue
            if decision == REJECT:
                self.store.transition(
                    task["id"], "REJECTED", expected={"READY", "APPROVED"},
                    fields={"failure_reason": reason, "finished_at": utc_now()},
                    event_type="TASK_POLICY_REJECTED",
                )
                progressed = True
                continue
            if decision != AUTO_EXECUTE:
                raise RuntimeError(f"unhandled policy decision {decision}")
            claimed = self.store.claim_task(task["id"], self.owner)
            if claimed is None:
                continue
            try:
                self.executor.launch(claimed)
            except Exception as exc:
                self._fail(claimed, f"process launch failed: {exc}")
            progressed = True
        return progressed

    def _terminal_result(self, tasks: list[dict], recovery: dict) -> dict | None:
        if any(task["status"] in {"RUNNING", "VERIFYING", "READY", "APPROVED"}
               for task in tasks):
            self._waiting_since = None
            return None
        if any(task["status"] == "WAITING_APPROVAL" for task in tasks):
            approvals = self.store.pending_approvals()
            if not approvals:
                return self._exit(BLOCKED, "waiting approval but no pending approval",
                                  recovery)
            # Stay in the loop briefly so the operator can decide; the loop's
            # default poll interval caps how long we wait.
            now = time.time()
            self._waiting_since = self._waiting_since or now
            if now - self._waiting_since >= self.approval_wait_seconds:
                return self._exit(WAITING_APPROVAL,
                                  ", ".join(a["approval_id"] for a in approvals),
                                  recovery)
            return None
        self._waiting_since = None
        if any(task["status"] == "RETRY_WAIT" for task in tasks):
            return None
        mandatory = set(self.plan.get("mandatory_task_ids", []))
        by_id = {task["id"]: task for task in tasks}
        missing = sorted(task_id for task_id in mandatory if task_id not in by_id)
        failed_mandatory = sorted(task_id for task_id in mandatory
                                  if task_id in by_id and by_id[task_id]["status"] != "PASSED")
        final_failures = [task for task in tasks if task["status"] == "FAIL"]
        if missing or failed_mandatory or final_failures:
            reasons = []
            if missing:
                reasons.append("missing mandatory tasks: " + ", ".join(missing))
            if failed_mandatory:
                reasons.append("mandatory tasks not PASS: " + ", ".join(failed_mandatory))
            if final_failures:
                reasons.append("failed tasks: " + ", ".join(task["id"] for task in final_failures))
            return self._exit(BLOCKED, "; ".join(reasons), recovery)
        deadlock = self.scheduler.deadlock_reason()
        if deadlock:
            return self._exit(BLOCKED, deadlock, recovery)
        if all(task["status"] in {"PASSED", "REJECTED"} for task in tasks):
            return self._exit(COMPLETE, "all mandatory tasks passed", recovery)
        return self._exit(BLOCKED, "no executable tasks remain", recovery)

    def _wait_without_spinning(self, tasks: list[dict]) -> None:
        retry_times = [task["retry_at"] for task in tasks
                       if task["status"] == "RETRY_WAIT" and task.get("retry_at")]
        delay = self.poll_interval
        if retry_times:
            delay = min(delay, max(0.01, min(retry_times) - time.time()))
        time.sleep(delay)

    def _exit(self, status: str, reason: str, recovery: dict) -> dict:
        if status not in EXIT_STATES:
            raise ValueError(f"invalid controller exit state: {status}")
        self.store.record_event("CONTROLLER_EXIT", payload={"status": status,
                                                            "reason": reason})
        snapshots = self.store.export_snapshots()
        return {"status": status, "reason": reason,
                "project_root": str(self.project_root), "recovery": recovery,
                "snapshots": snapshots, "tasks": self.store.list_tasks(),
                "pending_approvals": self.store.pending_approvals()}
