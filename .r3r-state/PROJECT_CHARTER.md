# Kestrel-Repro R3R 项目章程

**项目**: kestrel-repro 插件的 R3-Refactor 推进
**版本**: v1.0 (2026-07-19)
**上游**: kestrel-repro Cursor Plugin
**核心仓库**: /home/carlkestrel/.cursor/plugins/local/kestrel-repro
**远程**: gh:carlkestrel/kestrel-repro
**最新 commit**: 632277d (chore: fix Ruff lint errors)
**Python**: 3.13.13
**venv**: /tmp/kestrel_r1_workspace/kestrel_r1_venv

## 1. 项目本质

**kestrel-repro 不是一个零碎组件**——它是一个已经工业化完成的 Cursor Plugin：

- 9 个 agents（repro-lead, data-metric-auditor, runtime-optimizer, evidence-verifier, repo-scout, hardware-fit-auditor 等）
- 4 个 skills（paper-reproduction, deep-learning-runtime, point-cloud-reproduction, repository-selection）
- 11 个 Cursor command（`/repro-init`, `/repro-audit`, `/repro-launch` 等）
- 6 门 gate（paper audit → preflight → short loop → parity → full training → evidence）
- 持久化组件：`scripts/orchestrator/` (Controller / Scheduler / StateStore / PolicyEngine / Watchdog / RecoveryManager / EvidenceManager / ReportGenerator)

**R3-Refactor 是当前阶段**：把 state / approval / orchestration 整合到 Controller，去掉 R2 引入的隔离中间层。

## 2. 真实基线（来自 refactor_state.json + commits）

### 2.1 已完成
- **R2 (orchestrator integration)**: ✅ 完成
- **R3-0 (state consolidation)**: ✅ 完成 (17/17 acceptance tests)
- **R3-3 (signal handling)**: ✅ 完成 — stop_hook thread-safe
- **R3-4 (process manager exit codes)**: ✅ 完成 — explain_exit_code() added
- **R3-Ruff Python 3.10 compat**: ✅ 完成 (commit a92117f)
- **R3-2 (canonical PlanSchema → Controller)**: ✅ 完成 (commit 45363a0)
- **R3-4 to R3-8 (P0-5/P0-6 fixes, metrics_recompute, repro-start, isolation tests)**: ✅ 完成 (commit 212bd60)
- **R3-Ruff evidence artifacts**: ✅ 完成 (commit 249f2e6)
- **Ruff lint cleanup**: ✅ 完成 (commit 632277d)

### 2.2 进行中（PARTIAL）
- **R3-1 (controller integration)**: ⚠️ PARTIAL — state adapters added; executor/scheduler wiring still pending
- **R3-2 (approval gate)**: ⚠️ PARTIAL — canonical APPROVED/REJECTED/WAIVED states integrated; controller wiring pending

### 2.3 未做
- **R3-5 (recovery)**: ⏳ open items R3-5-001, R3-5-002
- **R3-6 (GPU resource lock)**: ⏳ planned
- **R3-7 (shell command safety boundary)**: ⏳ planned + R3-7-001 fail
- **R3-CHAOS-1 (chaos test schema migration)**: ⏳ tests use legacy status column

### 2.4 测试全景
```
collected: 258
passed:    237 (91.9%)
failed:    21  (8.1%)

per-file:
  test_r3_0_acceptance.py        17/17 ✅
  test_r2_acceptance.py          31/31 ✅
  test_r1_acceptance.py          12/12 ✅
  test_startup.py                53/53 ✅
  test_ostar.py                  35/35 ✅
  test_stabilization.py          12/12 ✅
  test_other_suites              52/52 ✅
  test_chaos.py                  21/28 ❌ 7 fail
  test_orchestrator.py            4/18 ❌ 14 fail  ← 重点

junit_xml: ci_reports/R3_FULL_JUNIT.xml
```

### 2.5 失败原因
**R3-1**：
- R3-1-006: Scheduler 不让任务进入 RUNNING
- R3-1-007: claim_task 加了但任务不进 RUNNING

**R3-2**：
- R3-2-002: ApprovalGate 没从 controller 创建 approval
- R3-2-003: PolicyEngine 没从 policy file 重载

**R3-3**：
- R3-3-001: Verifier 没在任务完成时触发
- R3-3-002: PAUSED state 没被 controller loop honored

**R3-5**：
- R3-5-001: Recovery 没从 journal 恢复 RUNNING
- R3-5-002: Final acceptance 没在 mandatory task 跑

**R3-7**：
- R3-7-001: Daemon lifecycle 没干净停止 orphan workers

**R3-CHAOS-1**：
- 用 legacy status column 或 PASS/FAIL 值，应改 canonical schema

## 3. 战略目标（R3 后续阶段）

不是从零写 plugin，是**修复 21 个 test failure**。按 refactor_state.json 的 next_steps 排序：

1. **R3-1 收尾**：scheduler ↔ executor 接线 — 让 ready tasks 被 claim
2. **R3-2 收尾**：ApprovalGate 接线 + PolicyEngine reload
3. **R3-3 收尾**：Verifier 触发 + PAUSED state
4. **R3-5 收尾**：Recovery 从 journal 恢复 RUNNING
5. **R3-CHAOS-1**：chaos tests 改 canonical schema
6. **R3-6 (新)**：GPU resource lock 实现
7. **R3-7 (新)**：Shell command safety boundary

## 4. 多 agent 协作模式

### 4.1 当前 agent 工具层的能力（实测）
- ✅ Read / Edit / Write / Grep / Glob
- ✅ Shell (run python pytest, run scripts, git)
- ❌ **没有 spawn_subagent 工具**（MCP 层验证）
- ❌ **没有 parallel_agent 工具**
- ✅ Cursor UI 端可手动开 Background Subagent

### 4.2 选定的协作模式 = **worktree_fallback**
（理由见 USER_DECISIONS.md D-2026-07-19-004）

worktree_fallback 含义：
- 单一 Lead agent 在主 git worktree 串行推进
- 需要并行试验时，用 `git worktree add` 起多个隔离 worktree
- 每个 worktree 是单向 branch，不互相同步（避免 merge 冲突）
- Lead 自己在 worktree 之间搬运 patch

### 4.3 不选 dynamic_tranche_partitioning 的原因
- 当前 Cursor MCP 层没有任务分配协议
- Subagent 的边界由 Cursor UI 决定，不是 agent 决定

### 4.4 用户的角色
- Subagent 写完后**用户把报告回贴 Lead**
- Lead 的 git 推送需要用户审批
- 主架构决策由用户决议（看 USER_DECISIONS.md）

## 5. 退出条件

| 退出条件 | 标准 |
|---|---|
| 测试通过 | `pytest tests/ -q` 退出 0 |
| Gate 验证 | `python reproctl.py status` 显示所有 gate PASS |
| R3 全部完成 | refactor_phase = "R3-complete" 或更新阶段标记 |
| 用户审批 push | 用户在 USER_DECISIONS.md 签字 |
| 证据链完整 | `artifacts/runs/<run_id>/verification.json` 全部 ON_DISK |

