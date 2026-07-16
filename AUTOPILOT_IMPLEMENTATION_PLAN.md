# Autopilot Implementation Plan - NORA Integration

**Project**: dl-paper-repro plugin automation upgrade  
**Date**: 2026-07-16  
**Status**: In Progress

---

## 1. 现有模块复用分析

### 1.1 已有且可复用

| 模块 | 路径 | 状态 | 说明 |
|------|------|------|------|
| Controller | `scripts/orchestrator/controller.py` | ✅ 完善 | 已有持久化 blocked-or-complete 运行循环 |
| Scheduler | `scripts/orchestrator/scheduler.py` | ✅ 完善 | 依赖 DAG + READY 任务选择 |
| StateStore | `scripts/orchestrator/state_store.py` | ✅ 完善 | SQLite WAL + event journal |
| PolicyEngine | `scripts/orchestrator/policy_engine.py` | ✅ 完善 | safe-auto 边界 + 审批策略 |
| TaskExecutor | `scripts/orchestrator/task_executor.py` | ✅ 完善 | subprocess 启动 + 日志 |
| Verifier | `scripts/orchestrator/verifier.py` | ✅ 完善 | acceptance_tests 执行 |
| Watchdog | `scripts/orchestrator/watchdog.py` | ✅ 基础 | 心跳 + 超时检测 |
| RecoveryManager | `scripts/orchestrator/recovery.py` | ✅ 基础 | RUNNING 孤儿恢复 |
| ApprovalGate | `scripts/orchestrator/approval_gate.py` | ✅ 存在 | 待检查 |
| ProcessManager | `scripts/orchestrator/process_manager.py` | ✅ 存在 | 进程管理 |
| EventJournal | `scripts/orchestrator/event_journal.py` | ✅ 存在 | JSONL 事件日志 |
| Backup | `scripts/orchestrator/backup.py` | ✅ 存在 | 项目快照 |
| Migrate | `scripts/orchestrator/migrate.py` | ✅ 存在 | schema 迁移 |
| Doctor | `scripts/startup/doctor.py` | ✅ 完善 | 硬件/环境预检 |
| StateMachine | `scripts/startup/state_machine.py` | ✅ 存在 | BOOTSTRAP→EXECUTE_NEXT |
| ReproAgent | `agents/repro-lead.md` | ✅ 完善 | 论文复现流程 |
| Tests | `tests/` | ✅ 14+ 测试文件 | orchestrator, state_machine, chaos |

### 1.2 缺失/需增强

| 模块 | 优先级 | 说明 |
|------|--------|------|
| **Autopilot 统一入口** | P0 | `/repro-autopilot` 命令，替代分散的命令 |
| **Continuous Run** | P0 | `--until blocked-or-complete` 持续循环 |
| **Takeover 命令** | P0 | 识别已有项目并生成任务图 |
| **Watchdog 增强** | P1 | GPU 监控、OOM 检测、梯度异常 |
| **Evidence Manager** | P1 | 统一 artifact 根目录 |
| **训练恢复增强** | P1 | checkpoint 完整性验证、指标连续性 |
| **Report Generator** | P2 | 从验证证据生成报告 |
| **L0-L3 自动执行** | P2 | 集成到编排器 |

### 1.3 NORA 功能映射

| NORA 概念 | 现有等价物 | 差距 |
|-----------|-----------|------|
| full-pipeline | Controller.run() | 需增加 autopilot 子命令 |
| training-check | Watchdog + training_monitor.py | 需集成到编排器 |
| handoff.json | state.db recovery | 已有部分，需完善 |
| memory/MEMORY.md | event_log.jsonl | 需结构化摘要 |
| PreToolUse/PostToolUse | EventJournal | 已有事件记录 |
| auto-review-loop | Reviewer agent | 需集成 |
| evidence discipline | 分散在 artifacts/ | 需统一规范 |
| paper-writing pipeline | scripts/reproctl.py report | 需增强 |

---

## 2. 最小改动实施顺序

### 批次 1: Autopilot 统一入口 (P0)
- 创建 `scripts/autopilot.py` - 统一命令入口
- 集成 `reproctl orchestrator run` 到 autopilot
- 添加 `--until blocked-or-complete` 选项

### 批次 2: Takeover 命令 (P0)
- 创建 `scripts/takeover.py` - 项目识别和接管
- 自动检测已有项目类型
- 生成初始任务图

### 批次 3: 状态增强 (P1)
- 增强 Watchdog GPU 监控
- 增强 RecoveryManager checkpoint 验证
- 添加 OOM 自动恢复策略

### 批次 4: Evidence 统一 (P1)
- 创建 `artifacts/` 规范目录结构
- 更新 Verifier 生成 evidence paths
- 添加 evidence 验证规则

### 批次 5: 文档更新 (P2)
- 更新 HTML 手册添加 autopilot 章节
- 添加中文文档

### 批次 6: 自检和测试 (P2)
- 运行现有测试套件
- 添加 autopilot 特定测试
- 添加 L0-L3 集成测试

---

## 3. 风险和回滚点

### 3.1 主要风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 破坏现有 orchestrator | 中 | 高 | 不修改 controller.py 核心逻辑 |
| 状态不一致 | 低 | 高 | SQLite WAL + 事务 |
| 进程孤儿 | 低 | 中 | Watchdog + RecoveryManager |
| 路径冲突 | 低 | 中 | artifacts/ 规范 + 迁移适配 |

### 3.2 回滚点

- 每次批次修改前备份相关文件
- 使用 git 分支进行实验
- 每个批次后运行 `reproctl orchestrator status`

---

## 4. 验收条件

1. `python scripts/autopilot.py run --project . --until blocked-or-complete` 可持续运行
2. 中断后 `python scripts/autopilot.py recover` 可恢复
3. 状态通过 `python scripts/autopilot.py status` 可查看
4. 现有 `reproctl orchestrator` 命令保持兼容
5. L0-L3 测试可通过 autopilot 自动执行

---

## 5. 文件变更清单

### 新增文件
- `scripts/autopilot.py` - Autopilot 统一入口
- `scripts/takeover.py` - 项目接管
- `automation_policy.yaml` - 自动化策略模板

### 修改文件
- `commands/reproctl.py` - 添加 autopilite 子命令（如果需要）
- `scripts/orchestrator/watchdog.py` - 增强 GPU 监控
- `scripts/orchestrator/recovery.py` - 增强 checkpoint 验证
- `docs/html/` - 更新文档

### 测试文件
- `tests/test_autopilot.py` - Autopilot 测试
- `tests/test_takeover.py` - Takeover 测试
