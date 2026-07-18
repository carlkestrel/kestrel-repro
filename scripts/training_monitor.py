#!/usr/bin/env python3
"""
training_monitor.py — Live training health monitor for dl-paper-repro.

Watches an in-progress training run and classifies it into one of nine
statuses based on 15 collected metrics. Designed to run side-by-side with
any training script (no in-process hooks required) — it samples process
state, GPU state (via `nvidia-smi` if available), and the run's log file.

Usage:
    from training_monitor import TrainingMonitor, Status
    m = TrainingMonitor(run_id="r-001", log_path="experiments/r-001/logs/train.log")
    m.start()
    while training_is_running:
        m.sample()           # call this from your training loop, or use watch()
        snap = m.snapshot()   # dict with 15 metrics + classified status
    m.stop()

    # Or CLI mode:
    python training_monitor.py --run-id r-001 --log experiments/r-001/logs/train.log check

The module also emits telemetry via `write_telemetry()` (P4_T06):
    experiments/<run_id>/TELEMETRY.jsonl          # one row per sample
    experiments/<run_id>/TELEMETRY_STAGES.jsonl   # one row per detected stage transition
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    """Nine canonical run states (P4_T01 acceptance)."""
    OK = "OK"
    STALLED = "STALLED"
    DIVERGED = "DIVERGED"
    OOM = "OOM"
    NAN = "NAN"
    CKPT_STUCK = "CKPT_STUCK"
    CLASS_COLLAPSE = "CLASS_COLLAPSE"
    OVERHEAT = "OVERHEAT"
    UNKNOWN = "UNKNOWN"


# Order matters for severity reporting (first match wins after OK).
STATUS_PRIORITY = [
    Status.NAN,
    Status.OOM,
    Status.OVERHEAT,
    Status.DIVERGED,
    Status.CLASS_COLLAPSE,
    Status.CKPT_STUCK,
    Status.STALLED,
    Status.UNKNOWN,
]


@dataclass
class Metrics:
    """The 15-metric snapshot. Field names match TELEMETRY.jsonl schema."""
    ts: str = ""
    gpu_util_pct: float = 0.0           # 1
    gpu_mem_used_mb: float = 0.0        # 2
    gpu_mem_peak_mb: float = 0.0        # 3
    gpu_temp_c: float = 0.0             # 4
    cpu_pct: float = 0.0                # 5
    ram_used_mb: float = 0.0            # 6
    disk_used_pct: float = 0.0          # 7
    step_time_s: float = 0.0            # 8
    loss: float = 0.0                   # 9
    grad_norm: float = 0.0              # 10
    has_nan: bool = False               # 11
    has_oom: bool = False               # 12
    last_ckpt_age_s: float = -1.0       # 13
    class_distribution_entropy: float = 0.0  # 14 (high = healthy, low = collapse)
    log_keyword_hits: dict = field(default_factory=dict)  # 15
    status: str = Status.UNKNOWN.value  # classification
    run_id: str = ""
    stage: str = ""                     # free-form stage name (data, fwd, bwd, optim, ckpt, eval)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: str, timeout: float = 2.0) -> str:
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return out.stdout if out.returncode == 0 else ""
    except Exception:
        return ""


def _gpu_metrics() -> tuple[float, float, float, float]:
    """Return (util%, mem_used_mb, mem_peak_mb, temp_c) via nvidia-smi, or (0,0,0,0)."""
    out = _run(
        "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu "
        "--format=csv,noheader,nounits"
    )
    if not out:
        return 0.0, 0.0, 0.0, 0.0
    try:
        line = out.strip().splitlines()[0]
        util, mem_used, mem_total, temp = [float(x.strip()) for x in line.split(",")[:4]]
        return util, mem_used, mem_total, temp
    except Exception:
        return 0.0, 0.0, 0.0, 0.0


def _cpu_metrics() -> tuple[float, float]:
    try:
        import psutil  # type: ignore
        return float(psutil.cpu_percent(interval=0.0)), float(psutil.virtual_memory().used / 1024 / 1024)
    except Exception:
        return 0.0, 0.0


def _disk_metrics(path: str = "/") -> float:
    try:
        import psutil  # type: ignore
        return float(psutil.disk_usage(path).percent)
    except Exception:
        return 0.0


_KEYWORD_PATTERNS = {
    "nan_inf": re.compile(r"\b(nan|inf)\b", re.IGNORECASE),
    "oom": re.compile(r"(out of memory|cuda oom|allocat\w+ failed)", re.IGNORECASE),
    "ckpt_saved": re.compile(r"(saving checkpoint|checkpoint saved|model saved)", re.IGNORECASE),
    "diverged": re.compile(r"(diverge|loss explosion|loss spike)", re.IGNORECASE),
    "overheat": re.compile(r"(thermal throttl\w+|temperature.*critical)", re.IGNORECASE),
    "class_collapse": re.compile(r"(class collapse|all predictions.*same|predictions degenerate)", re.IGNORECASE),
}


def _scan_log_keywords(log_path: Path | None) -> dict:
    if not log_path or not log_path.exists():
        return dict.fromkeys(_KEYWORD_PATTERNS, 0)
    try:
        # Tail the last 200 lines (cheap and avoids re-reading huge files).
        text = subprocess.run(
            ["tail", "-n", "200", str(log_path)],
            capture_output=True, text=True, timeout=2.0,
        ).stdout
    except Exception:
        return dict.fromkeys(_KEYWORD_PATTERNS, 0)
    hits = {}
    for k, pat in _KEYWORD_PATTERNS.items():
        hits[k] = len(pat.findall(text))
    return hits


def _class_collapse_entropy(class_dist: dict) -> float:
    """Shannon entropy of class distribution (higher = more uniform)."""
    import math
    total = sum(class_dist.values())
    if total <= 0 or len(class_dist) <= 1:
        return 0.0
    h = 0.0
    for c in class_dist.values():
        if c > 0:
            p = c / total
            h -= p * math.log(p)
    return h


def classify(metrics: Metrics) -> Status:
    """Apply the nine-state classifier. Priority order: NAN > OOM > OVERHEAT >
    DIVERGED > CLASS_COLLAPSE > CKPT_STUCK > STALLED > UNKNOWN. OK is the
    default if no rules fire."""
    kw = metrics.log_keyword_hits or {}
    if metrics.has_nan or kw.get("nan_inf", 0) > 0:
        return Status.NAN
    if metrics.has_oom or kw.get("oom", 0) > 0:
        return Status.OOM
    if metrics.gpu_temp_c >= 85.0 or kw.get("overheat", 0) > 0:
        return Status.OVERHEAT
    if kw.get("diverged", 0) > 0:
        return Status.DIVERGED
    # Class collapse: entropy < 0.5 AND we have a distribution.
    if metrics.class_distribution_entropy > 0 and metrics.class_distribution_entropy < 0.5:
        return Status.CLASS_COLLAPSE
    # CKPT stuck: age > 30 min and step_time still flowing.
    if 0 < metrics.last_ckpt_age_s > 1800:
        return Status.CKPT_STUCK
    # Stalled: GPU util < 5% AND no recent step.
    if metrics.gpu_util_pct < 5.0 and metrics.step_time_s <= 0:
        return Status.STALLED
    if metrics.gpu_util_pct < 5.0:
        return Status.STALLED
    return Status.OK


class TrainingMonitor:
    """Sample 15 metrics + classify status. Optionally emits TELEMETRY.jsonl."""

    def __init__(
        self,
        run_id: str,
        log_path: Path | None = None,
        telemetry_dir: Path | None = None,
    ):
        self.run_id = run_id
        self.log_path = log_path
        self.telemetry_dir = telemetry_dir
        self._last_sample_ts: float | None = None
        self._stage: str = ""
        self._stage_start: float | None = None
        self._stages: list = []
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()

    # --- public API ---
    def start(self) -> None:
        self._stop_evt.clear()

    def stop(self) -> None:
        self._stop_evt.set()
        # Flush current stage, if any.
        if self._stage and self._stage_start is not None:
            self._stages.append({
                "stage": self._stage,
                "start_ts": datetime.fromtimestamp(self._stage_start, timezone.utc).isoformat(),
                "end_ts": _now_iso(),
                "duration_s": time.time() - self._stage_start,
            })
        if self.telemetry_dir is not None:
            self._flush_stages()

    def set_stage(self, name: str) -> None:
        """Mark a stage transition (e.g., 'fwd' → 'bwd'). Writes a row to
        TELEMETRY_STAGES.jsonl."""
        now = time.time()
        with self._lock:
            if self._stage and self._stage_start is not None:
                self._stages.append({
                    "stage": self._stage,
                    "start_ts": datetime.fromtimestamp(self._stage_start, timezone.utc).isoformat(),
                    "end_ts": _now_iso(),
                    "duration_s": now - self._stage_start,
                })
            self._stage = name
            self._stage_start = now
        if self.telemetry_dir is not None:
            self._flush_stages()

    def sample(
        self,
        *,
        loss: float = 0.0,
        grad_norm: float = 0.0,
        class_dist: dict | None = None,
        ckpt_mtime: float | None = None,
        step_time_s: float = 0.0,
    ) -> Metrics:
        """Take one snapshot. Returns the classified Metrics dataclass."""
        util, mem_used, mem_peak, temp = _gpu_metrics()
        cpu_pct, ram_mb = _cpu_metrics()
        disk_pct = _disk_metrics()
        kw = _scan_log_keywords(self.log_path)
        ent = _class_collapse_entropy(class_dist or {})
        ckpt_age = (time.time() - ckpt_mtime) if ckpt_mtime else -1.0
        m = Metrics(
            ts=_now_iso(),
            gpu_util_pct=util,
            gpu_mem_used_mb=mem_used,
            gpu_mem_peak_mb=mem_peak,
            gpu_temp_c=temp,
            cpu_pct=cpu_pct,
            ram_used_mb=ram_mb,
            disk_used_pct=disk_pct,
            step_time_s=step_time_s,
            loss=loss,
            grad_norm=grad_norm,
            has_nan=(loss != loss) or (grad_norm != grad_norm),  # NaN check
            has_oom=(kw.get("oom", 0) > 0),
            last_ckpt_age_s=ckpt_age,
            class_distribution_entropy=ent,
            log_keyword_hits=kw,
            status=Status.UNKNOWN.value,
            run_id=self.run_id,
            stage=self._stage,
        )
        m.status = classify(m).value
        self._last_sample_ts = time.time()
        if self.telemetry_dir is not None:
            self._write_telemetry(m)
        return m

    def snapshot(self) -> dict:
        return asdict(self.sample())

    # --- telemetry writers (P4_T06) ---
    def _write_telemetry(self, m: Metrics) -> None:
        assert self.telemetry_dir is not None
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        with open(self.telemetry_dir / "TELEMETRY.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(m), ensure_ascii=False) + "\n")

    def _flush_stages(self) -> None:
        assert self.telemetry_dir is not None
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        with open(self.telemetry_dir / "TELEMETRY_STAGES.jsonl", "a", encoding="utf-8") as f:
            for row in self._stages:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._stages.clear()


# --- Module-level helpers used by CLI ---

def write_telemetry(
    metrics: Metrics,
    telemetry_dir: Path,
    stages: list | None = None,
) -> None:
    """Stand-alone writer for callers that don't want a TrainingMonitor instance."""
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    with open(telemetry_dir / "TELEMETRY.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(metrics), ensure_ascii=False) + "\n")
    if stages:
        with open(telemetry_dir / "TELEMETRY_STAGES.jsonl", "a", encoding="utf-8") as f:
            for row in stages:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _cli_check(args: argparse.Namespace) -> int:
    m = TrainingMonitor(
        run_id=args.run_id,
        log_path=Path(args.log) if args.log else None,
        telemetry_dir=Path(args.telemetry_dir) if args.telemetry_dir else None,
    )
    m.start()
    snap = m.sample(loss=args.loss or 0.0)
    print(json.dumps(snap, indent=2, ensure_ascii=False))
    return 0 if snap["status"] == Status.OK.value else 2


def _cli_watch(args: argparse.Namespace) -> int:
    m = TrainingMonitor(
        run_id=args.run_id,
        log_path=Path(args.log) if args.log else None,
        telemetry_dir=Path(args.telemetry_dir) if args.telemetry_dir else None,
    )
    m.start()
    while not m._stop_evt.is_set():
        snap = m.sample()
        print(json.dumps({"ts": snap["ts"], "status": snap["status"]}, ensure_ascii=False))
        time.sleep(args.interval)
    m.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="dl-paper-repro training monitor")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_chk = sub.add_parser("check", help="Take one sample and print JSON")
    p_chk.add_argument("--run-id", required=True)
    p_chk.add_argument("--log", default="")
    p_chk.add_argument("--telemetry-dir", default="")
    p_chk.add_argument("--loss", type=float, default=0.0)
    p_chk.set_defaults(func=_cli_check)

    p_w = sub.add_parser("watch", help="Continuously sample at fixed interval")
    p_w.add_argument("--run-id", required=True)
    p_w.add_argument("--log", default="")
    p_w.add_argument("--telemetry-dir", default="")
    p_w.add_argument("--interval", type=float, default=10.0)
    p_w.set_defaults(func=_cli_watch)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
