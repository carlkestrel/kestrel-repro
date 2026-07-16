---name: resumedescription: Resume execution from execution_state.json---
# /resume — 从 execution_state.json 恢复执行

## Purpose

在 Cursor 关闭、上下文丢失或崩溃后恢复执行。

## 步骤

1. 读取 `plan_snapshot.md` 并计算哈希，与 `execution_state.json` 中 `plan_hash` 对比
2. 校验失败 → 提示用户，**不**继续
3. 读取 `execution_state.json`：
   - `last_completed_task`
   - `running_processes`（是否有遗留 PID）
4. 检查遗留进程：杀残留 PID 或提示用户
5. 检查上一个任务的输出是否完整
6. 通过 acceptance_tests 确认任务是否真的完成（不依赖记忆）
7. 不重复已 PASS 的任务
8. 找到第一个 PENDING 且依赖已 PASS 的任务，调用 `/execute-next`

## 输入

- 无（从 `.execution/execution_state.json` 读取）

## 输出

- 恢复报告 `.execution/checkpoints/resume_<timestamp>.json`
- 如果恢复到任务：调用 `/execute-next`

## 失败模式

| 情况 | 处理 |
|---|---|
| plan_hash 不匹配 | 提示用户确认是否继续 |
| 状态文件损坏 | 从 `task_journal.jsonl` 重建 |
| 任务 PARTIAL | 重置为 PENDING，附加注释 |
| 任务有遗留 PID | 杀进程并标注 |

## 不允许

- 修改 Plan 哈希
- 跳过状态校验
- 直接执行下一个任务而不恢复上下文