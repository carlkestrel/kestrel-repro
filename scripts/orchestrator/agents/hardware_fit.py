"""
Hardware Fit Agent - NORA-style specialist for hardware compatibility checking.

This agent evaluates hardware requirements and provides fit recommendations.
"""
from __future__ import annotations

import subprocess
from typing import Any

from .base import (
    AgentRegistry,
    AgentResult,
    HandoffContext,
    SpecialistAgent,
)


class HardwareFitAgent(SpecialistAgent):
    """
    Agent for hardware fit analysis.

    Responsibilities:
    - Detect available hardware (GPU, memory, etc.)
    - Evaluate hardware requirements
    - Provide fit recommendations
    - Prepare handoff for EvidenceVerifierAgent
    """

    agent_type = "hardware-fit"
    agent_name = "HardwareFitAgent"
    description = "Evaluates hardware compatibility and provides fit recommendations"
    capabilities = [
        "gpu_detection",
        "memory_analysis",
        "compute_estimate",
        "fit_recommendation",
    ]
    next_agents = ["evidence-verifier"]

    def execute(self, context: HandoffContext) -> AgentResult:
        """Execute hardware fit analysis."""
        method_summary = context.data.get("method_summary", {})
        requirements = context.data.get("requirements", [])
        repositories = context.data.get("repositories", [])

        hardware_info = self._detect_hardware()
        requirements_analysis = self._analyze_requirements(requirements)
        fit_recommendation = self._evaluate_fit(hardware_info, requirements_analysis)

        config = self._generate_config(hardware_info, fit_recommendation)

        self.prepare_handoff(context, {
            "hardware_info": hardware_info,
            "requirements_analysis": requirements_analysis,
            "fit_recommendation": fit_recommendation,
            "config": config,
        })

        return AgentResult(
            agent_type=self.agent_type,
            agent_id=self.agent_id,
            status="success",
            output={
                "hardware_info": hardware_info,
                "requirements_analysis": requirements_analysis,
                "fit_recommendation": fit_recommendation,
                "config": config,
            },
            handoff={
                "hardware_info": hardware_info,
                "fit_recommendation": fit_recommendation,
                "config": config,
                "next_agent": "evidence-verifier",
            },
            metadata={
                "complexity": method_summary.get("complexity", "unknown"),
                "gpu_available": hardware_info.get("gpu", {}).get("available", False),
            },
        )

    def _detect_hardware(self) -> dict[str, Any]:
        """Detect available hardware."""
        info = {
            "cpu": self._detect_cpu(),
            "memory": self._detect_memory(),
            "gpu": self._detect_gpu(),
            "disk": self._detect_disk(),
        }

        info["compute_score"] = self._calculate_compute_score(info)

        return info

    def _detect_cpu(self) -> dict[str, Any]:
        """Detect CPU information."""
        cpu_info = {
            "name": "Unknown",
            "cores": 1,
            "threads": 1,
        }

        try:
            result = subprocess.run(
                ["nproc"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                cpu_info["threads"] = int(result.stdout.strip())
                cpu_info["cores"] = cpu_info["threads"]
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["cat", "/proc/cpuinfo"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "model name" in line:
                        cpu_info["name"] = line.split(":")[1].strip()
                        break
        except Exception:
            pass

        return cpu_info

    def _detect_memory(self) -> dict[str, Any]:
        """Detect memory information."""
        mem_info = {
            "total_gb": 0,
            "available_gb": 0,
        }

        try:
            result = subprocess.run(
                ["free", "-b"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        mem_info["total_gb"] = int(parts[1]) / (1024**3)
                    if len(parts) >= 7:
                        mem_info["available_gb"] = int(parts[6]) / (1024**3)
        except Exception:
            pass

        return mem_info

    def _detect_gpu(self) -> dict[str, Any]:
        """Detect GPU information."""
        gpu_info = {
            "available": False,
            "devices": [],
            "type": "none",
        }

        try:
            import torch

            if torch.cuda.is_available():
                gpu_info["available"] = True
                gpu_info["type"] = "cuda"
                gpu_info["device_count"] = torch.cuda.device_count()

                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    gpu_info["devices"].append({
                        "id": i,
                        "name": torch.cuda.get_device_name(i),
                        "total_memory_gb": props.total_memory / (1024**3),
                        "compute_capability": f"{props.major}.{props.minor}",
                    })
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                gpu_info["available"] = True
                gpu_info["type"] = "mps"
                gpu_info["devices"].append({
                    "id": 0,
                    "name": "Apple Silicon GPU (MPS)",
                    "total_memory_gb": 0,
                    "compute_capability": "mps",
                })

        except ImportError:
            pass

        if not gpu_info["available"]:
            try:
                result = subprocess.run(
                    ["nvidia-smi"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    gpu_info["available"] = True
                    gpu_info["type"] = "nvidia-smi"
            except Exception:
                pass

        return gpu_info

    def _detect_disk(self) -> dict[str, Any]:
        """Detect disk information."""
        disk_info = {
            "free_gb": 0,
            "total_gb": 0,
        }

        try:
            import shutil
            usage = shutil.disk_usage("/")
            disk_info["free_gb"] = usage.free / (1024**3)
            disk_info["total_gb"] = usage.total / (1024**3)
        except Exception:
            pass

        return disk_info

    def _calculate_compute_score(self, hardware_info: dict[str, Any]) -> float:
        """Calculate overall compute score."""
        score = 0.0

        cpu_threads = hardware_info.get("cpu", {}).get("threads", 1)
        score += min(cpu_threads * 0.5, 50)

        mem_gb = hardware_info.get("memory", {}).get("total_gb", 0)
        score += min(mem_gb * 2, 100)

        gpu = hardware_info.get("gpu", {})
        if gpu.get("available"):
            gpu_devices = gpu.get("devices", [])
            for device in gpu_devices:
                mem_gb = device.get("total_memory_gb", 0)
                score += min(mem_gb * 10, 200)
            score += 100

        return score

    def _analyze_requirements(self, requirements: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze hardware requirements from paper."""
        analysis = {
            "estimated_memory_gb": 4,
            "estimated_compute_tflops": 1,
            "estimated_disk_gb": 10,
            "requires_gpu": False,
            "complexity": "small",
        }

        for req in requirements:
            if req.get("type") == "hardware":
                desc = req.get("description", "").lower()
                if "gpu" in desc or "cuda" in desc:
                    analysis["requires_gpu"] = True
                if "large" in desc:
                    analysis["complexity"] = "large"
                    analysis["estimated_memory_gb"] = 16
                elif "medium" in desc:
                    analysis["complexity"] = "medium"
                    analysis["estimated_memory_gb"] = 8

        return analysis

    def _evaluate_fit(self, hardware_info: dict[str, Any],
                      requirements: dict[str, Any]) -> dict[str, Any]:
        """Evaluate hardware fit."""
        fit = {
            "score": 0,
            "status": "unknown",
            "issues": [],
            "recommendations": [],
        }

        mem_available = hardware_info.get("memory", {}).get("available_gb", 0)
        mem_required = requirements.get("estimated_memory_gb", 4)

        if mem_available < mem_required:
            fit["issues"].append(f"Insufficient memory: {mem_available:.1f}GB available, {mem_required:.1f}GB required")
        else:
            fit["score"] += 50

        if requirements.get("requires_gpu", False):
            if not hardware_info.get("gpu", {}).get("available"):
                fit["issues"].append("GPU required but not available")
                fit["status"] = "no-fit"
            else:
                gpu_mem = sum(d.get("total_memory_gb", 0) for d in hardware_info.get("gpu", {}).get("devices", []))
                if gpu_mem < mem_required:
                    fit["issues"].append(f"Insufficient GPU memory: {gpu_mem:.1f}GB available")
                else:
                    fit["score"] += 50
        else:
            fit["score"] += 50

        if fit["score"] >= 80:
            fit["status"] = "good-fit"
            fit["recommendations"].append("Hardware is well-suited for this task")
        elif fit["score"] >= 50:
            fit["status"] = "partial-fit"
            fit["recommendations"].append("Hardware can run with some limitations")
        else:
            fit["status"] = "no-fit"
            fit["recommendations"].append("Consider upgrading hardware or reducing scope")

        return fit

    def _generate_config(self, hardware_info: dict[str, Any],
                        fit: dict[str, Any]) -> dict[str, Any]:
        """Generate configuration based on hardware."""
        config = {
            "device": "cpu",
            "batch_size": 8,
            "num_workers": 2,
            "mixed_precision": False,
            "gradient_checkpointing": False,
        }

        gpu = hardware_info.get("gpu", {})
        if gpu.get("available"):
            if gpu.get("type") == "cuda":
                config["device"] = "cuda"
            elif gpu.get("type") == "mps":
                config["device"] = "mps"

            total_gpu_mem = sum(d.get("total_memory_gb", 0) for d in gpu.get("devices", []))

            if total_gpu_mem >= 16:
                config["batch_size"] = 32
                config["mixed_precision"] = True
            elif total_gpu_mem >= 8:
                config["batch_size"] = 16
                config["mixed_precision"] = True
            else:
                config["batch_size"] = 8
                config["gradient_checkpointing"] = True

            config["num_workers"] = min(4, hardware_info.get("cpu", {}).get("threads", 4))

        return config


AgentRegistry.register(HardwareFitAgent)
