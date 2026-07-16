# 项目结构

```
dl-paper-repro/
├── .cursor-plugin/
│   └── plugin.json              # Cursor 插件清单
├── agents/                      # Agent 定义
│   ├── skill.json
│   └── ...
├── commands/                    # Cursor 命令 (Markdown)
│   ├── repro-discover.md
│   ├── repro-contract.md
│   ├── repro-evaluate.md
│   └── ...
├── docs/                        # 文档 (你正在阅读)
│   ├── README.md
│   ├── architecture.md
│   ├── quickstart.md
│   ├── command_reference.md
│   ├── configuration_reference.md
│   ├── troubleshooting.md
│   ├── faq.md
│   ├── glossary.md
│   └── generated/              # 自动生成
│       ├── feature_status.csv
│       ├── cli_help.txt
│       └── documentation_validation.md
├── rules/                       # Cursor 规则
│   └── ...
├── schemas/                     # JSON Schema
│   ├── config.schema.json
│   ├── plan.schema.json
│   ├── task.schema.json
│   ├── state.schema.json
│   ├── automation_policy.schema.json
│   ├── adapter.schema.json
│   ├── run_manifest.schema.json
│   └── evidence.schema.json
├── scripts/                      # Python 脚本 (核心)
│   ├── reproctl.py              # 唯一 CLI 入口
│   ├── research_crawler.py       # GitHub 搜索爬虫
│   ├── repro_perf_tuner.py      # GPU 调优
│   ├── training_monitor.py       # 训练监控
│   ├── artifact_verify.py        # 工件验证
│   ├── compare_runs.py          # 运行比较
│   ├── environment_check.py     # 环境检查
│   ├── startup/                  # Startup 子系统
│   │   ├── __init__.py
│   │   ├── cli.py               # Startup CLI
│   │   ├── config.py            # 配置解析
│   │   ├── doctor.py            # 预检
│   │   ├── generate_artifacts.py
│   │   ├── lock.py             # PID 文件锁
│   │   ├── log_setup.py         # 日志设置
│   │   ├── plan_validate.py    # 计划验证
│   │   ├── recovery.py          # 恢复
│   │   ├── secrets_redactor.py  # 敏感信息脱敏
│   │   ├── state_machine.py    # 状态机
│   │   ├── stop.py             # 停止
│   │   └── storage_governance.py # 存储治理
│   └── orchestrator/            # Orchestrator 子系统
│       ├── __init__.py
│       ├── cli.py              # Orchestrator CLI
│       ├── controller.py       # 控制器
│       ├── state_store.py      # SQLite 状态存储
│       ├── task_executor.py    # 任务执行器
│       ├── watchdog.py         # 看门狗
│       ├── verifier.py         # 验证器
│       ├── scheduler.py        # 调度器
│       ├── policy_engine.py    # 策略引擎
│       ├── event_journal.py    # 事件日志
│       ├── process_manager.py  # 进程管理
│       ├── approval_gate.py    # 审批门
│       ├── migrate.py          # 迁移
│       └── backup.py           # 备份
├── skills/                      # Cursor Skills
│   ├── paper-reproduction/
│   ├── point-cloud-reproduction/
│   ├── deep-learning-runtime/
│   └── repository-selection/
├── templates/                    # 模板文件
│   ├── decision_log.md
│   ├── control_flags.md
│   └── ...
└── tests/                       # 测试
    └── ...
```

## 目录说明

### `.cursor-plugin/`

Cursor 插件配置目录，包含 `plugin.json` 清单文件。

### `commands/`

Cursor 命令定义，每个 `.md` 文件对应一个命令。

### `docs/`

文档目录。`generated/` 子目录包含自动生成的文件。

### `schemas/`

JSON Schema 定义，用于验证配置文件。

### `scripts/`

核心 Python 代码：

- `reproctl.py`: 唯一 CLI 入口，分发到 startup 或 orchestrator
- `startup/`: 启动子系统，负责预检、锁、状态检查
- `orchestrator/`: 编排子系统，负责任务调度、执行、监控

### `skills/`

Cursor Skills 定义，用于特定任务。

### `templates/`

模板文件，用于生成新项目结构。

## 执行布局

项目运行时生成以下结构：

```
project/
├── .repro/
│   ├── config.yaml              # 用户配置
│   ├── repro.yaml               # 项目配置
│   ├── run.lock                 # PID 锁
│   ├── repro_audit/
│   │   ├── STATE.json          # 状态
│   │   ├── DECISION_LOG.md     # 决策日志
│   │   └── checkpoints/
│   ├── startup/
│   │   ├── startup.log
│   │   ├── startup_state.json
│   │   ├── startup_summary.md
│   │   └── doctor_report.json
│   └── execution/
│       ├── execution_state.json
│       ├── state.sqlite3        # SQLite WAL
│       ├── controller.pid
│       ├── controller.heartbeat
│       ├── daemon.log
│       ├── checkpoints/
│       └── state.snapshot.*
├── primary/                     # 主要仓库
├── reference/                   # 参考仓库
├── experiments/
│   └── experiment_tracker.csv  # 实验跟踪
└── output/                      # 输出
    ├── PAPER_PLAN.md
    ├── manuscript/
    └── figures/
```
