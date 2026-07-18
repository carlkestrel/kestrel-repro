"""OSTAR state persistence via SQLite with atomic checkpoints.

Directory layout::

    soak/
    ├── soak_manifest.json        # top-level run metadata
    ├── current_state.json       # latest state snapshot (atomic write)
    ├── heartbeat.json           # last heartbeat (atomic write)
    ├── soak.sqlite3             # SQLite WAL journal
    ├── nodes/
    │   └── SOAK-BUG-<seq>.json # per-repair-node result
    ├── failures/
    │   └── FAIL-<seq>.json     # captured failure evidence
    ├── repairs/
    │   └── <bug_id>/           # per-bug repair evidence
    ├── logs/
    │   └── <run_id>/           # per-run log files
    ├── metrics/
    │   └── <run_id>.csv        # time-series resource metrics
    ├── checkpoints/
    │   └── ckpt_<seq>.json     # atomic state checkpoints
    └── reports/
        ├── overnight_summary.md
        ├── overnight_summary.html
        └── ...
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import constants as _C


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Atomic file helpers
# ─────────────────────────────────────────────────────────────────────────────

def _atomic_write_json(path: Path, data: dict) -> None:
    """Write ``data`` to ``path`` atomically (rename from tmp)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2, sort_keys=True))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ─────────────────────────────────────────────────────────────────────────────
# SoakStateStore
# ─────────────────────────────────────────────────────────────────────────────

