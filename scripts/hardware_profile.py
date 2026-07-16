#!/usr/bin/env python3
"""
hardware_profile.py

Profiles local hardware and generates a hardware profile report.
Captures GPU model, VRAM, CPU, RAM, disk, and PyTorch/CUDA compatibility info.

Usage:
    python hardware_profile.py [--output=hardware_profile.json]
"""

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_cmd(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"


def profile_gpu() -> dict[str, Any]:
    """Profile GPU hardware."""
    profile = {
        "available": False,
        "devices": [],
    }

    rc, stdout, stderr = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,compute_cap,driver_version",
                                   "--format=csv,noheader,nounits"])
    if rc == 0 and stdout.strip():
        profile["available"] = True
        for i, line in enumerate(stdout.strip().split("\n")):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                profile["devices"].append({
                    "id": i,
                    "name": parts[0],
                    "memory_total_mb": int(parts[1]),
                    "memory_free_mb": int(parts[2]),
                    "compute_capability": parts[3],
                    "driver_version": parts[4],
                })
    else:
        profile["error"] = stderr.strip() or "nvidia-smi not available"

    # Additional GPU details
    try:
        import torch
        if torch.cuda.is_available():
            profile["pytorch_cuda_version"] = torch.version.cuda
            profile["pytorch_bf16_supported"] = torch.cuda.is_bf16_supported()
            profile["pytorch_tf32_supported"] = (
                hasattr(torch.backends.cuda, "matmul") and
                torch.backends.cuda.matmul.allow_tf32
            ) if hasattr(torch, "backends") else False
            profile["cudnn_version"] = torch.backends.cudnn.version()
            profile["gpu_count"] = torch.cuda.device_count()

            # Memory info per device
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                profile["devices"][i]["compute_capability_nv"] = f"{props.major}.{props.minor}"
                profile["devices"][i]["total_memory_bytes"] = props.total_memory
                profile["devices"][i]["total_memory_gb"] = round(props.total_memory / 1e9, 2)
                profile["devices"][i]["multi_processor_count"] = props.multi_processor_count
    except ImportError:
        profile["pytorch_available"] = False

    return profile


def profile_cpu() -> dict[str, Any]:
    """Profile CPU hardware."""
    profile = {
        "processor": platform.processor(),
        "model": None,
        "physical_cores": None,
        "logical_cores": None,
        "architecture": platform.machine(),
    }

    rc, stdout, _ = run_cmd(["lscpu"])
    if rc == 0:
        for line in stdout.split("\n"):
            if "Model name" in line:
                profile["model"] = line.split(":", 1)[1].strip()
            elif "Core(s) per socket" in line:
                cores_per_socket = int(line.split()[-1])
            elif "Socket(s)" in line:
                sockets = int(line.split()[-1])
                if "cores_per_socket" in dir():
                    profile["physical_cores"] = cores_per_socket * sockets
            elif "Thread(s) per core" in line:
                profile["threads_per_core"] = int(line.split()[-1])
            elif "Logical cores" in line:
                profile["logical_cores"] = int(line.split()[-1])
            elif "CPU(s)" in line and "list" not in line.lower():
                # This is often the total logical cores
                if profile.get("logical_cores") is None:
                    profile["logical_cores"] = int(line.split()[-1])

    # Override with actual computation if we got socket info
    if profile.get("physical_cores") is None and profile.get("logical_cores"):
        profile["physical_cores"] = profile["logical_cores"]

    return profile


def profile_memory() -> dict[str, Any]:
    """Profile RAM."""
    profile = {}

    try:
        import shutil
        mem = shutil.mem_info()
        profile["total_gb"] = round(mem[0] / (1024 ** 3), 2)
        profile["available_gb"] = round(mem[1] / (1024 ** 3), 2)
        profile["used_gb"] = round(profile["total_gb"] - profile["available_gb"], 2)
    except Exception:
        pass

    rc, stdout, _ = run_cmd(["free", "-h"])
    if rc == 0:
        profile["free_output"] = stdout.strip()

    return profile


