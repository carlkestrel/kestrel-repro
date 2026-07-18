"""Doctor — preflight checks for plugin structure, env, plan, hardware, etc.

Mandatory FAIL items block `start` (exit code 3). WARNING items are reported
but do not block. Status enum: PASS / WARNING / FAIL / BLOCKED / UNSUPPORTED.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EXIT_DOCTOR_FAIL = 3


# ──────────────────────────────────────────────────────────────────────
# Individual checks
# ──────────────────────────────────────────────────────────────────────


def _check_plugin_manifest(plugin_root: Path) -> dict:
    """plugin.json must exist and parse as JSON."""
    p = plugin_root / ".cursor-plugin" / "plugin.json"
    if not p.exists():
        return {"name": "plugin_manifest", "status": "FAIL",
                "message": f"missing {p}",
                "fix": "create .cursor-plugin/plugin.json"}
    try:
        data = json.loads(p.read_text())
        if "name" not in data:
            return {"name": "plugin_manifest", "status": "FAIL",
                    "message": "plugin.json missing `name`",
                    "fix": "add `name` field"}
        return {"name": "plugin_manifest", "status": "PASS",
                "message": f"plugin name={data['name']} version={data.get('version', '?')}"}
    except json.JSONDecodeError as e:
        return {"name": "plugin_manifest", "status": "FAIL",
                "message": f"plugin.json invalid JSON: {e}",
                "fix": "fix JSON syntax in plugin.json"}


def _check_python() -> dict:
    v = sys.version_info
    return {"name": "python", "status": "PASS",
            "message": f"Python {v.major}.{v.minor}.{v.micro} on {platform.platform()}"}


def _check_deps() -> dict:
    missing = []
    for dep in ("yaml",):
        try:
            importlib.util.find_spec(dep)
        except (ImportError, ValueError):
            missing.append(dep)
    if missing:
        return {"name": "deps", "status": "WARNING",
                "message": f"optional deps missing: {missing}",
                "fix": f"pip install {' '.join(missing)}"}
    return {"name": "deps", "status": "PASS", "message": "core deps OK"}


def _check_config_format(project_root: Path) -> dict:
    for rel in (".repro/config.yaml", "repro.yaml"):
        p = project_root / rel
        if not p.exists():
            continue
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(p.read_text())
        except Exception:
            try:
                import yaml  # type: ignore
                data = yaml.safe_load(p.read_text())
            except ImportError:
                data = _mini_yaml(p.read_text())
            except Exception as e:
                return {"name": "config_format", "status": "FAIL",
                        "message": f"cannot parse {rel}: {e}",
                        "fix": "fix YAML syntax"}
        if data is not None and not isinstance(data, dict):
            return {"name": "config_format", "status": "FAIL",
                    "message": f"{rel} must be a YAML mapping",
                    "fix": "rewrite config as `key: value` mapping"}
    return {"name": "config_format", "status": "PASS",
            "message": "no config files, or they parse"}


def _mini_yaml(text: str) -> dict:
    out: dict = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"unparsable config line: {line!r}")
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.lower() in ("true", "false"):
            out[k] = (v.lower() == "true")
        elif v.lower() in ("null", "~", ""):
            out[k] = None
        else:
            try:
                out[k] = int(v)
            except ValueError:
                try:
                    out[k] = float(v)
                except ValueError:
                    out[k] = v
    return out


def _check_git(project_root: Path) -> dict:
    if not (project_root / ".git").exists():
        return {"name": "git", "status": "WARNING",
                "message": "project is not a git repository",
                "fix": "run `git init` (optional, but recommended)"}
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(project_root),
            stderr=subprocess.DEVNULL, text=True).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(project_root),
            stderr=subprocess.DEVNULL, text=True)
        dirty = bool(status.strip())
        msg = f"commit={sha[:12]} dirty={dirty}"
        return {"name": "git", "status": "PASS", "message": msg,
                "details": {"commit": sha, "dirty": dirty}}
    except subprocess.CalledProcessError as e:
        return {"name": "git", "status": "FAIL",
                "message": f"git error: {e}",
                "fix": "commit your changes or re-init the repo"}


def _check_plan_exists(plan_path: Path) -> dict:
    if not plan_path:
        return {"name": "plan_exists", "status": "FAIL",
                "message": "no plan path provided",
                "fix": "pass --plan <PLAN_PATH>"}
    if not plan_path.exists():
        return {"name": "plan_exists", "status": "FAIL",
                "message": f"plan not found: {plan_path}",
                "fix": "create the plan file or pass a valid path"}
    return {"name": "plan_exists", "status": "PASS",
            "message": f"plan {plan_path.name} found"}


def _check_task_graph(plan_path: Path) -> dict:
    """Minimal sanity check on the plan's task-graph."""
    try:
        import yaml  # type: ignore
        text = plan_path.read_text()
        # Strip frontmatter fences
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm = yaml.safe_load(parts[1]) or {}
            else:
                fm = {}
        else:
            fm = {}
        tasks = fm.get("tasks") or []
        if tasks and isinstance(tasks, list):
            ids = {t.get("id") for t in tasks if t.get("id")}
            unknown = []
            for t in tasks:
                for d in t.get("depends_on") or []:
                    if d not in ids:
                        unknown.append((t.get("id"), d))
            if unknown:
                return {"name": "task_graph", "status": "FAIL",
                        "message": f"unknown deps: {unknown}",
                        "fix": "fix or remove unknown task dependencies"}
        return {"name": "task_graph", "status": "PASS",
                "message": f"{len(tasks)} tasks" if tasks else "no tasks declared"}
    except Exception as e:
        return {"name": "task_graph", "status": "WARNING",
                "message": f"could not introspect task graph: {e}",
                "fix": "ensure plan frontmatter is valid YAML"}


