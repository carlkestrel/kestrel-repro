#!/usr/bin/env python3
"""
environment_check.py

Checks the runtime environment for a deep learning paper reproduction:
- Python version
- CUDA and cuDNN versions
- PyTorch version and build info
- GPU availability
- Required packages
- Disk space
- Custom CUDA extension compatibility

Usage:
    python environment_check.py [--output-format=json|markdown]
"""

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_cmd(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=str(cwd) if cwd else None
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"


def check_python() -> dict[str, Any]:
    return {
        "version": sys.version,
        "version_info": list(sys.version_info[:3]),
        "executable": sys.executable,
        "platform": platform.platform(),
        "architecture": platform.machine(),
    }


def check_cuda() -> dict[str, Any]:
    result = {
        "available": False,
        "version": None,
        "cudnn_version": None,
        "nvidia_smi": None,
    }

    # Check nvidia-smi
    rc, stdout, _ = run_cmd(["nvidia-smi"])
    if rc == 0:
        result["nvidia_smi"] = stdout.strip().split("\n")[0] if stdout else None

    # Check nvcc
    rc, stdout, _ = run_cmd(["nvcc", "--version"])
    if rc == 0:
        for line in stdout.split("\n"):
            if "release" in line.lower():
                result["version"] = line.strip()
                break

    # Check PyTorch CUDA
    try:
        import torch

        result["available"] = torch.cuda.is_available()
        if result["available"]:
            result["pytorch_cuda_version"] = torch.version.cuda
            result["cudnn_version"] = torch.backends.cudnn.version()
            result["gpu_count"] = torch.cuda.device_count()
            result["gpu_name"] = torch.cuda.get_device_name(0) if result["gpu_count"] > 0 else None
            result["compute_capability"] = (
                torch.cuda.get_device_capability(0) if result["gpu_count"] > 0 else None
            )
            result["bf16_supported"] = torch.cuda.is_bf16_supported()
    except ImportError:
        result["pytorch_available"] = False

    return result


def check_pytorch() -> dict[str, Any]:
    result = {"available": False}
    try:
        import torch

        result["available"] = True
        result["version"] = torch.__version__
        result["cuda_available"] = torch.cuda.is_available()
        result["cuda_version"] = torch.version.cuda
        result["cudnn_version"] = torch.backends.cudnn.version()
        result["distributed_available"] = hasattr(torch, "distributed")
        result["compile_available"] = hasattr(torch, "compile")

        # Memory info
        if torch.cuda.is_available():
            result["gpu_memory_total"] = torch.cuda.get_device_properties(0).total_memory
            result["gpu_memory_gb"] = round(result["gpu_memory_total"] / 1e9, 2)
    except ImportError:
        result["error"] = "PyTorch not installed"
    return result


def check_packages() -> dict[str, Any]:
    """Check for required packages."""
    required = [
        "torch",
        "numpy",
        "PIL",
        "yaml",
        "json",
        "pathlib",
    ]
    results = {}
    for pkg in required:
        try:
            mod = __import__(pkg.replace("-", "_"))
            ver = getattr(mod, "__version__", "unknown")
            results[pkg] = {"installed": True, "version": ver}
        except ImportError:
            results[pkg] = {"installed": False}
    return results


def check_disk_space(path: str = ".") -> dict[str, Any]:
    """Check available disk space."""
    import shutil

    result = {"path": path}
    try:
        usage = shutil.disk_usage(path)
        result["total_gb"] = round(usage.total / 1e9, 1)
        result["free_gb"] = round(usage.free / 1e9, 1)
        result["used_percent"] = round((usage.used / usage.total) * 100, 1)
        result["sufficient"] = usage.free > 10 * (1024**3)  # 10 GB minimum
    except Exception as e:
        result["error"] = str(e)
    return result


def check_cpu() -> dict[str, Any]:
    """Check CPU information."""
    result = {
        "processor": platform.processor(),
        "physical_cores": None,
        "logical_cores": None,
    }
    rc, stdout, _ = run_cmd(["lscpu"])
    if rc == 0:
        for line in stdout.split("\n"):
            if "Core(s)" in line:
                result["physical_cores"] = int(line.split()[-1])
            if "Thread(s)" in line:
                result["logical_cores"] = int(line.split()[-1])
            if "Model name" in line:
                result["model_name"] = line.split(":")[1].strip()
    return result


def check_memory() -> dict[str, Any]:
    """Check RAM availability."""
    import shutil

    result = {}
    try:
        mem = shutil.mem_info()
        result["total_gb"] = round(mem[0] / (1024**3), 1)
        result["available_gb"] = round(mem[1] / (1024**3), 1)
    except Exception:
        rc, stdout, _ = run_cmd(["free", "-h"])
        if rc == 0:
            result["free_output"] = stdout.strip()
    return result


def check_custom_extensions(primary_path: Path) -> dict[str, Any]:
    """Check for custom CUDA extensions in the repository."""
    extensions = {
        "found": [],
        "compilation_info": {},
    }

    # Look for common CUDA extension files
    patterns = ["*.cu", "*.cpp", "*.cuo", "setup.py", "setup.cfg"]
    for pattern in patterns:
        files = list(primary_path.rglob(pattern))
        for f in files:
            if "test" not in f.name.lower():
                extensions["found"].append(str(f.relative_to(primary_path)))

    # Check if they can be compiled
    if extensions["found"]:
        rc, _, _ = run_cmd(["which", "nvcc"])
        extensions["nvcc_available"] = rc == 0

    return extensions


def run_full_check(output_format: str = "json", primary_path: Path | None = None) -> dict[str, Any]:
    """Run all environment checks."""
    timestamp = datetime.now(timezone.utc).isoformat()

    checks = {
        "timestamp": timestamp,
        "python": check_python(),
        "cuda": check_cuda(),
        "pytorch": check_pytorch(),
        "packages": check_packages(),
        "cpu": check_cpu(),
        "memory": check_memory(),
        "disk_space": check_disk_space(),
    }

    if primary_path and primary_path.exists():
        checks["custom_extensions"] = check_custom_extensions(primary_path)

    return checks


def format_markdown(results: dict[str, Any]) -> str:
    """Format results as Markdown."""
    lines = ["# Environment Check Report", ""]
    lines.append(f"**Timestamp:** {results['timestamp']}")
    lines.append("")

    # Python
    lines.append("## Python")
    p = results["python"]
    lines.append(f"- Version: `{p['version']}`")
    lines.append(f"- Executable: `{p['executable']}`")
    lines.append(f"- Platform: `{p['platform']}`")
    lines.append("")

    # CUDA
    lines.append("## CUDA")
    c = results["cuda"]
    if c.get("nvidia_smi"):
        lines.append(f"- Driver: `{c['nvidia_smi']}`")
    lines.append(f"- PyTorch CUDA: `{c.get('pytorch_cuda_version', 'N/A')}`")
    lines.append(f"- cuDNN: `{c.get('cudnn_version', 'N/A')}`")
    gpu_name = c.get("gpu_name")
    if gpu_name:
        lines.append(f"- GPU: `{gpu_name}`")
    lines.append(f"- BF16 support: `{c.get('bf16_supported', 'N/A')}`")
    lines.append("")

    # PyTorch
    lines.append("## PyTorch")
    pt = results["pytorch"]
    lines.append(f"- Version: `{pt.get('version', 'N/A')}`")
    lines.append(f"- CUDA available: `{pt.get('cuda_available', False)}`")
    lines.append(f"- `torch.compile`: `{pt.get('compile_available', False)}`")
    lines.append("")

    # CPU
    lines.append("## CPU")
    cpu = results["cpu"]
    lines.append(f"- Model: `{cpu.get('model_name', cpu.get('processor', 'N/A'))}`")
    lines.append(f"- Physical cores: `{cpu.get('physical_cores', 'N/A')}`")
    lines.append(f"- Logical cores: `{cpu.get('logical_cores', 'N/A')}`")
    lines.append("")

    # Memory
    mem = results.get("memory", {})
    if mem.get("total_gb"):
        lines.append("## Memory")
        lines.append(f"- Total: `{mem['total_gb']} GB`")
        lines.append(f"- Available: `{mem.get('available_gb', 'N/A')} GB`")
        lines.append("")

    # Disk
    lines.append("## Disk Space")
    disk = results.get("disk_space", {})
    lines.append(f"- Free: `{disk.get('free_gb', 'N/A')} GB`")
    lines.append(f"- Total: `{disk.get('total_gb', 'N/A')} GB`")
    lines.append(f"- Sufficient for reproduction: `{disk.get('sufficient', 'N/A')}`")
    lines.append("")

    # Packages
    lines.append("## Required Packages")
    for pkg, info in results.get("packages", {}).items():
        status = "✅" if info.get("installed") else "❌"
        ver = info.get("version", "")
        lines.append(f"- {status} `{pkg}`{f' ({ver})' if ver else ''}")
    lines.append("")

    # Extensions
    exts = results.get("custom_extensions", {})
    if exts.get("found"):
        lines.append("## Custom CUDA Extensions")
        for f in exts["found"]:
            lines.append(f"- Found: `{f}`")
        lines.append(f"- nvcc available: `{exts.get('nvcc_available', False)}`")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-format", choices=["json", "markdown"], default="json")
    parser.add_argument("--primary", type=Path, help="Path to primary repository")
    args = parser.parse_args()

    primary_path = args.primary or Path("primary")
    results = run_full_check(args.output_format, primary_path)

    if args.output_format == "markdown":
        print(format_markdown(results))
    else:
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
