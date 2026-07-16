# 自动化工作流

## 概述

自动化工作流用于无监控运行长时间任务。

## 模式选择

### 1. 安全自动 (safe-auto)

默认模式。需要人工审批关键决策。

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md \
  --automation safe-auto
```

### 2. 手动模式 (manual)

所有任务都需要人工审批。

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md \
  --automation manual
```

### 3. 无监控模式 (unattended)

不等待审批，超时后自动跳过或失败。

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md \
  --automation unattended
```

## 守护进程模式

### 启动守护进程

```bash
python scripts/reproctl.py orchestrator daemon \
  --project . \
  start \
  --plan output/PAPER_PLAN.md \
  --mode optimized
```

### 检查守护进程状态

```bash
python scripts/reproctl.py orchestrator daemon \
  --project . \
  status
```

输出示例：
```json
{
  "project_root": "/path/to/project",
  "pid": 12345,
  "status": "RUNNING",
  "heartbeat": {
    "owner": "controller",
    "pid": 12345,
    "timestamp": 1234567890.123,
    "detail": {...}
  }
}
```

### 停止守护进程

```bash
python scripts/reproctl.py orchestrator daemon \
  --project . \
  stop
```

## 运行策略

### 直到完成或阻塞

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md \
  --until blocked-or-complete
```

### 直到完成

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md \
  --until complete
```

### 无限期运行

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md
```

## 策略文件

### 创建策略文件

```json
{
  "policy_id": "custom-policy",
  "rules": [
    {
      "condition": "task.gate == 'gate_0_paper_audit'",
      "action": "auto_approve"
    },
    {
      "condition": "task.timeout_min > 60",
      "action": "require_approval"
    }
  ],
  "defaults": {
    "approval_required": false,
    "retry_on_failure": true,
    "max_retries": 3
  }
}
```

### 使用策略文件

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md \
  --policy /path/to/policy.json
```

## 暂停和继续

### 暂停

```bash
python scripts/reproctl.py orchestrator pause --project .
```

### 继续

```bash
python scripts/reproctl.py orchestrator continue --project .
```

## 恢复模式

### 从中断恢复

```bash
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md \
  --resume
```

## 环境配置

### GPU 模拟（无 GPU 环境）

```bash
export REPRO_FAKE_GPU=0
python scripts/reproctl.py doctor --project .
```

### CUDA 版本模拟

```bash
export REPRO_FAKE_CUDA=11.8
python scripts/reproctl.py doctor --project . --expected-cuda 11.8
```

### 磁盘空间模拟

```bash
export REPRO_FAKE_DISK_FREE=1073741824  # 1GB
python scripts/reproctl.py doctor --project .
```

## 日志管理

### 查看启动日志

```bash
tail -f .repro/startup/startup.log
```

### 查看 Daemon 日志

```bash
tail -f .repro/execution/daemon.log
```

### 查看任务日志

```bash
tail -f .repro/execution/tasks/<task-id>.log
```

## 通知

### 检查事件

```bash
python scripts/reproctl.py orchestrator events --project . --limit 10
```

### 实时事件流

```bash
# 持续监控
while true; do
  python scripts/reproctl.py orchestrator events --project . --limit 1
  sleep 5
done
```

## 自动化脚本示例

### 示例：无人值守训练

```bash
#!/bin/bash
set -e

PROJECT=$1
PLAN=${2:-output/PAPER_PLAN.md}

echo "Starting unattended training for $PROJECT"

# 预检
python scripts/reproctl.py doctor --project "$PROJECT" || {
  echo "Doctor check failed"
  exit 3
}

# 启动守护进程
python scripts/reproctl.py orchestrator daemon \
  --project "$PROJECT" \
  start \
  --plan "$PLAN" \
  --automation unattended

# 等待完成或阻塞
while true; do
  STATUS=$(python scripts/reproctl.py orchestrator daemon \
    --project "$PROJECT" \
    status 2>/dev/null | jq -r '.status')
  
  if [ "$STATUS" = "STOPPED" ]; then
    echo "Training completed or stopped"
    break
  elif [ "$STATUS" = "STALE" ]; then
    echo "Daemon became stale, restarting..."
    python scripts/reproctl.py orchestrator daemon \
      --project "$PROJECT" \
      start \
      --plan "$PLAN" \
      --automation unattended
  fi
  
  sleep 60
done

# 验证结果
python scripts/reproctl.py verify --project "$PROJECT"
```

## 故障处理

### 进程崩溃

1. 检查状态：
```bash
python scripts/reproctl.py orchestrator daemon status --project .
```

2. 重启：
```bash
python scripts/reproctl.py orchestrator daemon stop --project .
python scripts/reproctl.py orchestrator daemon start --project . --plan output/PAPER_PLAN.md
```

### 数据库锁定

```bash
# 检查锁
python scripts/reproctl.py status --project .

# 清理锁
rm -f .repro/execution/state.sqlite3-wal
rm -f .repro/execution/state.sqlite3-shm
```
