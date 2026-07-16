# 配置参考

本文档基于 `scripts/startup/config.py` 和相关代码提取。

## 1. 配置来源

配置按优先级从高到低合并：

1. CLI 参数
2. 环境变量 (`REPRO_*`)
3. 项目配置文件 (`.repro/config.yaml`, `repro.yaml`)
4. 默认值

## 2. 配置路径

| 路径 | 描述 |
|------|------|
| `.repro/config.yaml` | 项目本地配置 |
| `repro.yaml` | 项目根配置 |
| `output/PAPER_PLAN.md` | 计划文件（YAML frontmatter） |

## 3. 配置字段

### 3.1 Startup 配置

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `mode` | string | strict | 执行模式 |
| `expected_cuda` | string | - | 期望 CUDA 版本 |
| `log_level` | string | INFO | 日志级别 |
| `automation` | string | safe-auto | 自动化策略 |

### 3.2 执行模式

| 模式 | 描述 |
|------|------|
| `strict` | 严格复现模式（默认） |
| `optimized` | 优化模式（需 parity 测试） |
| `diagnose` | 诊断模式 |
| `test` | 测试模式 |
| `extend` | 扩展模式 |

### 3.3 日志级别

| 级别 | 描述 |
|------|------|
| `DEBUG` | 详细调试信息 |
| `INFO` | 信息（默认） |
| `WARNING` | 警告 |
| `ERROR` | 错误 |

### 3.4 自动化策略

| 策略 | 描述 |
|------|------|
| `safe-auto` | 安全自动（默认） |
| `manual` | 手动审批 |
| `unattended` | 无监控运行 |

### 3.5 Gate 状态

| 状态 | 描述 |
|------|------|
| `pending` | 待处理 |
| `passed` | 通过 |
| `failed` | 失败 |
| `skipped` | 跳过 |

### 3.6 Task 状态

| 状态 | 描述 |
|------|------|
| `PENDING` | 等待中 |
| `READY` | 就绪 |
| `RUNNING` | 运行中 |
| `VERIFYING` | 验证中 |
| `PASS` | 通过（终态） |
| `FAIL` | 失败 |
| `RETRY_WAIT` | 重试等待 |
| `WAITING_APPROVAL` | 等待审批 |
| `APPROVED` | 已批准 |
| `REJECTED` | 已拒绝（终态） |

### 3.7 Control 状态

| 状态 | 描述 |
|------|------|
| `RUNNING` | 运行中 |
| `PAUSED` | 暂停 |
| `STOPPED` | 已停止 |

### 3.8 Doctor 检查状态

| 状态 | 描述 |
|------|------|
| `PASS` | 通过 |
| `WARNING` | 警告（不阻塞） |
| `FAIL` | 失败（阻塞 start） |
| `BLOCKED` | 阻塞 |
| `UNSUPPORTED` | 不支持 |

## 4. 环境变量

| 变量 | 描述 |
|------|------|
| `REPRO_FAKE_GPU` | 设为 `0` 模拟无 GPU |
| `REPRO_FAKE_CUDA` | 模拟 CUDA 版本 |
| `REPRO_FAKE_DISK_FREE` | 模拟可用磁盘空间（字节） |
| `REPRO_ORCHESTRATOR_DAEMON` | 设为 `1` 表示 daemon 进程 |
| `WSL_DISTRO_NAME` | WSL 发行版名称 |
| `WSLENV` | WSL 环境变量 |

## 5. 锁文件路径

| 路径 | 描述 |
|------|------|
| `.repro/run.lock` | PID 文件锁 |
| `.repro/execution/controller.pid` | Controller PID |
| `.repro/execution/controller.heartbeat` | 心跳文件 |

## 6. 数据库路径

| 路径 | 描述 |
|------|------|
| `.repro/execution/state.sqlite3` | SQLite WAL 数据库 |

## 7. StateStore 表结构

### 7.1 metadata 表

```sql
CREATE TABLE metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
)
```

**常用键**:
- `control_state`: RUNNING/PAUSED/STOPPED
- `plan_id`: 计划 ID
- `plan_path`: 计划文件路径
- `mode`: 执行模式
- `automation`: 自动化策略
- `mandatory_task_ids`: 强制任务 ID 列表
- `budgets`: 预算配置

### 7.2 tasks 表

```sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  gate TEXT NOT NULL,
  deps_json TEXT NOT NULL,
  command TEXT NOT NULL,
  timeout_min REAL NOT NULL,
  acceptance_json TEXT NOT NULL,
  retry_json TEXT NOT NULL,
  task_json TEXT NOT NULL,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  pid INTEGER,
  log_path TEXT,
  started_at TEXT,
  finished_at TEXT,
  retry_at REAL,
  failure_reason TEXT,
  lock_owner TEXT,
  updated_at TEXT NOT NULL
)
```

### 7.3 approvals 表

```sql
CREATE TABLE approvals (
  approval_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL,
  expires_at REAL,
  decided_at TEXT
)
```

### 7.4 events 表

```sql
CREATE TABLE events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  event_type TEXT NOT NULL,
  task_id TEXT,
  payload_json TEXT NOT NULL
)
```

### 7.5 heartbeats 表

```sql
CREATE TABLE heartbeats (
  owner TEXT PRIMARY KEY,
  pid INTEGER NOT NULL,
  timestamp REAL NOT NULL,
  detail_json TEXT NOT NULL
)
```

## 8. Task JSON 结构

```json
{
  "id": "task-001",
  "name": "Task Name",
  "gate": "gate_0_paper_audit",
  "deps": ["dep-task-001"],
  "command": "python script.py",
  "timeout_min": 30,
  "acceptance_tests": [
    {
      "type": "exit_code",
      "expected": 0
    },
    {
      "type": "file_exists",
      "path": "output/metrics.json"
    }
  ],
  "retry_policy": {
    "max_attempts": 3,
    "delay_seconds": 60
  }
}
```

## 9. Plan JSON 结构

```json
{
  "plan_id": "plan-001",
  "mode": "strict",
  "tasks": [...],
  "approvals_required": true,
  "mandatory_task_ids": ["task-001"],
  "budgets": {
    "gpu_hours": 100,
    "storage_gb": 500
  }
}
```

## 10. 决策日志格式

```
| D000 | 2024-01-01T00:00:00+00:00 | agent | P1_discover | task-001 | mode_switch | reproduce → diagnose | 原因描述 | links |
```

**列**:
- id: 决策 ID (D000, D001, ...)
- ts: 时间戳
- actor: 参与者 (agent/human)
- phase: 阶段
- task_id: 任务 ID
- decision_type: 决策类型
- before → after: 前后状态
- reason: 原因
- links: 链接
