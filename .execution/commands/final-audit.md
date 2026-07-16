---name: final-auditdescription: Independent final audit from raw requirements---
# /final-audit — 独立最终审计

## Purpose

从原始需求角度独立审计，不依赖执行 Agent 的完成声明。生成 9 份审计产物。

## 步骤

1. 读取 `plan_snapshot.md` 原始需求
2. 读取 `requirement_traceability.csv` 全表
3. 逐条检查：requirement → task_ids → implementation_files → evidence_files
4. 检查实际代码（不基于声明）：
   - 文件存在
   - 内容有效（非 stub / TODO / 硬编码）
   - 来源可追溯
5. 重新计算关键 metrics（基于 raw_metrics 或 predictions）
6. 执行回归测试套件
7. 检查图表来源（不硬编码）
8. 检查 checkpoint 完整性
9. 检查插件可安装可加载
10. 输出到 `.execution/final_audit/` 9 份文件

## 9 份产物

| 文件 | 内容 |
|---|---|
| `execution_summary.md` | 执行摘要 |
| `requirement_traceability.csv` | 需求追踪最终版 |
| `final_self_audit.md` | 任务/阶段/最终三级自检 |
| `test_report.md` | 测试报告 |
| `reproduction_report.md` | 复现报告（如适用） |
| `evidence_index.md` | 证据索引 |
| `unresolved_items.md` | 未解决项 |
| `remaining_risks.md` | 剩余风险 |
| `go_pivot_nogo.md` | 最终决策 |

## 最终结论

- **COMPLETE**: 所有 mandatory 需求有证据且 PASS
- **PARTIALLY_COMPLETE**: 部分可选未完成，但 mandatory 全 PASS
- **BLOCKED**: mandatory 需求因外部依赖未完成
- **FAILED**: mandatory 需求或关键测试未通过

## 不允许

- 信任执行 Agent 的"已完成"声明
- 把 PARTIAL 算作 PASS
- 在 BLOCKED/FAILED 时输出"完成"