def _check_disk(project_root: Path) -> dict:
    try:
        # Allow tests to inject a fake free-byte count via env var.
        fake = os.environ.get("REPRO_FAKE_DISK_FREE")
        if fake is not None:
            free = int(fake)
        else:
            u = shutil.disk_usage(str(project_root))
            free = u.free
        if free <= 0:
            return {"name": "disk_space", "status": "FAIL",
                    "message": "no free disk space",
                    "fix": "free at least 1 GB before starting"}
        if free < 1 * 1024 * 1024 * 1024:
            return {"name": "disk_space", "status": "WARNING",
                    "message": f"only {free // 1024 // 1024} MB free",
                    "fix": "consider freeing at least 1 GB"}
        return {"name": "disk_space", "status": "PASS",
                "message": f"{free // 1024 // 1024} MB free"}
    except Exception as e:
        return {"name": "disk_space", "status": "WARNING",
                "message": f"could not measure disk: {e}",
                "fix": "verify the project path is on a readable filesystem"}


def _check_rw(project_root: Path) -> dict:
    try:
        probe = project_root / ".repro" / ".doctor_probe"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok")
        probe.unlink()
        return {"name": "rw", "status": "PASS",
                "message": f"writable: {project_root}"}
    except Exception as e:
        return {"name": "rw", "status": "FAIL",
                "message": f"project not writable: {e}",
                "fix": "chmod +w the project root or pick another path"}


def _check_gpu() -> dict:
    if os.environ.get("REPRO_FAKE_GPU") == "0":
        return {"name": "gpu", "status": "WARNING",
                "message": "GPU not available (test/no-GPU host)",
                "fix": "proceed without GPU; performance will be limited"}
    try:
        import torch  # type: ignore
        if not torch.cuda.is_available():
            return {"name": "gpu", "status": "WARNING",
                    "message": "torch.cuda.is_available() == False",
                    "fix": "verify CUDA installation if you need GPU"}
        n = torch.cuda.device_count()
        name = torch.cuda.get_device_name(0) if n > 0 else "(none)"
        return {"name": "gpu", "status": "PASS",
                "message": f"{n}× {name}"}
    except ImportError:
        return {"name": "gpu", "status": "WARNING",
                "message": "torch not installed",
                "fix": "pip install torch (if you need GPU)"}
    except Exception as e:
        return {"name": "gpu", "status": "WARNING",
                "message": f"GPU probe failed: {e}",
                "fix": "check CUDA / driver installation"}


