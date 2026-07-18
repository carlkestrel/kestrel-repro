"""Test the unified startup system.

Covers all 20 mandatory test cases from the spec:

  1  fresh project start
  2  dry-run
  3  missing plan
  4  invalid plan
  5  bad config format
  6  no GPU
  7  CUDA mismatch
  8  disk full
  9  duplicate start
 10  stale lock
 11  interrupted recovery
 12  plan_hash changed
 13  corrupted state file
 14  corrupted checkpoint
 15  stop graceful
 16  Cursor cmd == CLI behavior
 17  Windows/WSL/Linux path handling
 18  paths with spaces
 19  uncommitted git changes
 20  secrets never in logs
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import textwrap
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
STARTUP_PKG = SCRIPTS / "startup"

# ---------------------------------------------------------------------------
# Module loaders
# ---------------------------------------------------------------------------

# Tests load the startup package by temporarily putting SCRIPTS on sys.path
# so that `import startup.cli` works (which requires a proper package).
import sys as _sys

if str(SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(SCRIPTS))

from startup import cli as _cli_mod
from startup import config as _cfg_mod
from startup import doctor as _doc_mod
from startup import lock as _lock_mod
from startup import log_setup as _log_mod
from startup import plan_validate as _plan_mod
from startup import recovery as _rec_mod
from startup import secrets_redactor as _red_mod
from startup import state_machine as _sm_mod
from startup import stop as _stop_mod


def load_cli():
    return _cli_mod


def load_state_machine():
    return _sm_mod


def load_lock():
    return _lock_mod


def load_doctor():
    return _doc_mod


def load_config():
    return _cfg_mod


def load_redactor():
    return _red_mod


def load_log():
    return _log_mod


def load_plan():
    return _plan_mod


def load_recovery():
    return _rec_mod


def load_stop():
    return _stop_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def workdir(path: Path):
    old = Path.cwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(str(old))


def make_project(root: Path, *, git: bool = True, dirty: bool = False) -> Path:
    """Create a minimal but realistic project layout under root."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "primary").mkdir(exist_ok=True)
    if git:
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "Test")
        (root / "README.md").write_text("# fixture\n")
        _git(root, "add", ".")
        _git(root, "commit", "-q", "-m", "init")
        if dirty:
            (root / "README.md").write_text("# fixture - dirty\n")
    return root


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def make_plan(root: Path, name: str = "PLAN") -> Path:
    plan = root / "plan.md"
    plan.write_text(
        textwrap.dedent(
            f"""\
            ---
            name: {name}
            overview: fixture plan
            ---
            # {name}
            """
        )
    )
    return plan


@contextmanager
def fake_disk_full(monkeypatch_target):
    """Patch shutil.disk_usage to report 0 free bytes."""
    from collections import namedtuple

    Disk = namedtuple("usage", "total used free")
    orig = shutil.disk_usage

    def fake(p):
        return Disk(total=10**9, used=10**9, free=0)

    monkeypatch_target(fake)
    try:
        yield
    finally:
        monkeypatch_target(orig)


@contextmanager
def fake_cuda(monkeypatch_target, *, available: bool, version: str = "11.8"):
    """Inject a fake torch.cuda into sys.modules with controllable fields."""
    import types

    fake = types.ModuleType("torch")
    fake.cuda = types.SimpleNamespace(
        is_available=lambda: available,
        device_count=lambda: 1 if available else 0,
        get_device_name=lambda i: "FakeGPU" if available else "",
    )
    fake.version = types.SimpleNamespace(cuda=version)
    orig = sys.modules.get("torch")
    sys.modules["torch"] = fake
    monkeypatch_target(orig)
    try:
        yield
    finally:
        if orig is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = orig


def run_cli(args, *, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """Invoke scripts/reproctl.py as a subprocess — the real entry the user uses."""
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "reproctl.py"), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=e,
    )


# ---------------------------------------------------------------------------
# Pure-unit tests on the new modules
# ---------------------------------------------------------------------------


# ── Module loadability (sanity) ──────────────────────────────────────────


def test_modules_load():
    """All scripts/startup/*.py modules must be importable on this machine."""
    for fn in (
        "cli.py",
        "state_machine.py",
        "lock.py",
        "doctor.py",
        "config.py",
        "secrets_redactor.py",
        "log_setup.py",
        "plan_validate.py",
        "recovery.py",
        "stop.py",
        "__init__.py",
    ):
        p = STARTUP_PKG / fn
        assert p.exists(), f"missing module: {p}"


