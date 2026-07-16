# Environment Card

> Canonical environment card. Filled in by `/repro-card`. Captures the
> full hardware/software/runtime context of a single reproduction run.

## Top overview (总览)

| Field | Value |
|---|---|
| Run id |  |
| Date (UTC+8) |  |
| Hostname |  |
| OS |  |
| GPU model + count |  |
| Total VRAM (GB) |  |
| Python |  |
| PyTorch |  |
| CUDA |  |
| **source:** | `experiments/<run_id>/env.json` |

---

## §1  Hardware (硬件)

- CPU model + core count
- RAM size + speed
- GPU model + driver version
- Storage type (NVMe / SSD / HDD)
- Interconnect (PCIe, NVLink)
- **source:** `experiments/<run_id>/env.json` + `nvidia-smi` snapshot

## §2  Software (软件)

- OS (kernel version)
- Python (with build)
- Conda/venv hash
- PyTorch + torchvision
- CUDA + cuDNN
- Domain libs (torch_geometric, mmcv, etc.)
- **source:** `experiments/<run_id>/env.json`

## §3  Container / venv hash (容器/虚拟环境)

- Dockerfile hash (if used)
- `pip freeze` hash
- Conda env hash
- **source:** `Dockerfile` + `pip-freeze.txt`

## §4  Determinism (确定性)

- cuDNN deterministic: True/False
- `CUBLAS_WORKSPACE_CONFIG`
- Seed policy (per-rank + global)
- `PYTHONHASHSEED`
- **source:** `experiments/<run_id>/run_manifest.json`

## §5  Resource benchmark (资源基准)

- Peak GPU util (%)
- Peak VRAM (GB)
- Peak CPU util (%)
- Throughput (samples/sec)
- **source:** `experiments/<run_id>/benchmark.json`

## §6  Distributed config (分布式)

- World size, rank, local_rank
- Backend (NCCL / Gloo)
- Init method
- **source:** `experiments/<run_id>/run_manifest.json`

## §7  Failure modes (失败模式)

- OOM during which epoch?
- Disk full?
- NCCL timeout?
- **source:** `experiments/<run_id>/failures.jsonl`

## §8  Cost (成本)

- Wall-clock (hours)
- GPU-hours (GPU_count × wall_clock)
- Approximate $ (if cloud)
- **source:** `experiments/<run_id>/cost.json`

---

## Appendix A — `nvidia-smi` snapshot

```
# <paste verbatim>
```

## Appendix B — `pip freeze`

```
# <paste verbatim>
```

## Appendix C — `git rev-parse HEAD`

```
# <paste verbatim>
```

## Appendix D — Disk layout

```
/home/user/proj/
├── data/
├── external/
├── experiments/
└── output/
```

## Appendix E — Re-run command

```bash
# Verbatim command that reproduces the run, byte-for-byte.
```
- **source:** `experiments/<run_id>/run_manifest.json` `command` field