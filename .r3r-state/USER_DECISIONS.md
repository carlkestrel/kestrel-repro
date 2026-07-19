# Kestrel-Repro R3R 用户决策日志

**项目**: kestrel-repro R3-Refactor 推进
**会话发起**: 2026-07-12（Cursor chat 历史）
**当前会话**: 2026-07-19（路径修正 + 状态文件重写）

---

## 决策格式

每个决策含 5 段：
- **ID**: D-YYYY-MM-DD-NNN
- **Question**: 问题陈述
- **Options**: 候选选项
- **Decision**: 用户选定
- **Rationale**: 选定理由
- **Impact**: 影响

---

## D-2026-07-19-001 — 主稿 v1.0 创建

**Question**: 是否要为 R3R 多 Subagent 协作创建一份主稿？

**Options**:
- A. 创建
- B. 不创建，直接在每条 Subagent prompt 写指令

**Decision**: A（创建）

**Rationale**: 多 Subagent 协作需要统一术语、阶段定义、退出条件。

**Impact**: 主稿放在本地 working memory（未持久化）。

---

## D-2026-07-19-002 — 主稿升 v1.2

**Question**: 是否要把主稿修订成更可操作的版本？

**Options**:
- A. 升 v1.2（含 18 节、可执行结构）
- B. 保持 v1.0

**Decision**: A

**Rationale**: v1.2 增加了 18 节（v1.0 是 12 节），覆盖 self-check、escalation、recovery。

**Impact**: 主稿从 380 行扩到 568 行。

---

## D-2026-07-19-003 — worktree_fallback 模式选定

**Question**: 如何应对单 Cursor Agent 没法管理多 Subagent 的现状？

**Options**:
- A. dynamic_tranche_partitioning（多 Lead）
- B. worktree_fallback（单 Lead + 多 worktree）
- C. worktree_only（仅本地分支隔离）
- D. escalate_to_user（升级到用户）

**Decision**: B（worktree_fallback）

**Rationale**:
- 当前 Cursor session 没有 Subagent 工具
- 单 Lead 串行最稳，但需要并行试验时用 worktree

**Impact**: Lead agent 是单一 writer，worktree 是隔离试验区。

---

## D-2026-07-19-004 — Subagent 不可用诊断

**Question**: 用户问"Subagent 功能为什么不可用"。

**Tools layer verified**:
- `cursor-app-control`：控制 Cursor 自身（✓ 有）
- `cursor-ide-browser`：浏览器自动化（✓ 有）
- `spawn_subagent` / `parallel_agent`（❌ 没有）

**Decision**: 这是 Cursor Agent MCP 工具层的固有限制，不是订阅问题。

**Impact**:
- 工作模式强约束为 worktree_fallback
- Subagent 必须通过用户在 Cursor UI 手动开
- Subagent 报告通过用户回贴给 Lead

---

## D-2026-07-19-005 — 状态文件重定位到 kestrel-repro/.r3r-state/

**Question**: 之前 6 个状态文件写在 `~/.cursor/agent-projects/kestrel-r3r/`，但 kestrel-repro 真实代码仓库在 `~/.cursor/plugins/local/kestrel-repro/`。两路径不重合，导致：
- Subagent 看不到状态文件
- 状态文件不进 git
- Cursor Project Context 默认不挂载

**Options**:
- A. 状态文件迁移到 `kestrel-repro/.r3r-state/` 并 commit 进 git（✓ 选定）
- B. 状态文件迁移到 `kestrel-repro/.agent-context/` 进 .gitignore
- C. 状态文件留在 `~/.cursor/agent-projects/` + Cursor Project Context 挂载
- D. 重组计划，先读真实基线再决定 R3R 下一阶段

**Decision**: A

**Rationale**:
- 进 git 让 Subagent 在任何 commit checkout 都能看到
- 放进 `.r3r-state/` 隐藏目录不污染 kestrel-repro 主结构
- 配合 .gitignore 备份（可以选）