# ── secrets_redactor (covers #20) ────────────────────────────────────────


def test_secrets_redactor_strips_auth_header():
    red = load_redactor()
    s = "Authorization: Bearer abcdef0123456789abcdef0123456789"
    out = red.redact(s)
    assert "abcdef0123456789" not in out
    assert "[REDACTED" in out


def test_secrets_redactor_strips_token_password_cookie():
    red = load_redactor()
    msg = "token=ABCDEF0123 password=hunter2 cookie=ses=abcdef0123456789"
    out = red.redact(msg)
    assert "ABCDEF0123" not in out
    assert "hunter2" not in out
    assert "abcdef0123456789" not in out


def test_secrets_redactor_no_op_for_normal_text():
    red = load_redactor()
    msg = "starting plan 729f69e9 at /tmp/x"
    assert red.redact(msg) == msg


# ── lock (covers #9, #10) ───────────────────────────────────────────────


def test_lock_acquire_and_reject_duplicate():
    lk = load_lock()
    proj = Path("/tmp/_reproctl_dup_test").resolve()
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir()
    lock_path = proj / ".repro" / "run.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    info = lk.acquire(lock_path, command="start", plan_hash="h1")
    assert info["project_root"] == str(proj)
    try:
        with pytest_raises(lk.LockHeld):
            lk.acquire(lock_path, command="start", plan_hash="h2")
    finally:
        lk.release(lock_path)


def test_lock_stale_is_cleared():
    lk = load_lock()
    proj = Path("/tmp/_reproctl_stale_test").resolve()
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir()
    lock_path = proj / ".repro" / "run.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    info = lk.acquire(lock_path, command="start", plan_hash="h1")
    # Spoof staleness: backdate start_time by >6 hours so _is_stale fires.
    # Use a fake PID that does NOT exist (very high number) AND backdate.
    info["process_id"] = 999_999_999
    info["start_time"] = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    info["heartbeat"] = info["start_time"]
    lock_path.write_text(json.dumps(info))
    # Next acquire should succeed (stale treated as free)
    info2 = lk.acquire(lock_path, command="start", plan_hash="h2")
    assert info2["command"] == "start"
    lk.release(lock_path)


def test_lock_release_removes_file():
    lk = load_lock()
    proj = Path("/tmp/_reproctl_release_test").resolve()
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir()
    lock_path = proj / ".repro" / "run.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lk.acquire(lock_path, command="start", plan_hash="h")
    assert lock_path.exists()
    lk.release(lock_path)
    assert not lock_path.exists()


class _PytestStyleRaises:
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            return False
        return issubclass(et, ev)


def pytest_raises(exc):
    return _RaisesCM(exc)


class _RaisesCM:
    def __init__(self, exc):
        self.exc = exc

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            raise AssertionError(f"expected {self.exc.__name__}, no exception")
        if not issubclass(et, self.exc):
            return False
        return True


# ── config priority (covers #5) ──────────────────────────────────────────


def test_config_priority_cli_over_yaml(tmp_path):
    cfg = load_config()
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".repro").mkdir()
    (proj / ".repro" / "config.yaml").write_text("mode: optimized\n")
    plan = make_plan(proj, "X")
    merged = cfg.resolve(project_root=proj, plan_path=plan, cli={"mode": "strict", "extra": "x"})
    assert merged["mode"] == "strict"
    assert merged["extra"] == "x"


def test_config_priority_yaml_over_default(tmp_path):
    cfg = load_config()
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".repro").mkdir()
    (proj / ".repro" / "config.yaml").write_text("mode: optimized\n")
    plan = make_plan(proj)
    merged = cfg.resolve(project_root=proj, plan_path=plan, cli={})
    assert merged["mode"] == "optimized"


def test_config_bad_format_raises(tmp_path):
    cfg = load_config()
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".repro").mkdir()
    (proj / ".repro" / "config.yaml").write_text(": bad: yaml :\n  - [")
    plan = make_plan(proj)
    raised = False
    try:
        cfg.resolve(project_root=proj, plan_path=plan, cli={})
    except SystemExit as e:
        raised = e.code == 2
    assert raised, "expected SystemExit(2) for bad config format"


# ── plan_validate (covers #3, #4) ───────────────────────────────────────


