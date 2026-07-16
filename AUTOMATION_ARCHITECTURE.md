# Automation Architecture - dl-paper-repro

**Project**: dl-paper-repro plugin automation upgrade  
**Date**: 2026-07-16  
**Version**: 1.0.0

---

## 1. 系统架构

### 1.1 组件图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Cursor Agent                                    │
│                     (repro-lead.md / repro-autopilot.md)                    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Autopilot Entry Point                               │
│                        scripts/autopilot.py                                 │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐            │
│  │    run       │   status     │   recover    │    l0l3      │            │
│  └──────────────┴──────────────┴──────────────┴──────────────┘            │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Orchestrator Controller                               │
│                 scripts/orchestrator/controller.py                         │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐            │
│  │  Scheduler   │  Executor    │   Verifier   │  Watchdog   │            │
│  └──────────────┴──────────────┴──────────────┴──────────────┘            │
│  ┌──────────────┬──────────────┬──────────────┐                          │
│  │PolicyEngine  │ApprovalGate │RecoveryMgr   │                          │
│  └──────────────┴──────────────┴──────────────┘                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         State Store (SQLite)                               │
│                 scripts/orchestrator/state_store.py                       │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │ tasks │ approvals │ events │ heartbeats │ metadata              │     │
│  └────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Evidence Layer                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │EvidenceManager  │  │ReportGenerator  │  │ L0L3Loop        │           │
│  │artifacts/runs/  │  │.repro/reports/ │  │ L0→L1→L2→L3    │           │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘           │
└───────────────────────────────────────────────────────────────────────────┘
```

### 1.2 数据流

```
用户命令 → autopilot.py → Controller.run()
                         ↓
              ┌─────────────────────┐
              │   任务调度循环      │
              │ while not terminal:  │
              │   1. recover()     │
              │   2. refresh()     │
              │   3. select_ready()│
              │   4. evaluate()    │
              │   5. launch()      │
              │   6. poll()        │
              │   7. verify()      │
              │   8. persist()    │
              └─────────────────────┘
                         ↓
                   状态持久化 → SQLite
                         ↓
                   证据收集 → artifacts/runs/<run_id>/
```

## 2. 核心组件

### 2.1 Controller (controller.py)

**职责**: 持久化 blocked-or-complete 运行循环

**关键方法**:
- `run()`: 主循环，持续执行直到 terminal state
- `_collect_processes()`: 收集已完成的进程
- `_run_verifications()`: 运行验证
- `_schedule()`: 调度 READY 任务
- `_terminal_result()`: 判断是否达到 terminal state

**状态转换**:
```
PENDING → READY (deps satisfied)
READY → RUNNING (claimed)
RUNNING → VERIFYING (process exit)
VERIFYING → PASS/FAIL (verification)
FAIL → RETRY_WAIT → READY
READY → WAITING_APPROVAL → APPROVED/REJECTED
```

### 2.2 Scheduler (scheduler.py)

**职责**: 任务依赖管理和 READY 任务选择

**关键方法**:
- `detect_cycles()`: 检测循环依赖
- `refresh()`: 更新 PENDING 任务状态
- `select_ready()`: 选择可执行任务
- `deadlock_reason()`: 检测死锁

### 2.3 StateStore (state_store.py)

**职责**: SQLite 持久化状态存储

**表结构**:
- `tasks`: 任务状态
- `approvals`: 审批状态
- `events`: 事件日志
- `heartbeats`: 心跳记录
- `metadata`: 元数据

**特性**:
- WAL 模式
- 事务支持
- Event journal 同步

### 2.4 PolicyEngine (policy_engine.py)

**职责**: 任务执行策略评估

**风险等级**:
- R0: 只读检查 → AUTO_EXECUTE
- R1: 项目内部修改 → AUTO_EXECUTE (with logging)
- R2: 预算内操作 → AUTO_EXECUTE
- R3: 正式训练 → REQUIRE_APPROVAL
- R4: 破坏性操作 → REJECT

### 2.5 Watchdog (watchdog.py)

**职责**: GPU 监控、OOM 检测、训练健康检查

**功能**:
- GPU 利用率/显存/温度监控
- OOM 检测和恢复策略
- 梯度异常检测
- 日志停滞检测
- NaN/Inf 检测

### 2.6 RecoveryManager (recovery.py)

**职责**: 进程崩溃和中断恢复

**功能**:
- 检查点完整性验证
- 孤儿任务恢复
- 指标连续性验证

### 2.7 EvidenceManager (evidence_manager.py)

**职责**: 证据收集和验证

**目录结构**:
```
artifacts/runs/<run_id>/
├── run_manifest.json
├── command.txt
├── config_resolved.yaml
├── environment.json
├── hardware.json
├── stdout.log
├── stderr.log
├── metrics.csv
├── checkpoints/
├── predictions/
├── confmat/
├── figures/
└── verification.json
```

### 2.8 ReportGenerator (report_generator.py)

**职责**: 从证据生成报告

**报告类型**:
- JSON/CSV 摘要报告
- Markdown 人类可读报告
- Go/Pivot/No-Go 判定
- 论文对比报告

## 3. 自动化策略

### 3.1 策略文件 (automation_policy.yaml)

```yaml
mode: safe-auto
run_until: blocked-or-complete

