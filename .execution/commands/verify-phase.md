---name: verify-phasedescription: Verify completion of current phase---
# /verify-phase — 验收当前阶段

## Purpose

对当前 Phase 进行阶段级自检，确认所有 mandatory 任务 PASS，无 PARTIAL/FAIL/BLOCKED 残留。

## 步骤

1. 读取 `execution_state.json` 获取 `current_phase`
2. 读取 `task_graph.yaml` 中所有属于该 Phase 的任务
3. 逐个检查状态：
   - mandatory 任务必须 PASS
   - 可选任务可 SKIPPED 或 PASS
4. 检查 `task_reports/` 中每个任务报告存在
5. 检查 `evidence/` 中每个任务的 evidence 存在
6. 输出阶段验收报告到 `.execution/checkpoints/verify_phase_<phase_id>_<timestamp>.md`

## 检查项

| 项 | 强制 | 检查方式 |
|---|---|---|
| 所有 mandatory 任务 PASS | 是 | task_graph.yaml status |
| 无 PARTIAL 残留 | 是 | task_graph.yaml |
| 无 FAIL 残留 | 是 | task_graph.yaml |
| BLOCKED 有 failure_report | 是 | failures/ 目录 |
| 任务报告存在 | 是 | task_reports/ 目录 |
| 证据存在 | 是 | evidence/ 目录 |
| 无 stub/TODO/硬编码 | 是 | grep 关键字符串 |
| 未引入计划外文件 | 是 | diff 当前文件 vs 阶段开始时 |

## 输出

- `.execution/checkpoints/verify_phase_<phase_id>_<timestamp>.md`
- 更新 `execution_state.json.current_phase` → 下一 phase（如通过）

## 不允许

- 跳过 mandatory 任务检查
- 把 PARTIAL 算作 PASS
- 在 BLOCKED 状态下切换 phase