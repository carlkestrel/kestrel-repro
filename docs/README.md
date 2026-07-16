# Deep Learning Paper Reproduction

> 基于证据驱动的深度学习论文复现系统

## 简介

dl-paper-repro 是一个 Cursor 插件 + CLI 系统，用于：
- 发现和评估论文候选仓库
- 分阶段验证复现可能性 (Gate 0-5)
- 执行受控训练和评估
- 生成可审计的证据链
- 支持点云和通用深度学习论文

## 快速开始

```bash
# 1. 查看版本
python scripts/reproctl.py version

# 2. 运行预检
python scripts/reproctl.py doctor --project .

# 3. 启动项目
python scripts/reproctl.py start --project . --plan output/PAPER_PLAN.md --mode strict
```

## 核心命令

| 命令 | 描述 |
|------|------|
| `start` | 引导和启动项目 |
| `doctor` | 运行预检 |
| `status` | 显示项目状态 |
| `resume` | 恢复中断的项目 |
| `stop` | 停止项目 |
| `verify` | 验证证据链 |
| `orchestrator run` | 运行任务控制器 |

## 文档

完整文档位于 `docs/` 目录：

- [架构](docs/architecture.md)
- [快速上手](docs/quickstart.md)
- [命令参考](docs/command_reference.md)
- [配置参考](docs/configuration_reference.md)
- [新项目工作流](docs/new_project_workflow.md)
- [自动化工作流](docs/automation_workflow.md)
- [复现协议](docs/reproduction_protocol.md)
- [硬件与性能](docs/hardware_and_performance.md)
- [故障排除](docs/troubleshooting.md)
- [FAQ](docs/faq.md)

完整手册: [docs/complete_manual.md](docs/complete_manual.md)

## 版本

- 当前版本: 0.2.0
- CLI 入口: `scripts/reproctl.py`
