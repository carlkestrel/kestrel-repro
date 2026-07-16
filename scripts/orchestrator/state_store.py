from __future__ import annotations

import csv
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


TASK_STATES = {
    "PENDING", "READY", "RUNNING", "VERIFYING", "PASS", "FAIL",
    "RETRY_WAIT", "WAITING_APPROVAL", "APPROVED", "REJECTED",
}
TRANSITIONS = {
    "PENDING": {"READY", "FAIL"},
    "READY": {"RUNNING", "WAITING_APPROVAL", "REJECTED", "FAIL"},
    "RUNNING": {"VERIFYING", "FAIL", "READY"},
    "VERIFYING": {"PASS", "FAIL"},
    "FAIL": {"RETRY_WAIT"},
    "RETRY_WAIT": {"READY"},
    "WAITING_APPROVAL": {"APPROVED", "REJECTED"},
    "APPROVED": {"RUNNING"},
    "PASS": set(),
    "REJECTED": set(),
}
CONTROL_STATES = {"RUNNING", "PAUSED", "STOPPED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """SQLite-backed source of truth for orchestrator state and history."""

    def __init__(self, project_root: str | Path, journal: Any | None = None):
        self.project_root = Path(project_root).resolve()
        self.execution_dir = self.project_root / ".repro" / "execution"
        self.execution_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.execution_dir / "state.sqlite3"
        self.heartbeat_path = self.execution_dir / "controller.heartbeat"
        self._journal = journal
        self._local = threading.local()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                raise
            else:
                conn.execute("COMMIT")
        finally:
            conn.close()

    def _initialize(self) -> None:
        ddl = [
            "CREATE TABLE IF NOT EXISTS metadata ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id TEXT PRIMARY KEY, name TEXT NOT NULL, gate TEXT NOT NULL,"
            "deps_json TEXT NOT NULL, command TEXT NOT NULL,"
            "timeout_min REAL NOT NULL, acceptance_json TEXT NOT NULL,"
            "retry_json TEXT NOT NULL, task_json TEXT NOT NULL,"
            "status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,"
            "pid INTEGER, log_path TEXT, started_at TEXT, finished_at TEXT,"
            "retry_at REAL, failure_reason TEXT, lock_owner TEXT,"
            "updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS approvals ("
            "approval_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
            "status TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL,"
            "expires_at REAL, decided_at TEXT,"
            "FOREIGN KEY(task_id) REFERENCES tasks(id))",
            "CREATE TABLE IF NOT EXISTS events ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT,"
            "timestamp TEXT NOT NULL, event_type TEXT NOT NULL,"
            "task_id TEXT, payload_json TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS heartbeats ("
            "owner TEXT PRIMARY KEY, pid INTEGER NOT NULL,"
            "timestamp REAL NOT NULL, detail_json TEXT NOT NULL)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id, seq)",
        ]
        with self.transaction() as conn:
            for stmt in ddl:
                conn.execute(stmt)
            conn.execute(
                "INSERT OR IGNORE INTO metadata(key,value) VALUES('control_state',?)",
                (json.dumps("RUNNING"),),
            )

    def _event_tx(self, conn: sqlite3.Connection, event_type: str,
                  task_id: str | None = None, payload: dict | None = None) -> dict:
        event = {
            "timestamp": utc_now(),
            "event_type": event_type,
            "task_id": task_id,
            "payload": payload or {},
        }
        cur = conn.execute(
            "INSERT INTO events(timestamp,event_type,task_id,payload_json) VALUES(?,?,?,?)",
            (event["timestamp"], event_type, task_id,
             json.dumps(event["payload"], sort_keys=True)),
        )
        event["seq"] = cur.lastrowid
        return event

    def _after_commit(self, events: list[dict]) -> None:
        if self._journal is not None:
            for event in events:
                self._journal.append(event)

    def set_metadata(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, sort_keys=True)
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO metadata(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, encoded),
            )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def initialize_plan(self, plan: dict, plan_path: str | Path,
                        automation: str = "safe-auto") -> None:
        required = {"plan_id", "mode", "tasks", "approvals_required",
                    "mandatory_task_ids", "budgets"}
        missing = required - set(plan)
        if missing:
            raise ValueError(f"plan missing keys: {', '.join(sorted(missing))}")
        events: list[dict] = []
        now = utc_now()
        with self.transaction() as conn:
            for key, value in {
                "plan_id": plan["plan_id"],
                "plan_path": str(Path(plan_path).resolve()),
                "mode": plan["mode"],
                "automation": automation,
                "mandatory_task_ids": plan["mandatory_task_ids"],
                "budgets": plan["budgets"],
            }.items():
                conn.execute(
                    "INSERT INTO metadata(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, json.dumps(value, sort_keys=True)),
                )
            known = {row["id"]: row["status"] for row in conn.execute(
                "SELECT id,status FROM tasks"
            )}
            ids = set()
            for task in plan["tasks"]:
                self._validate_task(task)
                task_id = task["id"]
                if task_id in ids:
                    raise ValueError(f"duplicate task id: {task_id}")
                ids.add(task_id)
                payload = json.dumps(task, sort_keys=True)
                values = (
                    task["name"], task["gate"], json.dumps(task.get("deps", [])),
                    task["command"], float(task["timeout_min"]),
                    json.dumps(task.get("acceptance_tests", [])),
                    json.dumps(task.get("retry_policy", {})), payload, now, task_id,
                )
                if task_id not in known:
                    conn.execute(
                        "INSERT INTO tasks(name,gate,deps_json,command,timeout_min,"
                        "acceptance_json,retry_json,task_json,updated_at,id,status) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,'PENDING')",
                        values,
                    )
                    events.append(self._event_tx(conn, "TASK_CREATED", task_id,
                                                 {"status": "PENDING"}))
                elif known[task_id] != "PASS":
                    conn.execute(
                        "UPDATE tasks SET name=?,gate=?,deps_json=?,command=?,timeout_min=?,"
                        "acceptance_json=?,retry_json=?,task_json=?,updated_at=? WHERE id=?",
                        values,
                    )
            unknown_deps = {
                dep for task in plan["tasks"] for dep in task.get("deps", []) if dep not in ids
            }
            if unknown_deps:
                raise ValueError(f"unknown dependencies: {', '.join(sorted(unknown_deps))}")
            events.append(self._event_tx(conn, "PLAN_LOADED", payload={
                "plan_id": plan["plan_id"], "task_count": len(plan["tasks"])
            }))
        self._after_commit(events)

    @staticmethod
    def _validate_task(task: dict) -> None:
        required = {"id", "name", "gate", "deps", "command", "timeout_min",
                    "acceptance_tests", "retry_policy"}
        missing = required - set(task)
        if missing:
            raise ValueError(f"task missing keys: {', '.join(sorted(missing))}")
        if not isinstance(task["deps"], list) or not isinstance(task["acceptance_tests"], list):
            raise ValueError(f"task {task['id']}: deps and acceptance_tests must be lists")

    def _row_to_task(self, row: sqlite3.Row) -> dict:
        task = json.loads(row["task_json"])
        task.update({
            "status": row["status"], "attempts": row["attempts"],
            "pid": row["pid"], "log_path": row["log_path"],
            "started_at": row["started_at"], "finished_at": row["finished_at"],
            "retry_at": row["retry_at"], "failure_reason": row["failure_reason"],
            "lock_owner": row["lock_owner"], "updated_at": row["updated_at"],
        })
        return task

    def list_tasks(self, statuses: set[str] | None = None) -> list[dict]:
        sql = "SELECT * FROM tasks"
        params: list[Any] = []
        if statuses:
            marks = ",".join("?" for _ in statuses)
            sql += f" WHERE status IN ({marks})"
            params.extend(sorted(statuses))
        sql += " ORDER BY rowid"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_task(self, task_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def transition(self, task_id: str, new_status: str, *,
                   expected: str | set[str] | None = None,
                   fields: dict | None = None,
                   event_type: str = "TASK_TRANSITION") -> dict:
        if new_status not in TASK_STATES:
            raise ValueError(f"invalid task state: {new_status}")
        events: list[dict] = []
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            old = row["status"]
            expected_set = {expected} if isinstance(expected, str) else expected
            if expected_set is not None and old not in expected_set:
                raise ValueError(f"task {task_id} is {old}, expected {sorted(expected_set)}")
            if new_status != old and new_status not in TRANSITIONS[old]:
                raise ValueError(f"invalid transition {old} -> {new_status}")
            updates = {"status": new_status, "updated_at": utc_now(), **(fields or {})}
            allowed = {"status", "attempts", "pid", "log_path", "started_at",
                       "finished_at", "retry_at", "failure_reason", "lock_owner",
                       "updated_at"}
            if set(updates) - allowed:
                raise ValueError("unsupported task update field")
            assignments = ",".join(f"{key}=?" for key in updates)
            conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                         [*updates.values(), task_id])
            events.append(self._event_tx(conn, event_type, task_id,
                                         {"from": old, "to": new_status,
                                          **(fields or {})}))
            result = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        self._after_commit(events)
        return self._row_to_task(result)

    def claim_task(self, task_id: str, owner: str) -> dict | None:
        events: list[dict] = []
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None or row["status"] not in {"READY", "APPROVED"}:
                return None
            old = row["status"]
            now = utc_now()
            conn.execute(
                "UPDATE tasks SET status='RUNNING',attempts=attempts+1,lock_owner=?,"
                "started_at=?,finished_at=NULL,pid=NULL,failure_reason=NULL,updated_at=? "
                "WHERE id=?",
                (owner, now, now, task_id),
            )
            events.append(self._event_tx(conn, "TASK_CLAIMED", task_id,
                                         {"from": old, "to": "RUNNING", "owner": owner}))
            result = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        self._after_commit(events)
        return self._row_to_task(result)

    def set_process(self, task_id: str, pid: int, log_path: str) -> None:
        events: list[dict] = []
        with self.transaction() as conn:
            conn.execute("UPDATE tasks SET pid=?,log_path=?,updated_at=? WHERE id=?",
                         (pid, log_path, utc_now(), task_id))
            events.append(self._event_tx(conn, "PROCESS_STARTED", task_id,
                                         {"pid": pid, "log_path": log_path}))
        self._after_commit(events)

    def record_event(self, event_type: str, task_id: str | None = None,
                     payload: dict | None = None) -> dict:
        with self.transaction() as conn:
            event = self._event_tx(conn, event_type, task_id, payload)
        self._after_commit([event])
        return event

    def events(self, after_seq: int = 0, limit: int = 1000) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?", (after_seq, limit)
            ).fetchall()
        return [{"seq": row["seq"], "timestamp": row["timestamp"],
                 "event_type": row["event_type"], "task_id": row["task_id"],
                 "payload": json.loads(row["payload_json"])} for row in rows]

    def set_control_state(self, state: str) -> None:
        if state not in CONTROL_STATES:
            raise ValueError(f"invalid control state: {state}")
        events: list[dict] = []
        with self.transaction() as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key='control_state'").fetchone()
            old = json.loads(row["value"]) if row else "RUNNING"
            conn.execute(
                "INSERT INTO metadata(key,value) VALUES('control_state',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(state),),
            )
            events.append(self._event_tx(conn, "CONTROL_STATE", payload={
                "from": old, "to": state
            }))
        self._after_commit(events)

    def control_state(self) -> str:
        return str(self.get_metadata("control_state", "RUNNING"))

    def heartbeat(self, owner: str, pid: int, detail: dict | None = None) -> None:
        import time
        stamp = time.time()
        payload = {"owner": owner, "pid": pid, "timestamp": stamp,
                   "detail": detail or {}}
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO heartbeats(owner,pid,timestamp,detail_json) VALUES(?,?,?,?) "
                "ON CONFLICT(owner) DO UPDATE SET pid=excluded.pid,timestamp=excluded.timestamp,"
                "detail_json=excluded.detail_json",
                (owner, pid, stamp, json.dumps(detail or {}, sort_keys=True)),
            )
        tmp = self.heartbeat_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.heartbeat_path)

    def get_heartbeat(self, owner: str = "controller") -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM heartbeats WHERE owner=?", (owner,)).fetchone()
        if row is None:
            return None
        return {"owner": row["owner"], "pid": row["pid"],
                "timestamp": row["timestamp"], "detail": json.loads(row["detail_json"])}

    def create_approval(self, approval_id: str, task_id: str,
                        expires_at: float | None) -> None:
        events: list[dict] = []
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO approvals(approval_id,task_id,status,created_at,expires_at) "
                "VALUES(?,?,'PENDING',?,?)",
                (approval_id, task_id, utc_now(), expires_at),
            )
            row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None or row["status"] != "READY":
                raise ValueError(f"task {task_id} is not READY")
            conn.execute("UPDATE tasks SET status='WAITING_APPROVAL',updated_at=? WHERE id=?",
                         (utc_now(), task_id))
            events.append(self._event_tx(conn, "APPROVAL_REQUESTED", task_id,
                                         {"approval_id": approval_id,
                                          "expires_at": expires_at}))
        self._after_commit(events)

    def decide_approval(self, approval_id: str, decision: str,
                        reason: str = "") -> dict:
        decision = decision.upper()
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("decision must be APPROVED or REJECTED")
        events: list[dict] = []
        with self.transaction() as conn:
            approval = conn.execute(
                "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
            if approval is None:
                raise KeyError(approval_id)
            if approval["status"] != "PENDING":
                raise ValueError(f"approval already {approval['status']}")
            task_id = approval["task_id"]
            task = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
            if task["status"] != "WAITING_APPROVAL":
                raise ValueError(f"task {task_id} is {task['status']}")
            conn.execute(
                "UPDATE approvals SET status=?,reason=?,decided_at=? WHERE approval_id=?",
                (decision, reason, utc_now(), approval_id),
            )
            conn.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?",
                         (decision, utc_now(), task_id))
            events.append(self._event_tx(conn, f"APPROVAL_{decision}", task_id,
                                         {"approval_id": approval_id, "reason": reason}))
            result = dict(approval)
            result.update({"status": decision, "reason": reason})
        self._after_commit(events)
        return result

    def pending_approvals(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status='PENDING' ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def status_summary(self) -> dict:
        tasks = self.list_tasks()
        counts: dict[str, int] = {}
        for task in tasks:
            counts[task["status"]] = counts.get(task["status"], 0) + 1
        return {"project_root": str(self.project_root),
                "control_state": self.control_state(), "counts": counts,
                "tasks": tasks, "pending_approvals": self.pending_approvals(),
                "heartbeat": self.get_heartbeat()}

    def export_snapshots(self) -> dict[str, str]:
        snapshot = self.status_summary()
        json_path = self.execution_dir / "state.snapshot.json"
        yaml_path = self.execution_dir / "state.snapshot.yaml"
        csv_path = self.execution_dir / "tasks.snapshot.csv"
        self._atomic_write(json_path, json.dumps(snapshot, indent=2, sort_keys=True))
        if yaml is not None:
            self._atomic_write(yaml_path, yaml.safe_dump(snapshot, sort_keys=False))
        else:
            self._atomic_write(yaml_path, json.dumps(snapshot, indent=2))
        tmp = csv_path.with_suffix(".tmp")
        fields = ["id", "name", "gate", "status", "attempts", "pid", "log_path",
                  "started_at", "finished_at", "failure_reason"]
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for task in snapshot["tasks"]:
                writer.writerow({key: task.get(key) for key in fields})
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, csv_path)
        return {"json": str(json_path), "yaml": str(yaml_path), "csv": str(csv_path)}

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