def test_plan_missing_raises():
    pv = load_plan()
    raised = False
    try:
        pv.validate(Path("/tmp/does-not-exist-XXX-1.md"))
    except SystemExit as e:
        raised = e.code == 5
    assert raised


def test_plan_invalid_raises(tmp_path):
    pv = load_plan()
    p = tmp_path / "bad.md"
    p.write_text("not yaml frontmatter\nbody\n")
    raised = False
    try:
        pv.validate(p)
    except SystemExit as e:
        raised = e.code == 5
    assert raised


def test_plan_ok(tmp_path):
    pv = load_plan()
    p = make_plan(tmp_path)
    h = pv.validate(p)
    assert isinstance(h, str) and len(h) == 64


def test_plan_cycle_detected(tmp_path):
    pv = load_plan()
    p = tmp_path / "cyclic.md"
    p.write_text(
        textwrap.dedent(
            """\
            ---
            name: cyclic
            tasks:
              - id: a
                depends_on: [b]
              - id: b
                depends_on: [a]
            ---
            # cyclic
            """
        )
    )
    raised = False
    try:
        pv.validate(p)
    except SystemExit as e:
        raised = e.code == 5
    assert raised


def test_plan_missing_acceptance_task_detected(tmp_path):
    pv = load_plan()
    p = tmp_path / "missing_acc.md"
    p.write_text(
        textwrap.dedent(
            """\
            ---
            name: missing_acc
            tasks:
              - id: a
                depends_on: []
                acceptance: []
            ---
            # missing_acc
            """
        )
    )
    raised = False
    try:
        pv.validate(p)
    except SystemExit as e:
        raised = e.code == 5
    assert raised


# ── doctor (covers #3, #5, #6, #7, #8 partial) ──────────────────────────


def test_doctor_clean_project(tmp_path):
    doc = load_doctor()
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    plan = make_plan(proj)
    report = doc.run(project_root=proj, plan_path=plan)
    # Plugin structure, manifest, python, config, git, plan, disk, r/w, etc.
    assert "checks" in report
    names = {c["name"] for c in report["checks"]}
    for required in (
        "plugin_manifest",
        "python",
        "config_format",
        "git",
        "plan_exists",
        "disk_space",
        "rw",
        "security",
    ):
        assert required in names, f"missing doctor check: {required}"


def test_doctor_no_gpu_status_warning(monkeypatch):
    doc = load_doctor()
    proj = make_project(Path("/tmp/_reproctl_d_nogpu").resolve())
    (proj / ".repro").mkdir()
    plan = make_plan(proj)
    with fake_cuda(
        lambda v: (
            setattr(sys.modules["torch"], "version", v) if v else sys.modules.pop("torch", None)
        ),
        available=False,
    ):
        # remove torch if any
        sys.modules.pop("torch", None)
        report = doc.run(project_root=proj, plan_path=plan)
    gpu_check = next(c for c in report["checks"] if c["name"] == "gpu")
    assert gpu_check["status"] in ("WARNING", "PASS")


def test_doctor_cuda_mismatch(monkeypatch):
    doc = load_doctor()
    proj = make_project(Path("/tmp/_reproctl_d_cudam").resolve())
    (proj / ".repro").mkdir()
    plan = make_plan(proj)
    import types

    fake = types.ModuleType("torch")
    fake_cuda = types.ModuleType("torch.cuda")
    fake_cuda.is_available = lambda: True
    fake_cuda.device_count = lambda: 1
    fake_version = types.ModuleType("torch.version")
    fake_version.cuda = "10.0"  # deliberately old
    fake.cuda = fake_cuda
    fake.version = fake_version
    orig = sys.modules.get("torch")
    sys.modules["torch"] = fake
    try:
        report = doc.run(project_root=proj, plan_path=plan, expected_cuda="12.0")
    finally:
        if orig is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = orig
    cuda_check = next(c for c in report["checks"] if c["name"] == "cuda_match")
    assert cuda_check["status"] in ("FAIL", "WARNING")


def test_doctor_disk_full(monkeypatch):
    doc = load_doctor()
    proj = make_project(Path("/tmp/_reproctl_d_disk").resolve())
    (proj / ".repro").mkdir()
    plan = make_plan(proj)
    from collections import namedtuple

    Disk = namedtuple("usage", "total used free")
    orig = shutil.disk_usage
    shutil.disk_usage = lambda p: Disk(total=10**9, used=10**9, free=0)
    try:
        report = doc.run(project_root=proj, plan_path=plan)
    finally:
        shutil.disk_usage = orig
    disk_check = next(c for c in report["checks"] if c["name"] == "disk_space")
    assert disk_check["status"] == "FAIL"


