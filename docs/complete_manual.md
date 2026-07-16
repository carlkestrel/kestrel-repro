# Deep Learning Paper Reproduction 完整手册

> 基于真实代码生成的文档 (v0.2.0)

## 目录

1. [系统架构](architecture.md)
2. [快速上手](quickstart.md)
3. [命令参考](command_reference.md)
4. [配置参考](configuration_reference.md)
5. [项目结构](project_structure.md)
6. [新项目工作流](new_project_workflow.md)
7. [接管工作流](takeover_workflow.md)
8. [自动化工作流](automation_workflow.md)
9. [复现协议](reproduction_protocol.md)
10. [硬件与性能](hardware_and_performance.md)
11. [搜索与 GitHub](search_and_github.md)
12. [测试与 CI](testing_and_ci.md)
13. [Bug 修复](bug_repair.md)
14. [备份、迁移与恢复](backup_migration_recovery.md)
15. [安全](security.md)
16. [故障排除](troubleshooting.md)
17. [FAQ](faq.md)
18. [术语表](glossary.md)
19. [Roadmap](roadmap.md)

---

## 快速参考

### 基本命令

```bash
# 版本信息
python scripts/reproctl.py version

# 预检
python scripts/reproctl.py doctor --project .

# 启动
python scripts/reproctl.py start --project . --plan output/PAPER_PLAN.md --mode strict

# 查看状态
python scripts/reproctl.py status --project .

# 恢复
python scripts/reproctl.py resume --project .

# 停止
python scripts/reproctl.py stop --project .
```

### Orchestrator 命令

```bash
# 运行控制器
python scripts/reproctl.py orchestrator run --project . --plan output/PAPER_PLAN.md

# 守护进程
python scripts/reproctl.py orchestrator daemon --project . start --plan output/PAPER_PLAN.md

# 查看状态
python scripts/reproctl.py orchestrator status --project .

# 审批
python scripts/reproctl.py orchestrator approve --project . apr_xxxxx
```

### Legacy 命令

```bash
# 初始化
python scripts/reproctl.py init --paper https://arxiv.org/abs/xxxx.xxxxx

# 短循环测试
python scripts/reproctl.py run-short-loop --level all

# 启动训练
python scripts/reproctl.py launch --seed 42 --epochs 300

# 记录实验
python scripts/reproctl.py record-experiment EXP001 module status --run-id R001
```

### 存储治理

```bash
# 磁盘状态
python scripts/reproctl.py storage status --project .

# 清理计划
python scripts/reproctl.py storage plan-cleanup --project .

# 执行清理
python scripts/reproctl.py storage cleanup --project . --approved-plan cleanup.json
```

---

## 文档说明

本文档基于 `scripts/reproctl.py` 实际代码生成：
- 所有命令参数来自 argparse 定义
- 所有退出码来自代码中的常量
- 所有状态来自 StateStore 定义
- 所有 Doctor 检查来自 doctor.py 实现

**自动生成目录**: `docs/generated/`
- `feature_status.csv`: 功能状态清单
- `cli_help.txt`: 原始 CLI 帮助输出
- `documentation_validation.md`: 文档验证报告

**最后更新**: 2024年
**版本**: 0.2.0
