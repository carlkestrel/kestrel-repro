# 接管工作流

## 概述

接管工作流用于继续一个已中断或未完成的项目。

## 何时使用

- 项目被中断（网络断开、进程崩溃等）
- 需要在另一台机器继续
- 需要切换用户/权限继续
- 需要恢复失败的尝试

## 阶段 1：评估状态

### 1.1 检查项目状态

```bash
python scripts/reproctl.py status --project .
```

### 1.2 检查 Doctor 报告

```bash
cat .repro/startup/doctor_report.json
```

### 1.3 检查 Orchestrator 状态

```bash
python scripts/reproctl.py orchestrator status --project .
```

### 1.4 检查事件日志

```bash
python scripts/reproctl.py orchestrator events --project . --limit 50
```

## 阶段 2：清理（如需要）

### 2.1 检查残留进程

```bash
# 手动检查
ps aux | grep reproctl
```

### 2.2 停止旧实例

```bash
python scripts/reproctl.py stop --project .
python scripts/reproctl.py orchestrator daemon --project . stop
```

### 2.3 清除锁文件

```bash
rm -f .repro/run.lock
rm -f .repro/execution/controller.pid
```

## 阶段 3：恢复

### 3.1 尝试恢复

```bash
python scripts/reproctl.py resume --project .
```

### 3.2 检查恢复结果

```bash
python scripts/reproctl.py status --project .
```

## 阶段 4：处理问题

### 4.1 如果恢复失败

检查 `.repro/execution/execution_state.json`：

```bash
cat .repro/execution/execution_state.json | python -m json.tool
```

### 4.2 手动恢复任务状态

```bash
# 查看任务状态
python scripts/reproctl.py orchestrator status --project .

# 重置失败任务
# (需要直接操作 SQLite)
```

### 4.3 重新运行 Doctor

```bash
python scripts/reproctl.py doctor --project .
```

## 阶段 5：继续执行

### 5.1 启动 Orchestrator

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md \
  --resume
```

### 5.2 或者启动守护进程

```bash
python scripts/reproctl.py orchestrator daemon \
  --project . \
  start \
  --plan output/PAPER_PLAN.md
```

## 阶段 6：监控

### 6.1 监控状态

```bash
# 持续监控
watch -n 5 'python scripts/reproctl.py orchestrator status --project .'
```

### 6.2 监控事件

```bash
# 实时事件流
python scripts/reproctl.py orchestrator events --project . --limit 10
```

## 阶段 7：处理失败

### 7.1 分析失败原因

```bash
# 查看任务日志
cat .repro/execution/tasks/<task-id>.log

# 查看 daemon 日志
cat .repro/execution/daemon.log
```

### 7.2 更新任务状态

```bash
# 重试失败任务
# (需要通过 Orchestrator API)
```

### 7.3 记录失败

```bash
python scripts/reproctl.py record-experiment \
  EXP-FAIL-001 \
  task-module \
  failed \
  --run-id "$(uuidgen)" \
  --status-detail "失败原因"
```

## 备份和恢复

### 创建备份

```bash
python scripts/reproctl.py orchestrator backup \
  --project . \
  --include-checkpoints \
  --output-dir /path/to/backup
```

### 从备份恢复

```bash
# 列出备份
ls /path/to/backup/

# 恢复
python scripts/reproctl.py orchestrator restore \
  --project . \
  --snapshot SNAPSHOT_ID \
  --output-dir /path/to/restore
```

## 检查清单

- [ ] 旧实例已停止
- [ ] 锁文件已清除
- [ ] 状态已评估
- [ ] Doctor 检查通过
- [ ] 恢复成功
- [ ] Orchestrator 运行中
- [ ] 任务继续执行
