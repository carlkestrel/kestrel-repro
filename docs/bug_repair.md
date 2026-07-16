# Bug 修复

## 调试方法

### 启用调试日志

```bash
python scripts/reproctl.py doctor --project . --log-level DEBUG
python scripts/reproctl.py start --project . --log-level DEBUG
```

### 查看日志文件

```bash
# 启动日志
cat .repro/startup/startup.log

# Daemon 日志
cat .repro/execution/daemon.log

# 任务日志
cat .repro/execution/tasks/<task-id>.log
```

### 启用 SQLite 调试

```python
import sqlite3
conn = sqlite3.connect(".repro/execution/state.sqlite3", isolation_level=None)
conn.set_trace_callback(print)
```

## 常见问题

### 1. Doctor 检查失败

#### 症状
```
EXIT_DOCTOR_FAIL: 3
```

#### 排查步骤

```bash
# 查看详细报告
cat .repro/startup/doctor_report.json | python -m json.tool

# 单独运行 Doctor
python scripts/reproctl.py doctor --project .
```

#### 常见原因

| 检查 | 常见原因 | 解决方案 |
|------|----------|----------|
| gpu | CUDA 不可用 | 检查 CUDA 安装 |
| cuda_match | 版本不匹配 | 指定 --expected-cuda |
| disk_space | 空间不足 | 清理磁盘 |
| security | 凭证泄露 | 移除敏感信息 |

### 2. 锁文件问题

#### 症状
```
EXIT_ALREADY_RUNNING: 4
```

#### 排查步骤

```bash
# 检查锁状态
python scripts/reproctl.py status --project .

# 检查 PID 是否存在
cat .repro/run.lock
ps aux | grep <PID>
```

#### 解决方案

```bash
# 方法 1: 停止旧实例
python scripts/reproctl.py stop --project .

# 方法 2: 手动删除锁
rm .repro/run.lock
```

### 3. SQLite 数据库锁定

#### 症状
```
database is locked
```

#### 排查步骤

```bash
# 检查 WAL 文件
ls -la .repro/execution/state.sqlite3*

# 检查持有锁的进程
lsof .repro/execution/state.sqlite3
```

#### 解决方案

```bash
# 方法 1: 清理 WAL
rm .repro/execution/state.sqlite3-wal
rm .repro/execution/state.sqlite3-shm

# 方法 2: 重启进程
python scripts/reproctl.py orchestrator stop --project .
python scripts/reproctl.py orchestrator daemon --project . start --plan output/PAPER_PLAN.md
```

### 4. 恢复失败

#### 症状
```
EXIT_RESUME_FAILED: 8
```

#### 排查步骤

```bash
# 检查状态文件
cat .repro/execution/execution_state.json | python -m json.tool

# 检查计划文件
cat output/PAPER_PLAN.md | head -50
```

#### 解决方案

```bash
# 方法 1: 清理中断标志
# 编辑 .repro/execution/execution_state.json
# 设置 "interrupted": false

# 方法 2: 完全重置
rm -rf .repro/execution/*
python scripts/reproctl.py start --project . --plan output/PAPER_PLAN.md --dry-run
```

### 5. 任务执行失败

#### 排查步骤

```bash
# 查看任务状态
python scripts/reproctl.py orchestrator status --project .

# 查看事件日志
python scripts/reproctl.py orchestrator events --project . --limit 20

# 查看任务日志
cat .repro/execution/tasks/<task-id>.log
```

#### 常见原因

| 原因 | 解决方案 |
|------|----------|
| 超时 | 增加 timeout_min |
| 依赖失败 | 先完成依赖任务 |
| 命令错误 | 检查 command 字段 |
| 权限问题 | 检查文件权限 |

### 6. 审批流程卡住

#### 症状
任务一直处于 WAITING_APPROVAL 状态

#### 排查步骤

```bash
# 查看待审批
python scripts/reproctl.py orchestrator status --project .

# 查看审批历史
python scripts/reproctl.py orchestrator events --project . --limit 50 | grep APPROVAL
```

#### 解决方案

```bash
# 批准任务
python scripts/reproctl.py orchestrator approve --project . apr_xxxxx

# 拒绝并重试
python scripts/reproctl.py orchestrator reject --project . apr_xxxxx --reason "条件不满足"
```

## 调试技巧

### Python 调试器

```python
import pdb; pdb.set_trace()
```

### 打印调试

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### SQLite 直接查询

```bash
sqlite3 .repro/execution/state.sqlite3
sqlite> SELECT * FROM tasks;
sqlite> SELECT * FROM events ORDER BY seq DESC LIMIT 10;
```

## 报告 Bug

### 收集信息

```bash
# 系统信息
python scripts/reproctl.py version

# Doctor 报告
python scripts/reproctl.py doctor --project . > doctor_report.txt 2>&1

# 状态摘要
python scripts/reproctl.py orchestrator status --project . > status.json 2>&1

# 事件日志
python scripts/reproctl.py orchestrator events --project . > events.json 2>&1
```

### 复现步骤

提供：
1. 完整命令
2. 预期行为
3. 实际行为
4. 错误信息
5. 环境信息