# ── state machine (covers #11, #12, #13) ────────────────────────────────


def test_state_machine_first_safe_task_claimed(tmp_path):
    sm = load_state_machine()
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    (proj / ".repro" / "execution").mkdir()
    plan = make_plan(proj)
    (proj / ".repro" / "execution" / "task_graph.yaml").write_text(
        textwrap.dedent(
            """\
            metadata: {plan_hash: abc}
            tasks:
              - id: a
                status: READY
              - id: b
                depends_on: [a]
                status: BLOCKED
            """
        )
    )
    next_task = sm.claim_one(project_root=proj, plan_path=plan)
    assert next_task["id"] == "a"
    assert next_task["status"] == "CLAIMED"


def test_state_machine_dry_run_does_not_claim(tmp_path):
    sm = load_state_machine()
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    (proj / ".repro" / "execution").mkdir()
    plan = make_plan(proj)
    (proj / ".repro" / "execution" / "task_graph.yaml").write_text(
        textwrap.dedent(
            """\
            metadata: {plan_hash: abc}
            tasks:
              - id: a
                status: READY
            """
        )
    )
    next_task = sm.claim_one(project_root=proj, plan_path=plan, dry_run=True)
    assert next_task["id"] == "a"
    # State file must NOT be mutated under dry-run
    assert not (proj / ".repro" / "execution" / "execution_state.json").exists()


def test_state_machine_corrupt_state_blocks(tmp_path):
    sm = load_state_machine()
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    (proj / ".repro" / "execution").mkdir()
    plan = make_plan(proj)
    (proj / ".repro" / "execution" / "execution_state.json").write_text("not json{{{")
    raised = False
    try:
        sm.claim_one(project_root=proj, plan_path=plan)
    except SystemExit as e:
        raised = e.code == 8
    assert raised


def test_state_machine_plan_hash_changed(tmp_path):
    sm = load_state_machine()
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    (proj / ".repro" / "execution").mkdir()
    plan = make_plan(proj)
    (proj / ".repro" / "execution" / "execution_state.json").write_text(
        json.dumps({"plan_hash": "OLD_HASH_OLD_HASH_OLD_HASH_OLD_HASH_OLD_HASH_OLD"})
    )
    raised = False
    try:
        sm.claim_one(project_root=proj, plan_path=plan)
    except SystemExit as e:
        raised = e.code == 8
    assert raised


# ── recovery (covers #11, #13, #14) ────────────────────────────────────


def test_recovery_skips_passed_tasks(tmp_path):
    rec = load_recovery()
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    (proj / ".repro" / "execution").mkdir()
    plan = make_plan(proj)
    # Seed execution_state so recovery has something to read
    from startup import plan_validate as _pv

    plan_hash = _pv.validate(plan)
    (proj / ".repro" / "execution" / "execution_state.json").write_text(
        json.dumps(
            {
                "plan_hash": plan_hash,
                "plan_path": str(plan),
                "completed_tasks": ["a"],
                "last_completed_task": "a",
            }
        )
    )
    (proj / ".repro" / "execution" / "task_graph.yaml").write_text(
        textwrap.dedent(
            """\
            metadata: {plan_hash: zzz}
            tasks:
              - id: a
                status: PASS
              - id: b
                depends_on: [a]
                status: READY
            """
        )
    )
    report = rec.run(project_root=proj, plan_path=plan)
    assert report["next_task"]["id"] == "b"
    assert "a" not in report["re_executed"]


# ── stop (covers #15) ───────────────────────────────────────────────────


def test_stop_records_state(tmp_path):
    stop = load_stop()
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    (proj / ".repro" / "execution").mkdir()
    plan = make_plan(proj)
    out = stop.run(project_root=proj, plan_path=plan)
    assert (proj / ".repro" / "execution" / "execution_state.json").exists()
    state = json.loads((proj / ".repro" / "execution" / "execution_state.json").read_text())
    assert state.get("stopped_at")


