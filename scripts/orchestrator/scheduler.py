from __future__ import annotations

import time
from collections import deque


class CycleDependencyError(ValueError):
    pass


class Scheduler:
    """Deterministic dependency scheduler with retry promotion and cycle checks."""

    def __init__(self, store):
        self.store = store

    def detect_cycles(self) -> list[str]:
        tasks = self.store.list_tasks()
        graph = {task["id"]: list(task.get("deps", [])) for task in tasks}
        indegree = {task_id: len(deps) for task_id, deps in graph.items()}
        dependents: dict[str, list[str]] = {task_id: [] for task_id in graph}
        for task_id, deps in graph.items():
            for dep in deps:
                if dep not in graph:
                    raise CycleDependencyError(f"task {task_id} has unknown dependency {dep}")
                dependents[dep].append(task_id)
        queue = deque(task_id for task_id, degree in indegree.items() if degree == 0)
        visited: list[str] = []
        while queue:
            current = queue.popleft()
            visited.append(current)
            for child in dependents[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if len(visited) != len(graph):
            cyclic = sorted(task_id for task_id, degree in indegree.items() if degree > 0)
            raise CycleDependencyError("cyclic dependencies: " + ", ".join(cyclic))
        return visited

    def refresh(self) -> bool:
        changed = False
        now = time.time()
        tasks = {task["id"]: task for task in self.store.list_tasks()}
        for task in tasks.values():
            if task["status"] == "RETRY_WAIT" and (task.get("retry_at") or 0) <= now:
                self.store.transition(task["id"], "READY", expected="RETRY_WAIT",
                                      fields={"retry_at": None})
                changed = True
        if changed:
            tasks = {task["id"]: task for task in self.store.list_tasks()}
        for task in tasks.values():
            if task["status"] != "PENDING":
                continue
            deps = [tasks[dep]["status"] for dep in task.get("deps", [])]
            if all(status in {"PASSED", "PASSED"} for status in deps):
                self.store.transition(task["id"], "READY", expected="PENDING")
                changed = True
        return changed

    def select_ready(self, max_parallel: int = 1) -> list[dict]:
        ready = self.store.list_tasks({"READY", "APPROVED"})
        if not ready:
            return []
        approved = [task for task in ready if task["status"] == "APPROVED"]
        if approved:
            return approved[:max_parallel]
        readonly = [task for task in ready if task.get("gate") == "read_only"]
        if readonly:
            return readonly[:max_parallel]
        return ready[:1]

    def next_task(self) -> dict | None:
        self.refresh()
        selected = self.select_ready(1)
        return selected[0] if selected else None

    def deadlock_reason(self) -> str | None:
        tasks = self.store.list_tasks()
        if any(task["status"] in {"RUNNING", "VERIFYING", "READY", "APPROVED",
                                  "RETRY_WAIT", "WAITING_APPROVAL"} for task in tasks):
            return None
        unfinished = [task for task in tasks if task["status"] == "PENDING"]
        if not unfinished:
            return None
        details = []
        by_id = {task["id"]: task for task in tasks}
        for task in unfinished:
            blocked = [f"{dep}:{by_id[dep]['status']}" for dep in task.get("deps", [])
                       if by_id[dep]["status"] not in {"PASSED", "PASSED"}]
            details.append(f"{task['id']} waits on {','.join(blocked)}")
        return "dependency deadlock: " + "; ".join(details)