def profile_disk(path: str = ".") -> dict[str, Any]:
    """Profile disk space and type."""
    import shutil
    profile = {"path": str(Path(path).resolve())}

    try:
        usage = shutil.disk_usage(path)
        profile["total_gb"] = round(usage.total / 1e9, 1)
        profile["free_gb"] = round(usage.free / 1e9, 1)
        profile["used_percent"] = round((usage.used / usage.total) * 100, 1)
    except Exception as e:
        profile["error"] = str(e)

    # Detect disk type (SSD vs HDD) — Linux only heuristic
    rc, stdout, _ = run_cmd(["lsblk", "-d", "-o", "TYPE", "-n"])
    if rc == 0:
        lines = [l.strip() for l in stdout.strip().split("\n") if l.strip()]
        profile["ssd_probability"] = "nvme" in stdout.lower() or "ssd" in stdout.lower()

    return profile


def profile_pytorch() -> dict[str, Any]:
    """Profile PyTorch installation."""
    profile = {"available": False}
    try:
        import torch
        profile["available"] = True
        profile["version"] = torch.__version__
        profile["cuda_available"] = torch.cuda.is_available()
        profile["cuda_version"] = torch.version.cuda
        profile["cudnn_version"] = torch.backends.cudnn.version()
        profile["distributed_available"] = hasattr(torch, "distributed")
        profile["compile_available"] = hasattr(torch, "compile")
        profile["amp_available"] = hasattr(torch.cuda.amp, "autocast")

        if torch.cuda.is_available():
            profile["gpu_count"] = torch.cuda.device_count()
    except ImportError:
        profile["error"] = "PyTorch not installed"
    return profile


def compute_recommendations(gpu_profile: dict, cpu_profile: dict,
                           memory_profile: dict, disk_profile: dict) -> dict[str, Any]:
    """Compute hardware recommendations."""
    recs = {}

    # GPU-based recommendations
    if gpu_profile.get("available"):
        device = gpu_profile["devices"][0] if gpu_profile["devices"] else {}
        vram_gb = device.get("memory_total_mb", 0) / 1024
        compute_cap = device.get("compute_capability", "0.0")

        # Batch size recommendation
        if vram_gb >= 24:
            recs["recommended_batch"] = 8
            recs["batch_tier"] = "large"
        elif vram_gb >= 16:
            recs["recommended_batch"] = 4
            recs["batch_tier"] = "medium"
        elif vram_gb >= 8:
            recs["recommended_batch"] = 2
            recs["batch_tier"] = "small"
        else:
            recs["recommended_batch"] = 1
            recs["batch_tier"] = "minimal"

        # Precision recommendations
        recs["amp_safe"] = True
        recs["bf16_safe"] = float(compute_cap.split(".")[0] if "." in str(compute_cap) else "0") >= 8
        recs["tf32_safe"] = recs["bf16_safe"]

        # Memory efficiency mode
        recs["gradient_checkpointing_recommended"] = vram_gb < 16

    # CPU-based recommendations
    logical_cores = cpu_profile.get("logical_cores", 4)
    recs["recommended_dataloader_workers"] = min(logical_cores, 8)
    recs["dataloader_workers_note"] = "Set num_workers based on CPU cores, capped at 8"

    # RAM-based recommendations
    total_ram = memory_profile.get("total_gb", 0)
    if total_ram >= 64:
        recs["data_caching_safe"] = True
    elif total_ram >= 32:
        recs["data_caching_safe"] = "partial"
    else:
        recs["data_caching_safe"] = False

    # Disk-based recommendations
    free_disk = disk_profile.get("free_gb", 0)
    recs["disk_space_sufficient"] = free_disk > 50
    recs["estimated_checkpoint_storage_gb"] = 5  # Conservative estimate

    return recs