def _check_cuda_match(expected: str | None) -> dict:
    """Compare observed torch.version.cuda against ``expected`` (if any)."""
    fake = os.environ.get("REPRO_FAKE_CUDA")
    try:
        import torch  # type: ignore
        actual = torch.version.cuda or ""
        if fake:
            actual = fake
    except ImportError:
        actual = fake or ""
    if not expected:
        return {"name": "cuda_match", "status": "PASS",
                "message": f"no expected_cuda configured (observed={actual or 'unknown'})"}
    if not actual:
        return {"name": "cuda_match", "status": "WARNING",
                "message": "cannot read CUDA version (torch missing?)",
                "fix": "install torch if you need CUDA"}
    if actual != expected:
        return {"name": "cuda_match", "status": "FAIL",
                "message": f"CUDA mismatch: expected={expected} observed={actual}",
                "fix": f"install torch matching CUDA {expected} or change config"}
    return {"name": "cuda_match", "status": "PASS",
            "message": f"CUDA {actual} matches expected"}


def _check_driver() -> dict:
    rc, out, _ = _run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits"])
    if rc != 0:
        return {"name": "driver", "status": "WARNING",
                "message": "nvidia-smi not available",
                "fix": "install NVIDIA driver if you need GPU"}
    return {"name": "driver", "status": "PASS",
            "message": f"driver={out.strip().splitlines()[0] if out.strip() else 'unknown'}"}


def _check_torch() -> dict:
    try:
        import torch  # type: ignore
        version = getattr(torch, "__version__", "unknown")
        cuda_v = getattr(getattr(torch, "version", None), "cuda", None) or "none"
        return {"name": "torch", "status": "PASS",
                "message": f"torch={version} cuda={cuda_v}"}
    except ImportError:
        return {"name": "torch", "status": "WARNING",
                "message": "torch not installed",
                "fix": "pip install torch (required for training, optional for planning)"}


