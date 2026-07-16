# 命令参考

本文档基于 `scripts/reproctl.py` 实际 CLI 实现编写。

## 1. Startup 命令

### 1.1 start

引导和启动项目。

**语法**:
```bash
python scripts/reproctl.py start --project <PATH> --plan <PLAN> [--mode MODE] [--dry-run] [--expected-cuda VERSION]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--project` | 是 | - | 项目根目录 |
| `--plan` | 是 | - | 计划文件路径 |
| `--mode` | 否 | strict | 执行模式 |
| `--log-level` | 否 | INFO | 日志级别 |
| `--dry-run` | 否 | False | 仅检查，不获取锁 |
| `--expected-cuda` | 否 | - | 期望 CUDA 版本 |

**Mode 选项**: `strict`, `optimized`, `diagnose`, `test`, `extend`

**退出码**:
- 0: 成功
- 2: 配置错误
- 3: Doctor 检查失败
- 4: 已有实例运行
- 5: 无效计划
- 8: 恢复失败

---

### 1.2 doctor

运行预检（无状态变更）。

**语法**:
```bash
python scripts/reproctl.py doctor --project <PATH> [--plan <PLAN>] [--expected-cuda VERSION]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--project` | 是 | - | 项目根目录 |
| `--plan` | 否 | - | 计划文件路径 |
| `--expected-cuda` | 否 | - | 期望 CUDA 版本 |
| `--log-level` | 否 | INFO | 日志级别 |

**退出码**:
- 0: 通过 (PASS/WARNING)
- 3: 失败 (FAIL)

---

### 1.3 status

显示项目状态、锁和计划哈希。

**语法**:
```bash
python scripts/reproctl.py status --project <PATH> [--log-level LEVEL]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--project` | 是 | - | 项目根目录 |
| `--log-level` | 否 | INFO | 日志级别 |

**输出格式**: JSON
```json
{
  "project_root": "/path/to/project",
  "plugin_version": "0.2.0",
  "execution_state": {...},
  "lock": {...},
  "checked_at": "2024-01-01T00:00:00+00:00"
}
```

**退出码**: 0/2

---

### 1.4 resume

恢复中断的项目。

**语法**:
```bash
python scripts/reproctl.py resume --project <PATH> [--log-level LEVEL]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--project` | 是 | - | 项目根目录 |
| `--log-level` | 否 | INFO | 日志级别 |

**退出码**:
- 0: 成功
- 2: 配置错误
- 4: 已有实例运行
- 8: 恢复失败

---

### 1.5 stop

优雅停止并清除锁。

**语法**:
```bash
python scripts/reproctl.py stop --project <PATH> [--log-level LEVEL]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--project` | 是 | - | 项目根目录 |
| `--log-level` | 否 | INFO | 日志级别 |

**退出码**: 0/2

---

### 1.6 verify

验证启动证据链。

**语法**:
```bash
python scripts/reproctl.py verify --project <PATH> [--log-level LEVEL]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--project` | 是 | - | 项目根目录 |
| `--log-level` | 否 | INFO | 日志级别 |

**验证项目**:
- `startup_state.json` 存在且有效
- `doctor_report.json` 存在
- `execution_state.json` 完整性
- `plan_hash` 稳定性

**退出码**:
- 0: 验证通过
- 8: 验证失败

---

### 1.7 version

打印插件和 CLI 版本。

**语法**:
```bash
python scripts/reproctl.py version
```

**输出格式**: JSON
```json
{
  "reproctl": "0.2.0",
  "plugin": "0.2.0",
  "plugin_root": "/path/to/plugin",
  "platform": "linux"
}
```

**退出码**: 0

---

## 2. Legacy 命令

### 2.1 init

初始化新项目。

**语法**:
```bash
python scripts/reproctl.py init [--paper URL] [--target METRIC]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--paper` | 否 | - | 论文 URL 或 arXiv ID |
| `--target` | 否 | - | 目标指标 |

**退出码**: 0/1

---