class SoakStateStore:
    """SQLite-backed + JSON-snapshot OSTAR state store."""

    def __init__(self, soak_root: str | Path):
        self.soak_root = Path(soak_root).resolve()
        self.nodes_dir = self.soak_root / "nodes"
        self.failures_dir = self.soak_root / "failures"
        self.repairs_dir = self.soak_root / "repairs"
        self.logs_dir = self.soak_root / "logs"
        self.metrics_dir = self.soak_root / "metrics"
        self.checkpoints_dir = self.soak_root / "checkpoints"
        self.reports_dir = self.soak_root / "reports"
        for d in (self.nodes_dir, self.failures_dir, self.repairs_dir,
                  self.logs_dir, self.metrics_dir, self.checkpoints_dir,
                  self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.db_path = self.soak_root / "soak.sqlite3"
        self.manifest_path = self.soak_root / "soak_manifest.json"
        self.state_path = self.soak_root / "current_state.json"
        self.heartbeat_path = self.soak_root / "heartbeat.json"
        self._local = threading.local()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
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

    def _init_db(self) -> None:
        ddl = [
            "CREATE TABLE IF NOT EXISTS metadata ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS soak_runs ("
            "run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,"
            "ended_at TEXT, status TEXT NOT NULL,"
            "config_json TEXT NOT NULL, verdict TEXT,"
            "duration_seconds REAL, cycles_completed INTEGER,"
            "total_repairs INTEGER, rollback_count INTEGER,"
            "consecutive_crashes INTEGER, updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS cycles ("
            "cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "run_id TEXT NOT NULL, sequence INTEGER NOT NULL,"
            "started_at TEXT NOT NULL, ended_at TEXT,"
            "status TEXT NOT NULL, exit_reason TEXT,"
            "bug_count INTEGER, repair_count INTEGER,"
            "FOREIGN KEY(run_id) REFERENCES soak_runs(run_id))",
            "CREATE TABLE IF NOT EXISTS bugs ("
            "bug_id TEXT PRIMARY KEY,"
            "run_id TEXT NOT NULL,"
            "fingerprint TEXT NOT NULL,"
            "error_class TEXT NOT NULL,"
            "first_seen_at TEXT NOT NULL,"
            "last_seen_at TEXT NOT NULL,"
            "occurrences INTEGER NOT NULL,"
            "consecutive_failures INTEGER NOT NULL,"
            "auto_repair_class TEXT,"
            "is_blocked INTEGER NOT NULL,"
            "FOREIGN KEY(run_id) REFERENCES soak_runs(run_id))",
            "CREATE TABLE IF NOT EXISTS repairs ("
            "repair_id TEXT PRIMARY KEY,"
            "bug_id TEXT NOT NULL,"
            "run_id TEXT NOT NULL,"
            "attempt INTEGER NOT NULL,"
            "started_at TEXT NOT NULL,"
            "ended_at TEXT,"
            "status TEXT NOT NULL,"
            "patch_json TEXT,"
            "regression_test_passed INTEGER,"
            "target_test_passed INTEGER,"
            "notes TEXT,"
            "FOREIGN KEY(bug_id) REFERENCES bugs(bug_id),"
            "FOREIGN KEY(run_id) REFERENCES soak_runs(run_id))",
            "CREATE TABLE IF NOT EXISTS ci_results ("
            "result_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "run_id TEXT NOT NULL, cycle_id INTEGER,"
            "suite_name TEXT NOT NULL,"
            "passed INTEGER NOT NULL, failed INTEGER NOT NULL,"
            "skipped INTEGER NOT NULL,"
            "duration_seconds REAL,"
            "flaky INTEGER NOT NULL,"
            "ran_at TEXT NOT NULL,"
            "FOREIGN KEY(run_id) REFERENCES soak_runs(run_id))",
            "CREATE TABLE IF NOT EXISTS events ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT,"
            "timestamp TEXT NOT NULL,"
            "event_type TEXT NOT NULL,"
            "payload_json TEXT NOT NULL)",
            "CREATE INDEX IF NOT EXISTS idx_cycles_run ON cycles(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_bugs_run ON bugs(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_repairs_bug ON repairs(bug_id)",
            "CREATE INDEX IF NOT EXISTS idx_ci_run ON ci_results(run_id)",
        ]
        with self.transaction() as conn:
            for stmt in ddl:
                conn.execute(stmt)

    # ─────────────────────────────────────────────────────────────────────
    # High-level API used by soak_engine
    # ─────────────────────────────────────────────────────────────────────

    def init_run(self, config: dict) -> str:
        """Create a new soak run, return its run_id."""
        run_id = f"{_C.DEFAULT_SOAK_RUN_ID_PREFIX}_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        config_json = json.dumps(config, sort_keys=True)
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO soak_runs(run_id,started_at,status,config_json,"
                "updated_at) VALUES(?,?,?,?,?)",
                (run_id, now, "INIT", config_json, now),
            )
            self._event_tx(conn, "RUN_INIT", {"run_id": run_id})
        self._write_manifest(run_id, config)
        self._write_state({"status": "INIT", "run_id": run_id, "config": config})
        return run_id

    def start_run(self, run_id: str) -> None:
        self._transition_run(run_id, "RUNNING")
        self._event("RUN_STARTED", {"run_id": run_id})

    def record_cycle(
        self,
        run_id: str,
        seq: int,
        status: str,
        *,
        ended_at: str | None = None,
        exit_reason: str | None = None,
        bug_count: int = 0,
        repair_count: int = 0,
    ) -> int:
        now = _utc_now()
        with self.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO cycles(run_id,sequence,started_at,ended_at,status,"
                "exit_reason,bug_count,repair_count) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (run_id, seq, now, ended_at or now, status,
                 exit_reason, bug_count, repair_count),
            )
            cycle_id = cur.lastrowid
            self._event_tx(conn, "CYCLE_COMPLETE", {
                "run_id": run_id, "cycle_id": cycle_id, "sequence": seq,
                "status": status, "exit_reason": exit_reason,
                "bug_count": bug_count, "repair_count": repair_count,
            })
        return cycle_id

    def record_ci_result(
        self,
        run_id: str,
        cycle_id: int | None,
        suite_name: str,
        passed: int,
        failed: int,
        skipped: int,
        duration_seconds: float,
        flaky: bool,
    ) -> None:
        now = _utc_now()
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO ci_results(run_id,cycle_id,suite_name,passed,failed,"
                "skipped,duration_seconds,flaky,ran_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, cycle_id, suite_name, passed, failed, skipped,
                 duration_seconds, int(flaky), now),
            )

    def upsert_bug(
        self,
        run_id: str,
        fingerprint: str,
        error_class: str,
    ) -> str:
        """Insert or update a bug entry. Returns bug_id."""
        now = _utc_now()
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT bug_id,occurrences,consecutive_failures FROM bugs "
                "WHERE run_id=? AND fingerprint=?",
                (run_id, fingerprint),
            ).fetchone()
            if existing:
                bug_id = existing["bug_id"]
                conn.execute(
                    "UPDATE bugs SET last_seen_at=?,occurrences=occurrences+1,"
                    "consecutive_failures=consecutive_failures+1 "
                    "WHERE bug_id=?",
                    (now, bug_id),
                )
            else:
                bug_id = f"SOAK-BUG-{uuid.uuid4().hex[:8].upper()}"
                is_blocked = int(error_class in _C.BLOCKED_CLASSES)
                conn.execute(
                    "INSERT INTO bugs(run_id,bug_id,fingerprint,error_class,"
                    "first_seen_at,last_seen_at,occurrences,"
                    "consecutive_failures,is_blocked) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (run_id, bug_id, fingerprint, error_class, now, now, 1, 1,
                     is_blocked),
                )
                self._event_tx(conn, "BUG_DETECTED", {
                    "run_id": run_id, "bug_id": bug_id,
                    "error_class": error_class,
                })
        return bug_id

    def record_repair(
        self,
        run_id: str,
        bug_id: str,
        attempt: int,
        patch: dict | None,
        status: str,
        *,
        ended_at: str | None = None,
        target_test_passed: bool | None = None,
        regression_passed: bool | None = None,
        notes: str | None = None,
    ) -> str:
        repair_id = f"REPAIR-{uuid.uuid4().hex[:8].upper()}"
        now = _utc_now()
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO repairs(repair_id,bug_id,run_id,attempt,started_at,"
                "ended_at,status,patch_json,target_test_passed,"
                "regression_test_passed,notes) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (repair_id, bug_id, run_id, attempt, now,
                 ended_at or now, status,
                 json.dumps(patch) if patch else None,
                 int(target_test_passed) if target_test_passed is not None else None,
                 int(regression_passed) if regression_passed is not None else None,
                 notes),
            )
            self._event_tx(conn, "REPAIR_ATTEMPT", {
                "run_id": run_id, "bug_id": bug_id,
                "repair_id": repair_id, "attempt": attempt,
                "status": status,
            })
        return repair_id

    def get_bug(self, bug_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM bugs WHERE bug_id=?", (bug_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_bugs_by_fingerprint(self, run_id: str, fingerprint: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bugs WHERE run_id=? AND fingerprint=?",
                (run_id, fingerprint),
            ).fetchall()
        return [dict(r) for r in rows]

    def reset_bug_consecutive_failures(self, bug_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE bugs SET consecutive_failures=0 WHERE bug_id=?",
                (bug_id,),
            )

    def complete_run(
        self,
        run_id: str,
        verdict: str,
        *,
        ended_at: str | None = None,
    ) -> None:
        now = ended_at or _utc_now()
        with self.transaction() as conn:
            meta = conn.execute(
                "SELECT started_at,duration_seconds FROM soak_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            duration = None
            if meta:
                start = datetime.fromisoformat(meta["started_at"])
                end = datetime.fromisoformat(now)
                duration = (end - start).total_seconds()
            cyc = conn.execute(
                "SELECT COUNT(*) as cnt FROM cycles WHERE run_id=?",
                (run_id,),
            ).fetchone()
            repl = conn.execute(
                "SELECT COUNT(*) as cnt FROM repairs WHERE run_id=? AND status='PASS'",
                (run_id,),
            ).fetchone()
            rlbk = conn.execute(
                "SELECT COUNT(*) as cnt FROM repairs WHERE run_id=? AND status='ROLLBACK'",
                (run_id,),
            ).fetchone()
            conn.execute(
                "UPDATE soak_runs SET status=?,verdict=?,ended_at=?,"
                "duration_seconds=?,cycles_completed=?,total_repairs=?,"
                "rollback_count=?,updated_at=? WHERE run_id=?",
                ("COMPLETED", verdict, now, duration,
                 (cyc["cnt"] if cyc else 0),
                 (repl["cnt"] if repl else 0),
                 (rlbk["cnt"] if rlbk else 0),
                 now, run_id),
            )
            self._event_tx(conn, "RUN_COMPLETE", {
                "run_id": run_id, "verdict": verdict,
            })
        self._write_state({"status": "COMPLETED", "run_id": run_id,
                           "verdict": verdict})

    def abort_run(self, run_id: str, reason: str) -> None:
        now = _utc_now()
        with self.transaction() as conn:
            conn.execute(
                "UPDATE soak_runs SET status=?,verdict=?,ended_at=?,updated_at=? "
                "WHERE run_id=?",
                ("FAILED", _C.VERDICT_FAILED_UNRESOLVED, now, now, run_id),
            )
            self._event_tx(conn, "RUN_ABORTED", {
                "run_id": run_id, "reason": reason,
            })
        self._write_state({"status": "FAILED", "run_id": run_id, "reason": reason})

    def pause_run(self, run_id: str) -> None:
        self._transition_run(run_id, "PAUSED")
        self._event("RUN_PAUSED", {"run_id": run_id})

    def resume_run(self, run_id: str) -> None:
        self._transition_run(run_id, "RUNNING")
        self._event("RUN_RESUMED", {"run_id": run_id})

    def heartbeat(self, run_id: str, pid: int, detail: dict | None = None) -> None:
        now = _utc_now()
        payload = {
            "run_id": run_id, "pid": pid,
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "utc": now,
            "detail": detail or {},
        }
        _atomic_write_json(self.heartbeat_path, payload)

    def write_node_result(self, node_id: str, result: dict) -> None:
        path = self.nodes_dir / f"{node_id}.json"
        _atomic_write_json(path, result)

    def write_failure_evidence(self, seq: int, failure: dict) -> str:
        path = self.failures_dir / f"FAIL-{seq:04d}.json"
        _atomic_write_json(path, failure)
        return str(path)

    def write_cycle_metrics(self, run_id: str, cycle_seq: int,
                            metrics: dict) -> None:
        path = self.metrics_dir / f"{run_id}_cycle_{cycle_seq:04d}.json"
        _atomic_write_json(path, metrics)

    def write_checkpoint(self, state: dict, seq: int) -> Path:
        path = self.checkpoints_dir / f"ckpt_{seq:06d}.json"
        _atomic_write_json(path, state)
        return path

    def latest_checkpoint(self) -> Path | None:
        cks = sorted(self.checkpoints_dir.glob("ckpt_*.json"))
        return cks[-1] if cks else None

    def get_run(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM soak_runs WHERE run_id=?", (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_cycles(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM cycles WHERE run_id=? ORDER BY sequence",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_bugs(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bugs WHERE run_id=? ORDER BY first_seen_at",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_repairs(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM repairs WHERE run_id=? ORDER BY started_at",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_ci_summary(self, run_id: str) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT suite_name, SUM(passed) as total_pass,"
                "SUM(failed) as total_fail,"
                "SUM(skipped) as total_skip,"
                "SUM(CASE WHEN flaky=1 THEN 1 ELSE 0 END) as flaky_count,"
                "COUNT(*) as runs "
                "FROM ci_results WHERE run_id=? GROUP BY suite_name",
                (run_id,),
            ).fetchall()
        return {r["suite_name"]: dict(r) for r in rows}

    def events(self, after_seq: int = 0, limit: int = 1000) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?",
                (after_seq, limit),
            ).fetchall()
        return [{"seq": r["seq"], "timestamp": r["timestamp"],
                 "event_type": r["event_type"],
                 "payload": json.loads(r["payload_json"])}
                for r in rows]

    def status_summary(self) -> dict:
        run_ids = self._get_active_runs()
        if not run_ids:
            return {"status": "IDLE", "active_runs": []}
        run_id = run_ids[-1]
        run = self.get_run(run_id)
        if not run:
            return {"status": "IDLE", "active_runs": []}
        bugs = self.get_bugs(run_id)
        repairs = self.get_repairs(run_id)
        cycles = self.get_cycles(run_id)
        return {
            "status": run["status"],
            "run_id": run_id,
            "started_at": run["started_at"],
            "duration_seconds": run.get("duration_seconds"),
            "cycles_completed": run.get("cycles_completed", len(cycles)),
            "total_repairs": run.get("total_repairs", len(repairs)),
            "rollback_count": run.get("rollback_count", 0),
            "verdict": run.get("verdict"),
            "active_bugs": len([b for b in bugs if b["consecutive_failures"] > 0]),
            "total_bugs": len(bugs),
            "ci_summary": self.get_ci_summary(run_id),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    def _transition_run(self, run_id: str, status: str) -> None:
        now = _utc_now()
        with self.transaction() as conn:
            conn.execute(
                "UPDATE soak_runs SET status=?,updated_at=? WHERE run_id=?",
                (status, now, run_id),
            )
        self._write_state({"status": status, "run_id": run_id})

    def _event(self, event_type: str, payload: dict | None = None) -> None:
        with self.transaction() as conn:
            self._event_tx(conn, event_type, payload)

    def _event_tx(self, conn: sqlite3.Connection, event_type: str,
                  payload: dict | None = None) -> dict:
        now = _utc_now()
        payload = payload or {}
        cur = conn.execute(
            "INSERT INTO events(timestamp,event_type,payload_json) VALUES(?,?,?)",
            (now, event_type, json.dumps(payload, sort_keys=True)),
        )
        return {"seq": cur.lastrowid, "timestamp": now,
                "event_type": event_type, "payload": payload}

    def _write_state(self, state: dict) -> None:
        _atomic_write_json(self.state_path, state)

    def _write_manifest(self, run_id: str, config: dict) -> None:
        manifest = {
            "run_id": run_id,
            "version": "0.1.0",
            "config": config,
            "created_at": _utc_now(),
        }
        _atomic_write_json(self.manifest_path, manifest)

    def _get_active_runs(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id FROM soak_runs WHERE status "
                "IN ('INIT','RUNNING','PAUSED','RESUMING','REHEARSING') "
                "ORDER BY started_at DESC",
            ).fetchall()
        return [r["run_id"] for r in rows]
