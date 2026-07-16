# 硬件与性能

## GPU 要求

### 最低要求

| 规格 | 要求 |
|------|------|
| 显存 | 8 GB |
| 计算能力 | 7.0+ |
| CUDA | 11.0+ |

### 推荐配置

| 规格 | 推荐 |
|------|------|
| 显存 | 16-24 GB |
| 计算能力 | 8.0+ |
| CUDA | 12.0+ |
| 多卡 | 2-4 卡 |

## GPU 检测

```bash
python scripts/reproctl.py doctor --project .
```

Doctor 检查项：
- `gpu`: GPU 可用性
- `cuda_match`: CUDA 版本匹配
- `driver`: NVIDIA 驱动
- `torch`: PyTorch 安装

## GPU 模拟

### 无 GPU 环境

```bash
export REPRO_FAKE_GPU=0
python scripts/reproctl.py doctor --project .
```

### CUDA 版本模拟

```bash
export REPRO_FAKE_CUDA=12.0
python scripts/reproctl.py doctor --project . --expected-cuda 12.0
```

## 性能优化

### 混合精度 (AMP)

启用 AMP 可加速训练并减少显存：

```bash
python scripts/reproctl.py launch --mode optimized_repro_safe --epochs 300
```

### 分布式训练 (DDP)

多卡训练：

```bash
# 单机多卡
torchrun --nproc_per_node=2 train.py

# 多机多卡
torchrun --nnodes=2 --nproc_per_node=2 --master_addr=$ADDR train.py
```

### 梯度累积

大 batch size 通过梯度累积实现：

```bash
python train.py --effective-batch-size 2048 --gradient-accumulation-steps 8
```

## 显存优化

### 检查显存使用

```bash
nvidia-smi
watch -n 1 nvidia-smi
```

### 减少显存占用

1. 减小 batch size
2. 启用 gradient checkpointing
3. 使用 AMP
4. 启用 torch.cuda.empty_cache()

### 显存不足 (OOM)

如果遇到 OOM：
1. 减小 batch size
2. 减小图像分辨率
3. 启用 AMP
4. 使用更小的模型变体

## 性能监控

### 实时监控

```bash
python scripts/training_monitor.py --interval 5
```

### GPU 利用率

```bash
nvidia-smi dmon -s u
```

### 训练日志

检查 `.repro/execution/tasks/*/train.log`

## 性能调优

### 使用 Perf Tuner

```bash
python scripts/reproctl.py repro_perf_tuner.py \
  --config configs/perf.yaml \
  --target-gpu-hours 100
```

### 调优参数

- Batch size
- 学习率 (线性缩放)
- Warmup 步数
- 优化器参数

## 存储要求

### 最低磁盘空间

| 用途 | 空间 |
|------|------|
| 代码 | 1 GB |
| 数据集 | 视数据集而定 |
| 检查点 | 5-50 GB |
| 日志 | 1 GB |
| 总计 | 10-100 GB |

### 检查磁盘空间

```bash
python scripts/reproctl.py doctor --project .
# 检查 disk_space 项
```

### 存储治理

```bash
# 查看磁盘状态
python scripts/reproctl.py storage status --project .

# 生成清理计划
python scripts/reproctl.py storage plan-cleanup --project .

# 执行清理
python scripts/reproctl.py storage cleanup --project . --approved-plan cleanup.json
```

## 网络要求

### 必需

- PyPI/npm 包下载
- GitHub 仓库克隆

### 可选

- 数据集下载
- 模型权重下载

### 离线使用

对于离线环境：
1. 预先下载所有依赖
2. 使用 pip cache
3. 预先克隆仓库

## 硬件配置示例

### 单卡配置

```yaml
# repro.yaml
hardware:
  gpu_count: 1
  gpu_memory_gb: 24
  cpu_cores: 8
  ram_gb: 64
```

### 多卡配置

```yaml
# repro.yaml
hardware:
  gpu_count: 4
  gpu_memory_gb: 24
  cpu_cores: 32
  ram_gb: 128
  network: ib  # InfiniBand
```

## 故障排除

### GPU 不可见

```bash
# 检查 CUDA
python -c "import torch; print(torch.cuda.is_available())"

# 检查 nvidia-smi
nvidia-smi

# 检查驱动
cat /proc/driver/nvidia/version
```

### CUDA 版本不匹配

```bash
# 查看 PyTorch CUDA 版本
python -c "import torch; print(torch.version.cuda)"

# 查看驱动支持
nvidia-smi | head -4
```

### 性能下降

可能原因：
1. GPU 过热降频
2. 显存碎片化
3. CPU 瓶颈
4. I/O 瓶颈

解决方案：
1. 清理显存：`torch.cuda.empty_cache()`
2. 重启进程
3. 优化数据加载
4. 使用更快存储
