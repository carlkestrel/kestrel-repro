# 故障排除

## 快速诊断

### 运行 Doctor

```bash
python scripts/reproctl.py doctor --project .
```

Doctor 会检查：
- Python 环境
- 依赖
- GPU/CUDA
- 磁盘空间
- 配置文件
- Git 状态

### 查看状态

```bash
# Startup 状态
python scripts/reproctl.py status --project .

# Orchestrator 状态
python scripts/reproctl.py orchestrator status --project .
```

## 常见问题

### Q1: Doctor 检查失败怎么办？

**A**: 
1. 查看详细报告：`cat .repro/startup/doctor_report.json`
2. 找到 FAIL 项
3. 根据 fix 字段修复

常见 FAIL 及解决方案：

| FAIL 项 | 原因 | 解决方案 |
|---------|------|----------|
| cuda_match | CUDA 版本不匹配 | 安装正确版本或设置 --expected-cuda |
| disk_space | 磁盘空间不足 | 清理磁盘 |
| security | 敏感信息泄露 | 移除敏感信息 |

### Q2: 锁文件冲突？

**A**:
```bash
# 检查锁状态
cat .repro/run.lock

# 如果 PID 不存在，手动删除
rm .repro/run.lock

# 或停止旧实例
python scripts/reproctl.py stop --project .
```

### Q3: 恢复失败？

**A**:
```bash
# 检查状态文件
cat .repro/execution/execution_state.json

# 如果 corrupt，手动修复或删除
rm .repro/execution/execution_state.json

# 重新启动
python scripts/reproctl.py start --project . --plan output/PAPER_PLAN.md --dry-run
```

### Q4: 任务一直卡住？

**A**:
1. 检查任务状态：`python scripts/reproctl.py orchestrator status --project .`
2. 查看事件日志：`python scripts/reproctl.py orchestrator events --project . --limit 20`
3. 查看任务日志：`cat .repro/execution/tasks/<task-id>.log`

可能原因：
- 等待审批（WAITING_APPROVAL）
- 等待依赖（依赖任务未完成）
- 进程挂起

### Q5: GPU 不可用？

**A**:
```bash
# 检查 CUDA
python -c "import torch; print(torch.cuda.is_available())"

# 检查 nvidia-smi
nvidia-smi

# 检查驱动
cat /proc/driver/nvidia/version
```

解决方案：
1. 安装/更新 NVIDIA 驱动
2. 安装正确版本的 CUDA
3. 安装 PyTorch with CUDA support
4. 或设置 REPRO_FAKE_GPU=0 跳过 GPU 检查

### Q6: SQLite 数据库锁定？

**A**:
```bash
# 检查 WAL 文件
ls -la .repro/execution/state.sqlite3*

# 删除 WAL
rm .repro/execution/state.sqlite3-wal
rm .repro/execution/state.sqlite3-shm

# 重启
python scripts/reproctl.py orchestrator stop --project .
python scripts/reproctl.py orchestrator daemon --project . start --plan output/PAPER_PLAN.md
```

### Q7: 训练 OOM？

**A**:
1. 减小 batch size
2. 减小图像分辨率
3. 启用 AMP（混合精度）
4. 启用 gradient checkpointing

```bash
python scripts/reproctl.py launch --mode optimized_repro_safe --epochs 300
```

### Q8: 模块导入失败？

**A**:
```bash
# 检查 Python 路径
python -c "import sys; print(sys.path)"

# 检查安装
pip show dl-paper-repro

# 重新安装
pip install -e .
```

### Q9: Schema 验证失败？

**A**:
```bash
# 运行完整性检查
python scripts/reproctl.py integrity-check

# 检查 Schema 文件
ls schemas/*.schema.json

# 验证 JSON
python -c "import json; json.load(open('schemas/plan.schema.json'))"
```

### Q10: 无法批准任务？

**A**:
```bash
# 查看待审批
python scripts/reproctl.py orchestrator status --project .

# 使用 approval ID
python scripts/reproctl.py orchestrator approve --project . apr_xxxxx

# 或使用 task ID
python scripts/reproctl.py orchestrator approve --project . task-001
```

## 诊断命令清单

```bash
# 1. 环境诊断
python scripts/reproctl.py doctor --project .

# 2. 状态诊断
python scripts/reproctl.py status --project .
python scripts/reproctl.py orchestrator status --project .

# 3. 事件诊断
python scripts/reproctl.py orchestrator events --project . --limit 50

# 4. 日志诊断
tail -f .repro/startup/startup.log
tail -f .repro/execution/daemon.log

# 5. 完整性诊断
python scripts/reproctl.py orchestrator integrity-check --project .
python scripts/reproctl.py integrity-check
```

## 获取帮助

### 查看命令帮助

```bash
python scripts/reproctl.py --help
python scripts/reproctl.py start --help
python scripts/reproctl.py doctor --help
```

### 查看架构文档

```bash
cat docs/architecture.md
cat docs/quickstart.md
cat docs/command_reference.md
```

### 查看日志

```bash
# 启动日志
cat .repro/startup/startup.log

# Daemon 日志
cat .repro/execution/daemon.log

# 任务日志
cat .repro/execution/tasks/*.log
```
