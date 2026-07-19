# Kestrel-Repro R3R Handoff Packet

**目标接手者**: 新 Cursor 会话 / 新 Lead Agent
**原始会话**: current (Cursor IDE chat)
**交接日期**: 2026-07-19
**项目**: kestrel-repro R3-Refactor 推进

---

## 0. 强制首读清单（在新 Cursor 对话第一秒就要读）

```
1. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/.r3r-state/PROJECT_CHARTER.md
2. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/.r3r-state/ORCHESTRATION_STATE.json
3. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/.r3r-state/TASK_LEDGER.md
4. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/.r3r-state/FILE_OWNERSHIP.json
5. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/.r3r-state/USER_DECISIONS.md
6. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/refactor_state.json   ← 项目自带顶级真相源
7. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/README.md
8. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/AUTOMATION_ARCHITECTURE.md
9. /home/carlkestrel/.cursor/plugins/local/kestrel-repro/ci_reports/R3_FULL_JUNIT.xml
```

---

## 1. 当前状态（45 秒摘要）

**kestrel-repro 已是一个工业化 Cursor Plugin**（不是零碎项目）。R3-Refactor 是当前阶段。

| 指标 | 值 | 来源 |
|---|---|---|
| Phase | R3-CONTINUATION | refactor_state.json |
| Tests | 258 collected / 237 pass / 21 fail | refactor_state.json |
| 最新 commit | 632277d (Ruff lint cleanup) | git log |
| R3-0 (state consolidation) | ✅ COMPLETE | refactor_state.json |
| R3-1 (controller integration) | ⚠️ PARTIAL | refactor_state.json |
| R3-2 (approval gate) | ⚠️ PARTIAL | refactor_state.json |
| R3-3 (signal handling) | ✅ COMPLETE | refactor_state.json |
| R3-4 (process exit codes) | ✅ COMPLETE | refactor_state.json |
| R3-5 (recovery) | ⏳ open | refactor_state.json |
| R3-6 (GPU lock) | ⏳ planned | refactor_state.json |
| R3-7 (shell safety) | ⏳ planned | refactor_state.json |
| R3-CHAOS-1 | ⏳ legacy schema | refactor_state.json |

**目标**: 修复 21 个 test failure，按 wave 推进。

---

## 2. 模式与边界

### 2.1 多 Agent 协作模式
- **模式**: `worktree_fallback`（单 Lead agent 串行推进）
- **理由**: Cursor Agent 的 MCP 工具层**没有 spawn_subagent**（已实测确认）
- **决策**: USER_DECISIONS.md D-2026-07-19-004

### 2.2 Subagent 怎么用
- Lead agent 不能直接 spawn Subagent
- **用户在 Cursor UI 手动开 Background Subagent**
- Subagent 写完后报告回贴给 Lead
- Lead agent 不重复 Subagent 已做的工作
- 详见 FILE_OWNERSHIP.json §"handoff_protocol"

### 2.3 Lead agent 不能写
- `.execution/state.sqlite3`（StateStore 独占）
- `artifacts/runs/<run_id>/checkpoints/**`（EvidenceManager 独占）
- `.git/**`（git 专属）

### 2.4 安全边界（来自 AUTOMATION_ARCHITECTURE.md §8.1）
**Safe Auto 允许写入**：
- `.r3r-state/`（本目录，状态文件）
- `.repro/`
- `artifacts/`
- `output/`
- `reports/`

**Safe Auto 禁止写入**：
- `src/`, `configs/`, `scripts/`
- `README.md`, `paper/`
- `.git/`

⚠️ **异常豁免**：本项目的 R3 阶段需要改 `scripts/orchestrator/`（修 bug），所以**临时豁免** scripts/ 的写入限制 — 但**只能写 `scripts/orchestrator/*.py`，不能写 `scripts/other/*.py`**。详见 USER_DECISIONS.md D-2026-07-19-005。