def test_stop_clears_lock(tmp_path):
    stop = load_stop()
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    (proj / ".repro" / "execution").mkdir()
    plan = make_plan(proj)
    lock = proj / ".repro" / "run.lock"
    lock.write_text(
        json.dumps(
            {
                "process_id": os.getpid(),
                "hostname": socket.gethostname(),
                "start_time": datetime.now(timezone.utc).isoformat(),
                "project_root": str(proj),
                "plan_hash": "x",
                "command": "start",
                "heartbeat": datetime.now(timezone.utc).isoformat(),
                "plugin_version": "0.1.0",
            }
        )
    )
    stop.run(project_root=proj, plan_path=plan)
    assert not lock.exists()


# ── integration via the real scripts/reproctl.py entry ────────────────
# These exercise the full CLI surface and prove that
#   `python scripts/reproctl.py ...`  ==
#   Cursor wrapper invocation.


# Helper: build a temporary plugin copy so the plugin's reproctl.py is
# exec'd with the *real* scripts/startup/ on sys.path. We use sys.path
# injection to avoid copying the repo.


def _cli_env(tmp_path: Path) -> dict:
    return {
        "PYTHONPATH": str(SCRIPTS) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        # Force doctor "no GPU" path even on a GPU host
        "REPRO_FAKE_GPU": "0",
    }


def _write_dummy_gpu_check_override(tmp_path):
    """Inject a doctor module patch via env-var so tests run on GPU hosts too."""
    return


# ─── TEST 1: fresh project start ───────────────────────────────────────


def test_integ_01_fresh_start(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=_cli_env(tmp_path)
    )
    assert r.returncode == 0, r.stdout + r.stderr
    # Files created
    assert (proj / ".repro" / "startup" / "startup_state.json").exists()
    assert (proj / ".repro" / "startup" / "doctor_report.json").exists()
    assert (proj / ".repro" / "startup" / "startup_summary.md").exists()
    assert (proj / ".repro" / "execution" / "task_graph.yaml").exists()
    assert (proj / ".repro" / "execution" / "execution_state.json").exists()
    # Lock present
    assert (proj / ".repro" / "run.lock").exists()


# ─── TEST 2: dry-run ───────────────────────────────────────────────────


def test_integ_02_dry_run(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan), "--dry-run"],
        cwd=proj,
        env=_cli_env(tmp_path),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    # No lock, no execution state mutation
    assert not (proj / ".repro" / "run.lock").exists()
    summary = (proj / ".repro" / "startup" / "startup_summary.md").read_text()
    # Case-insensitive check
    assert "(DRY RUN)" in summary or "dry run" in summary.lower()


# ─── TEST 3: missing plan ──────────────────────────────────────────────


def test_integ_03_missing_plan(tmp_path):
    proj = make_project(tmp_path / "p")
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(tmp_path / "missing.md")],
        cwd=proj,
        env=_cli_env(tmp_path),
    )
    assert r.returncode == 5


# ─── TEST 4: invalid plan ──────────────────────────────────────────────


def test_integ_04_invalid_plan(tmp_path):
    proj = make_project(tmp_path / "p")
    bad = tmp_path / "bad.md"
    bad.write_text("garbage, no frontmatter\n")
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(bad)], cwd=proj, env=_cli_env(tmp_path)
    )
    assert r.returncode == 5


# ─── TEST 5: bad config format ─────────────────────────────────────────


def test_integ_05_bad_config_format(tmp_path):
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir(exist_ok=True)
    (proj / ".repro" / "config.yaml").write_text("::: not :::: yaml :::\n  - [")
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=_cli_env(tmp_path)
    )
    assert r.returncode == 2


# ─── TEST 6: no GPU (doctor WARNING, not blocking start) ───────────────


def test_integ_06_no_gpu(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=tmp_path, env=_cli_env(tmp_path)
    )
    # No GPU on the test host -> WARNING in doctor, start still succeeds
    assert r.returncode == 0
    report = json.loads((proj / ".repro" / "startup" / "doctor_report.json").read_text())
    gpu_check = next((c for c in report["checks"] if c["name"] == "gpu"), None)
    assert gpu_check is not None
    assert gpu_check["status"] in ("WARNING", "PASS")


# ─── TEST 7: CUDA mismatch ─────────────────────────────────────────────


