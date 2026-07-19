# Kestrel-Repro R3R Task Ledger

**最后更新**: 2026-07-19
**当前阶段**: R3-CONTINUATION（修复 21 个 test failure）
**模式**: worktree_fallback（单 Lead agent 串行推进）

---

## Active Tasks（进行中）

### W0-2 — 状态文件重定位
- **状态**: IN_PROGRESS
- **内容**: 把 6 个状态文件从 `~/.cursor/agent-projects/kestrel-r3r/` 迁到 `kestrel-repro/.r3r-state/`
- **决策**: D-2026-07-19-005
- **退出条件**: 6 个文件全部 commit 进 kestrel-repro git
- **阻塞**: 无

### W0-3 — 重写状态文件
- **状态**: IN_PROGRESS
- **内容**: 抛弃 v1.2 主稿（基于假设），改写基于真实基线的状态文件
- **决策**: D-2026-07-19-006
- **退出条件**: PROJECT_CHARTER.md + ORCHESTRATION_STATE.json 反映 R3-1/2/3 进行中、R3-5/6/7 未做、21 fail 真实基线
- **阻塞**: 无

---

## Backlog（按 wave 排序）

### Wave 1 — R3-1 / R3-2 / R3-3 收尾
- [ ] W1-1 Scheduler ↔ Executor 接线（修 R3-1-006, R3-1-007）— `test_orchestrator.py::test_1-3, test_4`
- [ ] W1-2 ApprovalGate 接线（修 R3-2-002）— `test_orchestrator.py::test_5-7`
- [ ] W1-3 PolicyEngine hot-reload（修 R3-2-003）— `test_orchestrator.py::test_15`
- [ ] W1-4 Verifier 触发（修 R3-3-001）— `test_orchestrator.py::test_8-10`
- [ ] W1-5 PAUSED state honored（修 R3-3-002）— `test_orchestrator.py::test_13`

**预期**: test_orchestrator.py 14 fail → 5-7 fail

### Wave 2 — R3-5 / R3-CHAOS-1
- [ ] W2-1 Recovery 从 journal 恢复 RUNNING（修 R3-5-001）— `test_orchestrator.py::test_9`
- [ ] W2-2 Final acceptance mandatory check（修 R3-5-002）— `test_orchestrator.py::test_14`
- [ ] W2-3 Chaos tests 改 canonical schema（修 R3-CHAOS-1）— `test_chaos.py::*`

**预期**: test_chaos.py 7 fail → 0-2 fail，test_orchestrator.py 5-7 fail → 3-4 fail

### Wave 3 — R3-7 daemon
- [ ] W3-1 Daemon lifecycle 干净停止 orphan workers（修 R3-7-001）— `test_orchestrator.py::test_18`

**预期**: test_orchestrator.py 3-4 fail → 2-3 fail

### Wave 4 — R3-6 GPU resource lock
- [ ] W4-1 GPU resource lock 实现（新增）

### Wave 5 — R3-7 safety boundary
- [ ] W5-1 Shell command safety boundary
- **审批**: 安全敏感，需用户审批

---

## Done（完成）

### D-001 通过 D-005（v1.0 → v1.2 主稿，已废弃）
- D-001: 主稿 v1.0 创建
- D-002: 主稿 v1.2 创建
- D-003: worktree_fallback 模式选定
- D-004: Subagent 不可用诊断
- D-005: 状态文件重定位到 kestrel-repro/.r3r-state/

---

## Test Progress

| 时间 | collected | passed | failed | exit_code | source |
|---|---|---|---|---|---|
| 2026-07-19 baseline | 258 | 237 | 21 | 1 | refactor_state.json |
| 2026-07-19+1（待跑） | ? | ? | ? | ? | pytest tests/ -q 输出 |

**Exit criterion**: `pytest tests/ -q` 退出码 = 0，所有 21 个 fail 修复或合理文档化。