### 2.2 can-launch

检查能否启动训练。

**语法**:
```bash
python scripts/reproctl.py can-launch [--mode MODE]
```

**Mode 选项**: `strict_repro`, `optimized_repro_safe`, `experimental_fast`

**退出码**:
- 0: 可以启动
- 1: 不能启动

---

### 2.3 launch

启动完整训练。

**语法**:
```bash
python scripts/reproctl.py launch [--mode MODE] [--seed SEED] [--epochs EPOCHS] [--config CONFIG] [extra ...]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--mode` | 否 | strict_repro | 执行模式 |
| `--seed` | 否 | 42 | 随机种子 |
| `--epochs` | 否 | 300 | 训练轮数 |
| `--config` | 否 | - | 配置文件路径 |
| `extra` | 否 | - | 额外参数 |

**Mode 选项**: `strict_repro`, `optimized_repro_safe`, `experimental_fast`

**退出码**:
- 0: 成功
- 1: 失败

---

### 2.4 run-short-loop

运行短循环验证测试。

**语法**:
```bash
python scripts/reproctl.py run-short-loop [--level LEVEL] [--config CONFIG] [--overfit-steps STEPS] [--epochs EPOCHS]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--level` | 否 | all | 测试级别 |
| `--config` | 否 | - | 配置文件 |
| `--overfit-steps` | 否 | 100 | L1 过拟合步数 |
| `--epochs` | 否 | 3 | L2 训练轮数 |

**Level 选项**: `L0`, `L1`, `L2`, `L3`, `all`

| Level | 测试 |
|-------|------|
| L0 | Smoke Test (单批次前向+反向) |
| L1 | Overfit Test (单批次过拟合) |
| L2 | Mini-Loop Test (端到端小数据集) |
| L3 | Checkpoint Resume Test |

**退出码**: 0/1

---

### 2.5 verify

从检查点验证指标。

**语法**:
```bash
python scripts/reproctl.py verify [--run-id ID]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--run-id` | 否 | - | 指定运行 ID |

**退出码**: 0/1

---

### 2.6 report

生成报告。

**语法**:
```bash
python scripts/reproctl.py report
```

**退出码**: 0

---

### 2.7 update-gate

手动更新门状态。

**语法**:
```bash
python scripts/reproctl.py update-gate <GATE> <STATUS> [--evidence PATH]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `GATE` | 是 | - | 门名称 |
| `STATUS` | 是 | - | 状态 (passed/failed/pending) |
| `--evidence` | 否 | - | 证据路径 |

**Gate 名称**:
- `gate_0_paper_audit`
- `gate_1_preflight`
- `gate_2_short_loop`
- `gate_3_parity`
- `gate_4_full_training`
- `gate_5_evidence`

**退出码**: 0/1

---

### 2.8 record-experiment

追加实验行。

**语法**:
```bash
python scripts/reproctl.py record-experiment <ID> <MODULE> <STATUS> [options]
```

**位置参数**:
| 参数 | 描述 |
|------|------|
| `ID` | 实验 ID |
| `MODULE` | 模块名称 |
| `STATUS` | 状态 |

**选项**:
| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--run-id` | - | 运行 ID |
| `--support-claim` | - | 支持声明 |
| `--parent-run-id` | - | 父运行 ID |
| `--start-time` | now | 开始时间 |
| `--end-time` | - | 结束时间 |
| `--duration-min` | - | 持续时间（分钟） |
| `--gpu-hours` | - | GPU 小时数 |
| `--metric-value` | - | 指标值 |
| `--status-detail` | - | 状态详情 |

**退出码**: 0

---

### 2.9 update-experiment

更新实验行。

**语法**:
```bash
python scripts/reproctl.py update-experiment <ID> [options]
```

**位置参数**:
| 参数 | 描述 |
|------|------|
| `ID` | 实验 ID |

**选项**: 同 `record-experiment`

**退出码**:
- 0: 成功
- 1: 未找到

---

### 2.10 get-experiments

