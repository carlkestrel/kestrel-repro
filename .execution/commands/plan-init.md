---name: plan-initdescription: Convert plan to task graph with dependencies and acceptance criteria---
# /plan-init — Plan 转换为任务图

## Purpose

将现有 `.cursor/plans/<plan>.md` 转换为受控执行所需的所有初始化文件：

- `plan_snapshot.md` — 不可变逻辑快照
- `task_graph.yaml` — 原子任务图（含依赖、验收、风险、恢复）
- `execution_state.json` — 当前执行状态
- `task_journal.jsonl` — 任务日志
- `requirement_traceability.csv` — 需求追踪

## 输入

- `PLAN_PATH` 环境变量或参数（默认 `.cursor/plans/dl-paper-repro_nora_enhancement_0709b676.plan.md`）

## 步骤

1. 计算 Plan SHA256 哈希并校验
2. 复制 Plan 为只读快照
3. 提取所有显式和隐式需求（按 Phase + Sub-section）
4. 为每个 Phase 子节生成 1-3 个原子任务
5. 写入全部初始化文件
6. **不执行任何任务**

## 输出文件

| 文件 | 用途 |
|---|---|
| `.execution/plan_snapshot.md` | Plan 只读快照 |
| `.execution/task_graph.yaml` | 任务图 |
| `.execution/execution_state.json` | 当前状态 |
| `.execution/task_journal.jsonl` | 任务执行日志 |
| `.execution/requirement_traceability.csv` | 需求→任务追踪 |
| `.execution/PLAN_HASH` | 哈希值 |

## 验收

- 6 个文件全部生成
- Plan 哈希匹配
- 任务图覆盖 Plan 所有 Phase 子节
- 需求 CSV 每行 requirement_id 唯一

## 不允许

- 执行任何任务
- 修改 Plan 内容
- 删除 Plan 已有数据