---

## 3. 立即要做（W0 完成 → W1 启动）

### 3.1 W0 验证清单
- [ ] 读 PROJECT_CHARTER.md（5 分钟）
- [ ] 读 refactor_state.json（2 分钟）
- [ ] 跑 `cd /home/carlkestrel/.cursor/plugins/local/kestrel-repro && pytest tests/ -q --no-header` 验证 baseline（2 分钟）
- [ ] 输出 baseline 报告到 ORCHESTRATION_STATE.json 的 current 字段

### 3.2 W1 启动前的准备
- [ ] 读 `scripts/orchestrator/controller.py`（当前主循环）
- [ ] 读 `scripts/orchestrator/scheduler.py`
- [ ] 读 `scripts/orchestrator/approval_gate.py`
- [ ] 读 `tests/test_orchestrator.py::test_1` 至 `test_7`（找失败原因）

### 3.3 W1 第一刀（建议）
1. **W1-1**: Scheduler ↔ Executor 接线
   - 文件: `scripts/orchestrator/controller.py` + `scheduler.py`
   - 失败测试: `test_orchestrator.py::test_1-3, test_4`
   - 风险: 中 — 改状态机关键路径
   - 修完后跑 `pytest tests/test_orchestrator.py -q` 验证

---

## 4. 给新 Lead agent 的关键提醒

### 4.1 不要重新发明主稿
- v1.0 / v1.2 主稿**已废弃**（基于假设写，不基于真实基线）
- 看 PROJECT_CHARTER.md §2 反映的真实状态
- 决策日志 D-2026-07-19-006 解释为啥废弃

### 4.2 不要重新建工作目录
- 状态文件**已经迁到** `kestrel-repro/.r3r-state/`
- **不要再**写入 `~/.cursor/agent-projects/kestrel-r3r/`（那个路径是历史错误）

### 4.3 不要尝试 single-Lead 全自动 push
- Lead agent 可以 commit 到本地分支
- Lead agent **不要自动 push 到远程**
- push 操作需要用户审批（USER_DECISIONS.md 签字）

### 4.4 报告频率
- 每个 wave 完成后输出 `STATUS_REPORT.md`（含：完成 / 失败 / 测试增量）
- 每个 D-number 决策前输出 `DECISION_PROPOSAL.md`（含：决策点 / 选项 / 推荐）
- 阻塞时输出 `BLOCKER_REPORT.md`（含：阻塞 / 已尝试 / 需要什么）

### 4.5 Cursor Project Context 配置建议
如果要把这 6 个状态文件自动注入新对话：
- Cursor Settings → Project → "Project Context" 或 "Always include these files"
- 加这 6 个文件：
  - `.r3r-state/PROJECT_CHARTER.md`
  - `.r3r-state/ORCHESTRATION_STATE.json`
  - `.r3r-state/TASK_LEDGER.md`
  - `.r3r-state/FILE_OWNERSHIP.json`
  - `.r3r-state/USER_DECISIONS.md`
  - `.r3r-state/HANDOFF.md`（本文件）

---

## 5. 退出标准

Lead agent 完成 R3-Refactor 的标准：
- ✅ `pytest tests/ -q` 退出码 = 0
- ✅ `refactor_state.json` 的 remaining_r3_open 为空数组
- ✅ 用户在 USER_DECISIONS.md D-End 签字
- ✅ 所有 R3 范围内的改动已 commit + push（用户审批）
- ✅ R3 evidence artifacts 在 `ci_reports/` 落地

---

## 6. 紧急 fallback

如果 Lead agent 卡死 / 用户长时间未审批 / 异常：

1. 立刻停止任何修改
2. 看 ORCHESTRATION_STATE.json 的 `current_phase` 和 `next_action`
3. 在 USER_DECISIONS.md 新增一条 BLOCKER_REPORT 记录
4. 等用户回来处理

不要继续单方面推进。