查询实验。

**语法**:
```bash
python scripts/reproctl.py get-experiments [--module MODULE] [--status STATUS] [--support-claim CLAIM] [--experiment-id ID]
```

**选项**:
| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--module` | - | 模块过滤 |
| `--status` | - | 状态过滤 |
| `--support-claim` | - | 声明过滤 |
| `--experiment-id` | - | 实验 ID |

**退出码**: 0

---

### 2.11 human-checkpoint

强制 12 项人工检查。

**语法**:
```bash
python scripts/reproctl.py human-checkpoint [--action ACTION] [--reason REASON] [--approved-by NAME] [--item ITEM]
```

**参数**:
| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--action` | check | 操作 (check/override) |
| `--reason` | - | 原因 |
| `--approved-by` | - | 批准人 |
| `--item` | - | 项目编号 |

**退出码**:
- 0: 通过
- 1: 阻塞 (HUMAN_CHECKPOINT=true)
- 2: 参数错误

---

### 2.12 check-principles

校验 5 项最高原则。

**语法**:
```bash
python scripts/reproctl.py check-principles [--spec-file FILE]
```

**参数**:
| 参数 | 描述 |
|------|------|
| `--spec-file` | JSON spec 文件路径 |
| stdin | JSON spec (如果未指定文件) |

**校验原则**:
1. `require_official_first`: 官方仓库优先
2. `require_strict_mode`: 严格模式
3. `require_raw_metrics`: 原始指标
4. `require_provenance`: 溯源
5. `require_reproducibility`: 可复现性

**退出码**:
- 0: 全部通过
- 2: 有失败

---

### 2.13 integrity-check

验证 schema 和核心工件完整性。

**语法**:
```bash
python scripts/reproctl.py integrity-check
```

**验证项目**:
- 8 个 schema 文件 (JSON 有效性)
- `storage_governance.py` 可导入性

**退出码**:
- 0: 通过
- 1: 有错误

---

## 3. Orchestrator 命令

**前缀**: `reproctl orchestrator`

### 3.1 orchestrator run

运行持久化控制器循环。

**语法**:
```bash
python scripts/reproctl.py orchestrator run --project <PATH> --plan <PLAN> [options]
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--project` | 是 | - | 项目根目录 |
| `--plan` | 是 | - | 计划文件 |
| `--mode` | 否 | - | 执行模式 |
| `--automation` | 否 | safe-auto | 自动化策略 |
| `--policy` | 否 | - | 策略文件 |
| `--resume` | 否 | False | 恢复模式 |
| `--until` | 否 | blocked-or-complete | 运行策略 |

**退出码**: 0/7/10

---

### 3.2 orchestrator status

显示状态摘要。

**语法**:
```bash
python scripts/reproctl.py orchestrator status --project <PATH>
```

**参数**:
| 参数 | 必选 | 默认值 | 描述 |
|------|------|--------|------|
| `--project` | 是 | - | 项目根目录 |

**输出格式**: JSON
```json
{
  "project_root": "/path/to/project",
  "control_state": "RUNNING",
  "counts": {"PASS": 5, "RUNNING": 1, "PENDING": 3},
  "tasks": [...],
  "pending_approvals": [...],
  "heartbeat": {...}
}
```

**退出码**: 0

---

### 3.3 orchestrator pause

暂停 orchestrator。

**语法**:
```bash
python scripts/reproctl.py orchestrator pause --project <PATH>
```

**退出码**: 0

---

### 3.4 orchestrator continue

继续 orchestrator。

**语法**:
```bash
python scripts/reproctl.py orchestrator continue --project <PATH>
```

**退出码**: 0

---

### 3.5 orchestrator stop

停止 orchestrator。

**语法**:
```bash
python scripts/reproctl.py orchestrator stop --project <PATH>
```

**退出码**: 0

---

### 3.6 orchestrator events

事件日志流。

**语法**:
```bash
python scripts/reproctl.py orchestrator events --project <PATH> [--limit N] [--after-seq N]
```