def _check_security() -> dict:
    """Scan project_root for files containing credential-like strings."""
    bad = []
    project_root_str = ""  # only used for the explicit message
    # Only scan source-controlled text files; skip binary / lock files.
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
    SENSITIVE = ("Authorization", "Bearer ", "password=", "token=", "cookie=",
                 "AWS_SECRET", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    try:
        # We scan up to 200 files to keep doctor cheap.
        for path in list(Path.cwd().rglob("*"))[:2000]:
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in {".pth", ".pt", ".bin", ".safetensors",
                               ".png", ".jpg", ".pdf"}:
                continue
            try:
                text = path.read_text(errors="ignore")
            except Exception:
                continue
            for needle in SENSITIVE:
                if needle in text:
                    # Allow log lines explicitly written by our redactor:
                    if "[REDACTED]" in text and needle in {"Authorization"}:
                        # The presence of both means we already redacted.
                        continue
                    bad.append((str(path), needle))
                    break
    except Exception as e:
        return {"name": "security", "status": "WARNING",
                "message": f"security scan error: {e}",
                "fix": "manually grep for credentials"}
    if bad:
        return {"name": "security", "status": "WARNING",
                "message": f"credential-shaped strings in {len(bad)} files (e.g. {bad[0]})",
                "fix": "remove credentials from source tree",
                "details": {"first_matches": bad[:5]}}
    return {"name": "security", "status": "PASS",
            "message": "no credential-shaped strings detected"}


def _check_leftover_procs() -> dict:
    """Best-effort: look for python processes whose cwd is this project."""
    try:
        out = subprocess.check_output(
            ["ps", "-eo", "pid=,comm=,args="], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return {"name": "leftover_procs", "status": "PASS",
                "message": "ps not available"}
    pid_self = os.getpid()
    matches = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid == pid_self:
            continue
        cmd = parts[2]
        if ("python" in parts[1].lower() and "reproctl" in cmd
                and Path.cwd().as_posix() in cmd):
            matches.append(pid)
    if matches:
        return {"name": "leftover_procs", "status": "WARNING",
                "message": f"possible leftover reproctl processes: {matches}",
                "fix": "kill stale processes or use `reproctl stop`"}
    return {"name": "leftover_procs", "status": "PASS",
            "message": "no leftover reproctl processes"}


def _check_state_file(project_root: Path) -> dict:
    p = project_root / ".repro" / "execution" / "execution_state.json"
    if not p.exists():
        return {"name": "state_file", "status": "PASS",
                "message": "no execution state yet"}
    try:
        json.loads(p.read_text())
        return {"name": "state_file", "status": "PASS",
                "message": "execution_state.json is valid JSON"}
    except Exception as e:
        return {"name": "state_file", "status": "WARNING",
                "message": f"execution_state.json corrupt: {e}",
                "fix": "remove or restore .repro/execution/execution_state.json; "
                       "use `reproctl resume` to recover"}


def _check_checkpoint(project_root: Path) -> dict:
    p = project_root / ".repro" / "execution" / "checkpoints"
    if not p.exists():
        return {"name": "checkpoint", "status": "PASS",
                "message": "no checkpoints directory yet"}
    for ck in p.glob("*"):
        try:
            sz = ck.stat().st_size
        except OSError:
            continue
        if sz < 100:
            try:
                head = ck.read_bytes()[:8]
                if b"PKL" not in head and b"PK\x03\x04" not in head and not head.startswith(b"---"):
                    return {"name": "checkpoint", "status": "WARNING",
                            "message": f"checkpoint looks corrupt: {ck.name} ({sz} B)",
                            "fix": "remove the corrupt checkpoint; start will re-create"}
            except Exception:
                continue
    return {"name": "checkpoint", "status": "PASS",
            "message": "no corrupt checkpoints detected"}


# ──────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def run(*, project_root: Path, plan_path: Path | None,
        expected_cuda: str | None = None,
        plugin_root: Path | None = None) -> dict:
    """Run all checks and return a structured report."""
    plugin_root = plugin_root or Path(__file__).resolve().parents[2]

    checks = [
        _check_plugin_manifest(plugin_root),
        _check_python(),
        _check_deps(),
        _check_config_format(project_root),
        _check_git(project_root),
        _check_plan_exists(plan_path) if plan_path is not None else
            {"name": "plan_exists", "status": "WARNING",
             "message": "no plan path provided",
             "fix": "pass --plan <PLAN_PATH>"},
        _check_task_graph(plan_path) if plan_path is not None else
            {"name": "task_graph", "status": "PASS",
             "message": "skipped (no plan)"},
        _check_disk(project_root),
        _check_rw(project_root),
        _check_gpu(),
        _check_cuda_match(expected_cuda),
        _check_driver(),
        _check_torch(),
        _check_security(),
        _check_leftover_procs(),
        _check_state_file(project_root),
        _check_checkpoint(project_root),
    ]

    # Summarize
    summary = {"PASS": 0, "WARNING": 0, "FAIL": 0, "BLOCKED": 0, "UNSUPPORTED": 0}
    for c in checks:
        summary[c["status"]] = summary.get(c["status"], 0) + 1

    overall = "PASS"
    if summary["FAIL"] > 0:
        overall = "FAIL"
    elif summary["WARNING"] > 0:
        overall = "WARNING"

    return {
        "plugin_version": _plugin_version(plugin_root),
        "project_root": str(project_root),
        "plan_path": str(plan_path) if plan_path else "",
        "hostname": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "summary": summary,
        "overall": overall,
    }


def _plugin_version(plugin_root: Path) -> str:
    """Read plugin.json for the version (no hardcoding)."""
    p = plugin_root / ".cursor-plugin" / "plugin.json"
    try:
        return json.loads(p.read_text()).get("version", "0.0.0")
    except Exception:
        return "0.0.0"
