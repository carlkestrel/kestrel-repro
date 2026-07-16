---name: execute-nextdescription: Execute next READY task from task_graph.yaml---
# /execute-next — 执行下一个 READY 任务

## Purpose

从 `task_graph.yaml` 中读取状态为 READY 的下一个任务，执行 PRECHECK→EXECUTE→LOCAL TEST→EVIDENCE→VERIFY→CHECKPOINT→UPDATE STATE 循环。

## 步骤

1. 读取 `execution_state.json`，确认 WIP 限制（最多 1 个写任务）
2. 扫描 `task_graph.yaml`，找 PENDING 中所有依赖都 PASS 的第一个任务
3. 标记该任务为 RUNNING，写入 `task_journal.jsonl`
4. 执行 PRECHECK：依赖 PASS / 输入存在 / 硬件检查
5. 执行 EXECUTE：最小修改范围
6. LOCAL TEST：直接相关测试
7. EVIDENCE：保存日志/配置/diff 到 `.execution/evidence/<task_id>_<description>.{json,md,log}`
8. VERIFY：逐条执行 acceptance_tests，输出 PASS/PARTIAL/FAIL/BLOCKED
9. CHECKPOINT：保存到 `.execution/checkpoints/<task_id>.json`
10. UPDATE STATE：更新 task_graph + execution_state + requirement_traceability
11. 写任务报告到 `.execution/task_reports/<task_id>.md`

## 输入

- 无（自动选择下一个 READY）

## 输出

- `.execution/task_reports/<task_id>.md` — 任务报告
- `.execution/evidence/<task_id>_*` — 证据
- `.execution/execution_state.json` — 状态更新

## WIP 限制

- 同时只允许 1 个写任务 RUNNING
- 失败 2 次后标 BLOCKED
- 超时 = timeout_minutes × 60s 后强制 kill

## 不允许

- 一次执行多个任务
- 跳过 PRECHECK 或 VERIFY
- 静默修改 Plan 内容
- 用 stub 代替真实实现