**参数**:
| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--limit` | 200 | 最大事件数 |
| `--after-seq` | 0 | 从序列号之后开始 |

**退出码**: 0

---

### 3.7 orchestrator next

显示下一个任务。

**语法**:
```bash
python scripts/reproctl.py orchestrator next --project <PATH> --plan <PLAN> [--policy PATH]
```

**退出码**: 0

---

### 3.8 orchestrator approve

批准待审批任务。

**语法**:
```bash
python scripts/reproctl.py orchestrator approve --project <PATH> <ID>
```

**参数**:
| 参数 | 描述 |
|------|------|
| `ID` | approval ID (apr_...) 或 task ID |

**退出码**: 0/3

---

### 3.9 orchestrator reject

拒绝待审批任务。

**语法**:
```bash
python scripts/reproctl.py orchestrator reject --project <PATH> <ID> [--reason TEXT]
```

**参数**:
| 参数 | 描述 |
|------|------|
| `ID` | approval ID 或 task ID |
| `--reason` | 拒绝原因 |

**退出码**: 0/3

---

### 3.10 orchestrator daemon

后台守护进程控制。

**语法**:
```bash
python scripts/reproctl.py orchestrator daemon --project <PATH> <ACTION> [--plan <PLAN>] [options]
```

**Action**:
- `start`: 启动守护进程
- `status`: 查看状态
- `stop`: 停止守护进程

**退出码**: 0/2/10

---

### 3.11 orchestrator migrate

状态迁移。

**语法**:
```bash
python scripts/reproctl.py orchestrator migrate --project <PATH> [--check-only] [--target-version VERSION]
```

**退出码**: 0/1

---

### 3.12 orchestrator backup

创建备份快照。

**语法**:
```bash
python scripts/reproctl.py orchestrator backup --project <PATH> [--include-checkpoints] [--output-dir PATH]
```

**退出码**: 0

---

### 3.13 orchestrator restore

从备份恢复。

**语法**:
```bash
python scripts/reproctl.py orchestrator restore --project <PATH> --snapshot <ID> [--output-dir PATH]
```

**退出码**: 0/1

---

### 3.14 orchestrator integrity-check

运行完整性检查。

**语法**:
```bash
python scripts/reproctl.py orchestrator integrity-check --project <PATH>
```

**退出码**: 0/1

---

### 3.15 orchestrator rollback-version

回滚版本。

**语法**:
```bash
python scripts/reproctl.py orchestrator rollback-version --project <PATH> --backup-dir <PATH>
```

**退出码**: 0/1

---

## 4. Storage 命令

### 4.1 storage status

检查磁盘空间。

**语法**:
```bash
python scripts/reproctl.py storage status --project <PATH>
```

**退出码**: 0/1

---

### 4.2 storage plan-cleanup

生成清理计划（预演）。

**语法**:
```bash
python scripts/reproctl.py storage plan-cleanup --project <PATH>
```

**退出码**: 0

---

### 4.3 storage cleanup

执行清理。

**语法**:
```bash
python scripts/reproctl.py storage cleanup --project <PATH> --approved-plan <PATH>
```

**退出码**: 0

---

### 4.4 storage apply

应用保留和磁盘策略。

**语法**:
```bash
python scripts/reproctl.py storage apply --project <PATH> [--config <PATH>]
```

**退出码**: 0

---

## 5. 退出码汇总

| 退出码 | 含义 | 来源 |
|--------|------|------|
| 0 | 成功 | 通用 |
| 1 | 失败/参数错误 | Legacy 命令 |
| 2 | 配置错误 | Startup |
| 3 | Doctor 失败 | Startup |
| 4 | 已有实例运行 | Startup |
| 5 | 无效计划 | Startup |
| 6 | 任务失败 | Startup |
| 7 | 任务阻塞 | Orchestrator |
| 8 | 恢复失败 | Startup |
| 9 | 安全阻塞 | Startup |
| 10 | 内部错误 | 通用 |
