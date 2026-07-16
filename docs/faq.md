# FAQ

## 基础

### Q: reproctl.py 是什么？

**A**: `reproctl.py` 是 dl-paper-repro 的唯一 CLI 入口点。它负责分发命令到 startup 或 orchestrator 子系统。

### Q: 如何运行 reproctl？

**A**:
```bash
python scripts/reproctl.py <command>
```

或安装后：
```bash
reproctl <command>
```

### Q: Startup 和 Orchestrator 有什么区别？

**A**:
- **Startup**: 负责项目初始化、预检、锁管理
- **Orchestrator**: 负责任务调度、执行、监控

### Q: 需要什么环境？

**A**:
- Python 3.8+
- PyTorch (用于训练)
- CUDA 12.0+ (可选，用于 GPU)

## 命令

### Q: start 和 launch 有什么区别？

**A**:
- `start`: 启动 startup 子系统，用于项目初始化和任务调度
- `launch`: 启动 legacy 训练系统，用于直接运行训练

### Q: 如何检查项目状态？

**A**:
```bash
# Startup 状态
python scripts/reproctl.py status --project .

# Orchestrator 状态
python scripts/reproctl.py orchestrator status --project .

# Legacy 状态（Gate）
python scripts/reproctl.py status
```

### Q: 如何恢复中断的项目？

**A**:
```bash
python scripts/reproctl.py resume --project .
```

### Q: 如何停止正在运行的任务？

**A**:
```bash
python scripts/reproctl.py orchestrator stop --project .
# 或
python scripts/reproctl.py stop --project .
```

### Q: 如何批准待审批的任务？

**A**:
```bash
python scripts/reproctl.py orchestrator approve --project . apr_xxxxx
```

## 模式

### Q: strict 和 optimized 模式有什么区别？

**A**:
| 特性 | strict | optimized |
|------|--------|-----------|
| 指标容差 | ±0.5 pp | ±0.5 pp |
| 训练优化 | 无 | AMP, DDP |
| 性能 | 慢 | 快 |
| Gate 3 要求 | 不需要 | 需要通过 |

### Q: 如何切换模式？

**A**:
编辑 `.repro/STATE.json`：
```json
{
  "project_mode": "diagnose"
}
```

或使用命令：
```bash
# 需要在 reproctl.py 中实现
```

## 状态

### Q: 任务卡在 WAITING_APPROVAL 怎么办？

**A**:
```bash
# 查看待审批
python scripts/reproctl.py orchestrator status --project .

# 批准
python scripts/reproctl.py orchestrator approve --project . apr_xxxxx

# 或拒绝
python scripts/reproctl.py orchestrator reject --project . apr_xxxxx --reason "原因"
```

### Q: 任务一直 PENDING 怎么办？

**A**:
可能原因：
1. 依赖任务未完成
2. 调度器问题
3. 数据库锁定

解决方案：
```bash
# 检查依赖
python scripts/reproctl.py orchestrator events --project . | grep TASK_CREATED

# 重启 orchestrator
python scripts/reproctl.py orchestrator stop --project .
python scripts/reproctl.py orchestrator daemon --project . start --plan output/PAPER_PLAN.md
```

### Q: 状态文件 corrupt 了怎么办？

**A**:
```bash
# 备份
cp .repro/execution/execution_state.json .repro/execution/execution_state.json.bak

# 修复或删除
rm .repro/execution/execution_state.json

# 重新启动
python scripts/reproctl.py start --project . --plan output/PAPER_PLAN.md --dry-run
```

## 数据

### Q: 备份保存在哪里？

**A**:
默认在项目目录的 `.repro/backup/` 下，可通过 `--output-dir` 指定。

### Q: 如何清理旧的检查点？

**A**:
```bash
# 查看清理计划
python scripts/reproctl.py storage plan-cleanup --project .

# 执行清理
python scripts/reproctl.py storage cleanup --project . --approved-plan cleanup.json
```

### Q: 训练日志在哪里？

**A**:
- 启动日志：`.repro/startup/startup.log`
- Daemon 日志：`.repro/execution/daemon.log`
- 任务日志：`.repro/execution/tasks/<task-id>.log`

## 开发

### Q: 如何添加新命令？

**A**:
1. 在 `scripts/startup/cli.py` 或 `scripts/orchestrator/cli.py` 添加命令处理器
2. 在 argparse 子解析器中注册
3. 在 `HANDLERS` 字典中注册

### Q: 如何添加新 Doctor 检查？

**A**:
在 `scripts/startup/doctor.py` 中添加检查函数：

```python
def _check_new_item() -> dict:
    # 实现检查
    return {"name": "new_item", "status": "PASS", "message": "..."}
```

然后在 `run()` 函数的 `checks` 列表中添加。

### Q: 如何测试新功能？

**A**:
```bash
# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行特定测试
pytest tests/unit/test_new_feature.py -v
```

## 故障

### Q: Doctor 一直 FAIL？

**A**:
```bash
# 查看详细报告
cat .repro/startup/doctor_report.json | python -m json.tool

# 逐项修复
```

### Q: GPU 检测失败？

**A**:
```bash
# 检查 CUDA
python -c "import torch; print(torch.cuda.is_available())"

# 检查 nvidia-smi
nvidia-smi

# 跳过 GPU 检查（测试用）
export REPRO_FAKE_GPU=0
```

### Q: 权限问题？

**A**:
```bash
# 检查文件权限
ls -la .repro/

# 修复权限
chmod 755 .
chmod 755 .repro/
chmod 644 .repro/*.json
```

### Q: 网络问题？

**A**:
```bash
# 检查网络
ping github.com

# 克隆仓库
git clone https://github.com/user/repo.git

# 离线模式
export REPRO_ALLOW_NETWORK=false
```