budgets:
  max_gpu_hours: 24
  max_download_gb: 30
  max_task_minutes: 120
  max_retries: 2

hardware:
  max_gpu_temperature_c: 85
  reserve_vram_mb: 1500
  oom_recovery_strategy:
    - gradient_accumulation
    - reduce_batch_size
    - activation_checkpointing
    - amp
    - reduce_workers
```

### 3.2 门控 (Gates)

| Gate | 描述 | 默认行为 |
|------|------|----------|
| read_only | 只读操作 | AUTO_EXECUTE |
| safe | 安全操作 | AUTO_EXECUTE |
| gpu_training | GPU 训练 | REQUIRE_APPROVAL |
| modify_project_files | 修改项目文件 | REQUIRE_APPROVAL |
| destructive | 破坏性操作 | REJECT |

## 4. L0-L3 验证层级

### 4.1 L0: 静态检查

```bash
python scripts/smoke_test.py --primary .
```

**检查内容**:
- import 检查
- 配置解析
- 路径验证
- 依赖检查

### 4.2 L1: 真实单 Batch

```bash
python scripts/overfit_test.py --primary . --steps 50
```

**检查内容**:
- Forward pass
- Backward pass
- Optimizer step
- Eval pass
- Tensor shape/device/dtype

### 4.3 L2: 微型过拟合

```bash
python scripts/mini_loop_test.py --primary . --epochs 3
```

**检查内容**:
- 极小数据集子集
- 固定 seed
- Loss 下降验证
- 过拟合能力确认

### 4.4 L3: 短评估

```bash
python scripts/checkpoint_resume_test.py --primary .
```

**检查内容**:
- Checkpoint 保存
- Checkpoint 恢复
- 评估 pipeline
- 指标生成

## 5. Cursor 命令

### 5.1 /repro-autopilot

```
/repro-autopilot run --project . --until blocked-or-complete
/repro-autopilot status --project .
/repro-autopilot recover --project .
/repro-autopilot l0l3 --project .
/repro-autopilot report --project .
```

### 5.2 /repro-start

```
/repro-start --project . --plan .repro/plan.yaml
```

### 5.3 /repro-doctor

```
/repro-doctor --project . --plan .repro/plan.yaml
```

## 6. 目录结构

```
.repro/
├── startup/
│   ├── startup_state.json
│   └── doctor_report.json
├── execution/
│   ├── state.sqlite3
│   ├── events.jsonl
│   ├── controller.pid
│   ├── controller.heartbeat
│   ├── autopilot.pid
│   ├── autopilot.heartbeat
│   ├── task_graph.yaml
│   ├── execution_state.json
│   ├── checkpoints/
│   ├── logs/
│   └── evidence/
├── reports/
│   ├── summary_report.json
│   ├── summary_report.csv
│   ├── reproduction_report.md
│   └── go_pivot_nogo.json
└── automation_policy.yaml

artifacts/
├── runs/
│   └── <run_id>/
│       ├── run_manifest.json
│       ├── command.txt
│       ├── config_resolved.yaml
│       ├── environment.json
│       ├── hardware.json
│       ├── stdout.log
│       ├── stderr.log
│       ├── metrics.csv
│       ├── checkpoints/
│       ├── predictions/
│       ├── confmat/
│       ├── figures/
│       └── verification.json
└── evidence_index.json
```

## 7. 退出码

| 码 | 含义 | 说明 |
|----|------|------|
| 0 | SUCCESS | COMPLETE, PAUSED, STOPPED |
| 3 | DOCTOR_FAIL | Doctor 检查失败 |
| 4 | NOT_FOUND | 未找到资源 |
| 7 | BLOCKED | 任务阻塞 |
| 8 | WAITING_APPROVAL | 等待审批 |
| 9 | STOPPED | 已停止 |
| 10 | INTERNAL | 内部错误 |

## 8. 安全边界

### 8.1 Safe Auto 边界

**允许的写入路径**:
- `.repro`
- `artifacts`
- `output`
- `reports`
- `logs`

**禁止的写入路径**:
- `src`
- `configs`
- `scripts`
- `README.md`
- `paper`
- `.git`

### 8.2 破坏性操作

以下操作必须审批:
- 删除数据
- 覆盖 checkpoint
- 改变评估协议
- 发布结果
- 访问凭证

---

*Generated: 2026-07-16*