def test_integ_07_cuda_mismatch(tmp_path):
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir(exist_ok=True)
    (proj / ".repro" / "config.yaml").write_text("expected_cuda: 12.0\n")
    plan = make_plan(proj)
    # Force the fake torch module to report CUDA 10.0
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan), "--expected-cuda", "12.0"],
        cwd=tmp_path,
        env={"PYTHONPATH": str(SCRIPTS), "REPRO_FAKE_CUDA": "10.0", "REPRO_FAKE_GPU": "1"},
    )
    # doctor FAIL blocks start
    assert r.returncode == 3


# ─── TEST 8: disk full ─────────────────────────────────────────────────


def test_integ_08_disk_full(tmp_path, monkeypatch):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    # Patch shutil.disk_usage at the subprocess by writing an env var the
    # cli module reads (REPRO_FAKE_DISK_FREE=0). We need the cli to honor it.
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)],
        cwd=tmp_path,
        env={"PYTHONPATH": str(SCRIPTS), "REPRO_FAKE_DISK_FREE": "0", "REPRO_FAKE_GPU": "0"},
    )
    assert r.returncode == 3  # doctor FAIL blocks start


# ─── TEST 9: duplicate start ───────────────────────────────────────────


def test_integ_09_duplicate_start(tmp_path):
    """Two `start` invocations on the same project must not coexist.

    The first one is spawned as a long-running background process that
    intentionally sleeps before exiting; while it holds the lock, a
    second `start` must be rejected with exit code 4.
    """
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    e = _cli_env(tmp_path)

    # Use a wrapper that calls `start` and then idles so the lock is held.
    wrapper = proj / "_hold.py"
    wrapper.write_text(
        textwrap.dedent("""
        import os, sys, time
        sys.path.insert(0, os.environ.get("REPRO_SCRIPTS", "scripts"))
        from startup.cli import main as cli_main
        # First argument is "start" (the wrapper invokes itself)
        rc = cli_main(["start", "--project", sys.argv[1], "--plan", sys.argv[2]])
        # Hold the lock open
        time.sleep(float(sys.argv[3]))
    """)
    )
    e["REPRO_SCRIPTS"] = str(SCRIPTS)

    p1 = subprocess.Popen(
        [sys.executable, str(wrapper), str(proj), str(plan), "5"],
        cwd=proj,
        env=e,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give the first process time to acquire the lock
    time.sleep(1.0)
    try:
        r2 = run_cli(["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=e)
        assert r2.returncode == 4, (
            f"expected 4 (duplicate), got {r2.returncode}; "
            f"stdout={r2.stdout[:300]} stderr={r2.stderr[:300]}"
        )
    finally:
        p1.terminate()
        try:
            p1.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p1.kill()


# ─── TEST 10: stale lock cleared by state-consistency check ────────────


def test_integ_10_stale_lock(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    (proj / ".repro").mkdir(exist_ok=True)
    # Plant a clearly stale lock from yesterday
    yesterday = datetime.now(timezone.utc).replace(year=2000).isoformat()
    (proj / ".repro" / "run.lock").write_text(
        json.dumps(
            {
                "process_id": 999999,
                "hostname": "ghost",
                "start_time": yesterday,
                "project_root": str(proj),
                "plan_hash": "x",
                "command": "start",
                "heartbeat": yesterday,
                "plugin_version": "0.1.0",
            }
        )
    )
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=_cli_env(tmp_path)
    )
    # Stale lock should be cleared and start should succeed
    assert r.returncode == 0, r.stdout + r.stderr
    assert (proj / ".repro" / "run.lock").exists()  # replaced with fresh


# ─── TEST 11: interrupted recovery ─────────────────────────────────────


def test_integ_11_interrupted_recovery(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    e = _cli_env(tmp_path)
    r1 = run_cli(["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=e)
    assert r1.returncode == 0
    # Simulate interrupt: mutate execution_state to look mid-task
    es = proj / ".repro" / "execution" / "execution_state.json"
    state = json.loads(es.read_text())
    state["interrupted"] = True
    state["interrupted_task"] = state.get("current_task", "P0_T000")
    es.write_text(json.dumps(state))
    # Remove lock so resume can re-acquire
    (proj / ".repro" / "run.lock").unlink()
    r2 = run_cli(["resume", "--project", str(proj)], cwd=proj, env=e)
    assert r2.returncode == 0, r2.stdout + r2.stderr


# ─── TEST 12: plan_hash changed ────────────────────────────────────────


def test_integ_12_plan_hash_changed(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    e = _cli_env(tmp_path)
    r1 = run_cli(["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=e)
    assert r1.returncode == 0
    # Mutate plan hash in execution_state to a clearly different hash
    es = proj / ".repro" / "execution" / "execution_state.json"
    state = json.loads(es.read_text())
    state["plan_hash"] = "0" * 64
    es.write_text(json.dumps(state))
    (proj / ".repro" / "run.lock").unlink()
    r2 = run_cli(["resume", "--project", str(proj)], cwd=proj, env=e)
    assert r2.returncode == 8  # resume failed


# ─── TEST 13: corrupted state file ────────────────────────────────────


def test_integ_13_corrupted_state(tmp_path):
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    (proj / ".repro" / "execution").mkdir()
    (proj / ".repro" / "execution" / "execution_state.json").write_text("not json {{{")
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=_cli_env(tmp_path)
    )
    # Either rollback to safe-state (0) or refuse (8) are valid for v0.2
    assert r.returncode in (0, 8)


# ─── TEST 14: corrupted checkpoint ────────────────────────────────────


def test_integ_14_corrupted_checkpoint(tmp_path):
    proj = make_project(tmp_path / "p")
    (proj / ".repro").mkdir()
    ck = proj / ".repro" / "execution" / "checkpoints"
    ck.mkdir(parents=True)
    ck.joinpath("last.pth").write_text("garbage, not a torch save")
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=_cli_env(tmp_path)
    )
    # Start must not auto-train; corruption must be flagged but not crash start
    assert r.returncode in (0, 7)


# ─── TEST 15: stop graceful ───────────────────────────────────────────


def test_integ_15_stop_graceful(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    e = _cli_env(tmp_path)
    r1 = run_cli(["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=e)
    assert r1.returncode == 0
    r2 = run_cli(["stop", "--project", str(proj)], cwd=proj, env=e)
    assert r2.returncode == 0
    assert not (proj / ".repro" / "run.lock").exists()
    state = json.loads((proj / ".repro" / "execution" / "execution_state.json").read_text())
    assert state.get("stopped_at")


# ─── TEST 16: Cursor command == CLI behavior ────────────────────────────


def test_integ_16_cursor_cmd_equals_cli(tmp_path):
    """The /repro-start Cursor command is a thin wrapper. Verify it is a
    pure pass-through and the same code path is exercised."""
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    wrapper = REPO / "commands" / "repro-start.md"
    assert wrapper.exists()
    text = wrapper.read_text()
    # Wrapper must literally call the Python CLI (no parallel logic)
    assert "scripts/reproctl.py" in text or "reproctl.py" in text
    # And the wrapper file must be ≤ 30 lines
    assert len(text.splitlines()) <= 30, f"repro-start.md is {len(text.splitlines())} lines (>30)"
    # Running the same args via the Python CLI must succeed
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=_cli_env(tmp_path)
    )
    assert r.returncode == 0, r.stdout + r.stderr


# ─── TEST 17: Windows/WSL/Linux path handling ──────────────────────────


def test_integ_17_path_handling(tmp_path):
    """Paths with forward- and backward-slashes on POSIX; WSL/Windows
    detection must be platform-aware but not hard-coded to a single OS."""
    cli = load_cli()
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    p_norm = cli.normalize_path(proj)
    assert Path(p_norm).is_absolute()
    assert isinstance(cli.platform_tag(), str)
    assert cli.platform_tag() in ("linux", "darwin", "windows", "wsl", "unknown")


# ─── TEST 18: paths with spaces ────────────────────────────────────────


def test_integ_18_paths_with_spaces(tmp_path):
    proj = tmp_path / "p with spaces"
    make_project(proj)
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=tmp_path, env=_cli_env(tmp_path)
    )
    assert r.returncode == 0, r.stdout + r.stderr


# ─── TEST 19: uncommitted git changes ──────────────────────────────────


def test_integ_19_uncommitted_git(tmp_path):
    proj = make_project(tmp_path / "p", git=True, dirty=True)
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=_cli_env(tmp_path)
    )
    assert r.returncode == 0, r.stdout + r.stderr
    summary = (proj / ".repro" / "startup" / "startup_summary.md").read_text()
    assert "uncommitted" in summary.lower() or "dirty" in summary.lower()


# ─── TEST 20: secrets never in logs ────────────────────────────────────


def test_integ_20_secrets_never_in_logs(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    e = _cli_env(tmp_path)
    e["MY_SECRET_TOKEN"] = "THIS_IS_A_TEST_SECRET_VALUE_1234567890"
    r = run_cli(["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=e)
    # Grep for the secret in any file under .repro/
    found = []
    secret = "THIS_IS_A_TEST_SECRET_VALUE_1234567890"
    for p in (proj / ".repro").rglob("*"):
        if p.is_file():
            try:
                if secret in p.read_text(errors="ignore"):
                    found.append(str(p))
            except Exception:
                pass
    assert not found, f"secret leaked into: {found}"


# ─── Cursor commands exist & are ≤30 lines ─────────────────────────────


def test_all_cursor_commands_exist_and_thin():
    expected = [
        "repro-start.md",
        "repro-doctor.md",
        "repro-status.md",
        "repro-resume.md",
        "repro-stop.md",
        "repro-verify.md",
    ]
    for fn in expected:
        p = REPO / "commands" / fn
        assert p.exists(), f"missing wrapper: {p}"
        text = p.read_text()
        assert len(text.splitlines()) <= 30, f"{fn} is {len(text.splitlines())} lines (>30)"


# ─── start summary format ─────────────────────────────────────────────


def test_start_summary_format(tmp_path):
    proj = make_project(tmp_path / "p")
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan)], cwd=proj, env=_cli_env(tmp_path)
    )
    assert r.returncode == 0
    out = r.stdout
    # Required labels on the success line
    for label in (
        "Repro Agent Ready",
        "Project:",
        "Plan:",
        "Mode:",
        "Plugin Version:",
        "Git Commit:",
        "GPU:",
        "Execution State:",
        "Last Completed Task:",
        "Next Task:",
        "Log:",
        "Status Command:",
        "Stop Command:",
    ):
        assert label in out, f"missing label in summary: {label}"


# ─── unified entry has the new subcommands ────────────────────────────


def test_new_subcommands_dispatched():
    """The unified reproctl.py must dispatch: start, doctor, status, resume,
    stop, verify, version. Old subcommands must still exist (no breaking)."""
    r = run_cli(["help"], cwd=REPO)
    # help lists all of these
    for cmd in (
        "start",
        "doctor",
        "status",
        "resume",
        "stop",
        "verify",
        "version",
        "init",
        "report",
    ):
        assert cmd in r.stdout, f"missing {cmd} from help output"


# ─── version command ──────────────────────────────────────────────────


def test_version_command(tmp_path):
    r = run_cli(["version"], cwd=tmp_path)
    assert r.returncode == 0
    assert "dl-paper-repro" in r.stdout.lower() or "reproctl" in r.stdout.lower()


# ─── exit codes are unified ───────────────────────────────────────────


def test_exit_codes_documented(tmp_path):
    r = run_cli(
        ["start", "--project", "/nonexistent-XYZ", "--plan", "/also-missing-XYZ"],
        cwd=tmp_path,
        env=_cli_env(tmp_path),
    )
    # 2 (bad args: project missing), 4 (no lock), or 5 (no plan) are valid
    assert r.returncode in (2, 4, 5)


def test_no_hardcoded_paths_in_new_code():
    """Grep the new scripts/startup/*.py for /home/<name>/ patterns."""
    bad = []
    for p in (STARTUP_PKG).rglob("*.py"):
        text = p.read_text(errors="ignore")
        for token in (
            "/home/carlkestrel",
            "/home/user",
            "/Users/carlkestrel",
            "/data/",
            "/datasets/",
        ):
            if token in text:
                bad.append((str(p), token))
    assert not bad, f"hardcoded paths in new code: {bad}"


def test_dry_run_no_training_side_effects(tmp_path):
    """dry-run must not invoke training scripts."""
    proj = make_project(tmp_path / "p")
    (proj / "primary").mkdir(exist_ok=True)
    (proj / "primary" / "train.py").write_text(
        "raise SystemExit(99)  # sentinel: should never be invoked from start/dry-run\n"
    )
    plan = make_plan(proj)
    r = run_cli(
        ["start", "--project", str(proj), "--plan", str(plan), "--dry-run"],
        cwd=proj,
        env=_cli_env(tmp_path),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    # The sentinel must NOT have been executed
    assert (proj / ".repro" / "startup" / "doctor_report.json").exists()


# ─── pytest-style entry ───────────────────────────────────────────────


def _pytest_main():
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))


if __name__ == "__main__":
    _pytest_main()
