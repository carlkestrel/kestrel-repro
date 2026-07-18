---
description: Generate a structured reproduction report using the 10-section skeleton with cross-references to all cards.
---

# /repro-report (Phase 12)

> Generate the final `output/reports/reproduction_report.md` by
> filling `templates/repro_report_skeleton.md` and resolving all 5
> cross-references to data/environment/failure/parameter/benchmark
> cards.

## Usage

```
/repro-report
/repro-report --contract <path/to/research_contract.md>
/repro-report --out output/reports/reproduction_report.md
/repro-report --strict
/repro-report help
```

## 3-step flow

| Step | Reads | Writes |
|---|---|---|
| **1. Gather** | `templates/research_contract.md`, `templates/data_card.md`, `templates/environment_card.md`, `templates/parameter_table.md`, `templates/failure_case_report.md`, `experiments/<run_id>/raw_metrics.json` | in-memory dict |
| **2. Fill** | skeleton template + dict | `output/reports/reproduction_report.md` |
| **3. Cross-link** | the report + each card file | injects `source:` URLs into each section's "source:" line; runs traceability check |

## Required sections (10)

`§1 复现目标`, `§2 代码来源`, `§3 数据卡`, `§4 环境卡`, `§5 运行方法`,
`§6 实验结果`, `§7 失败与问题`, `§8 复现对比不足`, `§9 复现结论`,
`§10 交付物清单`.

If any section is missing, the report is rendered with a
`⚠ MISSING: §X` placeholder and a `--strict` invocation will REFUSE
to write the file.

## 5 cross-reference links (auto-filled)

| Section | Link |
|---|---|
| §3 数据卡 | `templates/data_card.md` |
| §4 环境卡 | `templates/environment_card.md` |
| §5 运行方法 | `templates/parameter_table.md §6` |
| §6 实验结果 | `templates/parameter_table.md §4` |
| §7 失败与问题 | `templates/failure_case_report.md` |

## Output

```
[repro-report] step 1/3 gather ............... 12 facts collected
[repro-report] step 2/3 fill .................. 10/10 sections filled
[repro-report] step 3/3 cross-link ............ 5/5 links injected
[repro-report] traceability check ............ 0 missing, 0 broken
[repro-report] wrote output/reports/reproduction_report.md
```

## Failure modes

- Missing `research_contract.md` → refuse to render.
- Missing `raw_metrics.json` for the active run → render `§6` with
  `⚠ MISSING` and refuse under `--strict`.
- Any "source:" link points to a non-existent file → refuse.

## What this command does NOT do

- Does NOT modify any card file (cards are owned by `/repro-card`).
- Does NOT auto-generate the report if the gate state is not PASS.
- Does NOT silence missing numbers; missing means missing.