**Impact**:
- 状态文件现在在 kestrel-repro git 历史里
- Subagent 接 kestrel-repro 时自然看到状态文件
- v1.2 主稿作废（D-2026-07-19-006）

---

## D-2026-07-19-006 — v1.2 主稿作废、重写基于真实基线

**Question**: v1.2 主稿写完后，用户指出"改 kestrel-repro 项目的路径根本不会对齐粒度"。这暴露了什么？

**Diagnosis**:
- 主稿 v1.2 是**基于假设**写的（568 行，主稿作者从未读过 kestrel-repro 真实代码）
- 真实情况：kestrel-repro 已工业化完整，是 Cursor Plugin（9 agents + 4 skills + 11 commands + 6 gates + 持久化 Orchestrator）
- 真实 R3 阶段：R3-1/2 partial、R3-5/6/7 open、21 个 test fail
- 主稿设想的 wave 切分（Wave 0 只读审计 + Wave 1 修复）和实际工作（修 21 个 fail）不匹配

**Options**:
- A. 主稿废弃，重写基于真实基线
- B. 主稿局部修订
- C. 主稿保留作为理论参考

**Decision**: A

**Rationale**:
- 实事求是比协调性重要
- Lead agent 必须是 real-grounded（基于真实文件）
- 不基于真实基线的主稿会把 Subagent 引到错误方向

**Impact**:
- PROJECT_CHARTER.md §2 完全重写，反映 refactor_state.json 真实基线
- ORCHESTRATION_STATE.json 重写 wave plan，按 R3-1/2/3/5/6/7 + R3-CHAOS-1 真实推进顺序排
- TASK_LEDGER.md 重写 backlog
- v1.2 主稿（已不存在于 git）作废

---

## D-2026-07-19-007 — 临时豁免 scripts/ 写入限制

**Question**: AUTOMATION_ARCHITECTURE.md §8.1 禁止 Safe Auto 写入 scripts/，但 R3 修复必须改 `scripts/orchestrator/*.py`。怎么办？

**Options**:
- A. 永久豁免 scripts/orchestrator/
- B. 临时豁免 scripts/orchestrator/（仅 R3 阶段），其他 scripts/ 仍禁写
- C. 全部豁免，改用 PR 审批流程

**Decision**: B

**Rationale**:
- AUTOMATION_ARCHITECTURE.md 的禁写是**默认安全策略**，不是绝对禁止
- R3 修复是**必要的**对 orchestrator 的改动
- 但要把豁范围限制到 `scripts/orchestrator/`，不动其他

**Impact**:
- `scripts/orchestrator/*.py` 在 R3 阶段可写
- Lead agent 写完一个 wave 后必须跑 `pytest tests/test_orchestrator.py -q` 验证
- 任何破坏 R3-0 测试的行为必须回滚

---

## 待决策（pending）

### P-2026-07-19-A: W1 第一刀是 W1-1 还是 W1-4？
- **W1-1**: Scheduler ↔ Executor 接线（高价值、中风险、修 4 tests）
- **W1-4**: Verifier 触发（低价值、低风险、修 3 tests）

**Recommend**: W1-1 先。理由：先打通"任务能跑"主路径，Verifier 是后置检查。

需要您确认。

### P-2026-07-19-B: 是否要进 R3-6 / R3-7 新功能？
- 当前 backlog 含 W4-1 GPU lock + W5-1 shell safety
- 这些是**新功能**，不是 bug fix

**Recommend**:
- 先把 R3-1/2/3/5 + R3-CHAOS-1 收尾（wave 1-2-3）
- 然后专门评估 R3-6/7 是否进 R3 final 或者推迟到 R4

需要您确认。

---

## Sign-off（用户决定何时结束推进）

**Lead agent 退出标准**:
- [ ] 21 个 test failure 全修（pytest 退出码 0）
- [ ] refactor_state.json 的 remaining_r3_open 为空
- [ ] 用户在本文签字
- [ ] git push 用户审批
- [ ] R3 evidence artifacts 落地

**当前签字状态**: ⏳ 未到达退出标准

