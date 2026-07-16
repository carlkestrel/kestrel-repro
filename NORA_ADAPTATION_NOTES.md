# NORA Adaptation Notes - dl-paper-repro

**Project**: dl-paper-repro plugin automation upgrade  
**NORA Reference**: https://github.com/GRIND-Lab-Core/night_owl_research_agent  
**Date**: 2026-07-16

---

## 1. NORA 核心概念映射

| NORA 概念 | dl-paper-repro 等价物 | 实现状态 |
|-----------|----------------------|----------|
| full-pipeline | `autopilot.py run` + `Controller.run()` | ✅ 已实现 |
| training-check | `Watchdog.check_training_health()` | ✅ 已实现 |
| handoff.json | `StateStore` + `recovery_manager` | ✅ 已实现 |
| memory/MEMORY.md | `EventJournal.events.jsonl` | ✅ 已实现 |
| PreToolUse/PostToolUse | `EventJournal.record_event()` | ✅ 已实现 |
| auto-review-loop | `ReportGenerator.generate_go_pivot_nogo()` | ✅ 已实现 |
| generator-evaluator separation | `Verifier` (独立于 `TaskExecutor`) | ✅ 已实现 |
| evidence discipline | `EvidenceManager` + `artifacts/runs/` | ✅ 已实现 |
| paper-writing pipeline | `ReportGenerator.generate_markdown_report()` | ✅ 已实现 |

## 2. NORA 缺失的概念

NORA 没有 L0-L3 概念，本项目已实现：

- **L0-L3 Loop**: `scripts/l0_l3_loop.py`
  - L0: 静态检查 (smoke_test.py)
  - L1: 真实单 batch (overfit_test.py)
  - L2: 微型过拟合 (mini_loop_test.py)
  - L3: 短评估 (checkpoint_resume_test.py)

## 3. NORA 特有的问题 (已避免)

| NORA 问题 | dl-paper-repro 解决方案 |
|-----------|------------------------|
| 依赖 Markdown 提示词维持状态 | ✅ 使用 SQLite + JSON 持久化 |
| 依赖单次 Cursor 对话 | ✅ 使用 `autopilot.py` 独立运行 |
| output/outputs 路径不一致 | ✅ 统一到 `artifacts/runs/` |
| 简单正则作为安全系统 | ✅ 使用 PolicyEngine + approval_gate |
| 每次会话完整复制输出 | ✅ 使用 checkpoint + WAL DB |
| 发现 GPU 就使用 | ✅ Watchdog 检查温度、显存、占用 |
| AUTO_PROCEED 绕过审批 | ✅ PolicyEngine 强制 gate 检查 |

## 4. 借鉴并重新实现的 NORA 思想

### 4.1 持续执行循环
```python
# NORA: Claude Code 会话持续运行
# dl-paper-repro: autopilot.py 持续运行
while terminal_state_not_reached:
    recover_interrupted_tasks()
    update_ready_tasks()
    task = select_next_ready_task()
    check_policy(task)
    execute(task)
    verify(task)
    persist_state()
    write_evidence()
```

### 4.2 状态持久化
```python
# NORA: handoff.json + memory/MEMORY.md
# dl-paper-repro: StateStore (SQLite WAL)
```

### 4.3 风险分级
```yaml
# NORA: HUMAN_CHECKPOINT, AUTO_PROCEED
# dl-paper-repro: R0-R4 risk levels in automation_policy.yaml
```

### 4.4 证据链
```python
# NORA: claim-to-evidence mapping
# dl-paper-repro: EvidenceManager + verification.json
```

## 5. 未复制的 NORA 功能

以下 NORA 功能未被复制，因为它们与本项目的论文复现目标不直接相关：

- lit-review (文献综述)
- idea-generation (创意生成)
- novelty-check (新颖性检查)
- paper-draft (论文起草)
- paper-covert (论文提交)

这些功能可以通过独立的 skill 添加，但不是当前 MVP 的范围。

## 6. 许可证说明

NORA 使用 MIT 许可证。本项目：

1. 未直接复制 NORA 代码
2. 借鉴了架构思想并重新实现
3. 所有代码使用 MIT/Apache 许可证

---

*Generated: 2026-07-16*