def run_full_profile() -> dict[str, Any]:
    """Run all hardware profiling."""
    timestamp = datetime.now(timezone.utc).isoformat()

    gpu = profile_gpu()
    cpu = profile_cpu()
    mem = profile_memory()
    disk = profile_disk()
    pytorch = profile_pytorch()

    recs = compute_recommendations(gpu, cpu, mem, disk)

    return {
        "timestamp": timestamp,
        "gpu": gpu,
        "cpu": cpu,
        "memory": mem,
        "disk": disk,
        "pytorch": pytorch,
        "recommendations": recs,
    }


def format_markdown(profile: dict[str, Any]) -> str:
    """Format profile as Markdown."""
    lines = ["# Hardware Profile", ""]
    lines.append(f"**Timestamp:** {profile['timestamp']}")
    lines.append("")

    # GPU
    lines.append("## GPU")
    gpu = profile["gpu"]
    if gpu.get("available"):
        for device in gpu.get("devices", []):
            lines.append(f"- **GPU {device['id']}**: {device['name']}")
            lines.append(f"  - VRAM: {device['memory_total_mb'] / 1024:.1f} GB")
            lines.append(f"  - Compute capability: {device.get('compute_capability', 'N/A')}")
            lines.append(f"  - Driver: {device.get('driver_version', 'N/A')}")
            if gpu.get("pytorch_bf16_supported"):
                lines.append("  - BF16: supported")
            if gpu.get("pytorch_tf32_supported"):
                lines.append("  - TF32: supported")
    else:
        lines.append(f"- No GPU detected: {gpu.get('error', 'unknown error')}")
    lines.append("")

    # CPU
    lines.append("## CPU")
    cpu = profile["cpu"]
    lines.append(f"- Model: {cpu.get('model', cpu.get('processor', 'N/A'))}")
    lines.append(f"- Physical cores: {cpu.get('physical_cores', 'N/A')}")
    lines.append(f"- Logical cores: {cpu.get('logical_cores', 'N/A')}")
    lines.append("")

    # Memory
    lines.append("## Memory")
    mem = profile["memory"]
    lines.append(f"- Total: {mem.get('total_gb', 'N/A')} GB")
    lines.append(f"- Available: {mem.get('available_gb', 'N/A')} GB")
    lines.append("")

    # Disk
    lines.append("## Disk")
    disk = profile["disk"]
    lines.append(f"- Free: {disk.get('free_gb', 'N/A')} GB")
    lines.append(f"- Total: {disk.get('total_gb', 'N/A')} GB")
    lines.append(f"- SSD likely: {disk.get('ssd_probability', 'unknown')}")
    lines.append("")

    # PyTorch
    lines.append("## PyTorch")
    pt = profile["pytorch"]
    lines.append(f"- Version: {pt.get('version', 'N/A')}")
    lines.append(f"- CUDA available: {pt.get('cuda_available', False)}")
    lines.append(f"- CUDA version: {pt.get('cuda_version', 'N/A')}")
    lines.append(f"- cuDNN: {pt.get('cudnn_version', 'N/A')}")
    lines.append(f"- `torch.compile`: {pt.get('compile_available', False)}")
    lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    recs = profile.get("recommendations", {})
    lines.append(f"- Recommended batch size: `{recs.get('recommended_batch', 'N/A')}` ({recs.get('batch_tier', 'unknown')})")
    lines.append(f"- Recommended dataloader workers: `{recs.get('recommended_dataloader_workers', 'N/A')}`")
    lines.append(f"- AMP safe: `{recs.get('amp_safe', 'unknown')}`")
    lines.append(f"- BF16 safe: `{recs.get('bf16_safe', 'unknown')}`")
    lines.append(f"- Gradient checkpointing recommended: `{recs.get('gradient_checkpointing_recommended', 'unknown')}`")
    lines.append(f"- Disk space sufficient: `{recs.get('disk_space_sufficient', 'unknown')}`")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument("--markdown", action="store_true", help="Output as Markdown")
    args = parser.parse_args()

    profile = run_full_profile()

    if args.markdown:
        print(format_markdown(profile))
    else:
        output = json.dumps(profile, indent=2, default=str)
        if args.output:
            args.output.write_text(output)
            print(f"Hardware profile saved to {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
