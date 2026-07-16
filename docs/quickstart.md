# 快速上手指南

本文档基于 `reproctl.py` 实际 CLI 输出编写。

## 1. 环境要求

- Python 3.8+
- PyTorch (用于 GPU 训练)
- CUDA 12.0+ (可选，用于 GPU 训练)

## 2. 安装

```bash
cd ~/.cursor/plugins/local/dl-paper-repro
pip install -e .
```

或直接使用 Python 运行：

```bash
python scripts/reproctl.py <command>
```

## 3. 快速命令参考

### 3.1 版本信息

```bash
python scripts/reproctl.py version
```

### 3.2 项目初始化

```bash
# 初始化新项目
python scripts/reproctl.py init --paper https://arxiv.org/abs/xxxx.xxxxx --target "Table 3, mIoU"
```

### 3.3 预检 (Doctor)

```bash
# 运行预检（不修改状态）
python scripts/reproctl.py doctor --project /path/to/project
python scripts/reproctl.py doctor --project /path/to/project --expected-cuda 12.0
```

### 3.4 启动项目

```bash
# 完整启动（需要 --project 和 --plan）
python scripts/reproctl.py start --project /path/to/project --plan output/PAPER_PLAN.md --mode strict
python scripts/reproctl.py start --project /path/to/project --plan output/PAPER_PLAN.md --mode diagnose

# 预演模式（不获取锁，不领取任务）
python scripts/reproctl.py start --project /path/to/project --plan output/PAPER_PLAN.md --dry-run
```

**Mode 选项**:
- `strict`: 严格复现模式（默认）
- `optimized`: 优化模式（需要通过 parity 测试）
- `diagnose`: 诊断模式
- `test`: 测试模式
- `extend`: 扩展模式

### 3.5 查看状态

```bash
# Startup 状态
python scripts/reproctl.py status --project /path/to/project

# Legacy 状态（显示 Gate 状态）
python scripts/reproctl.py status
```

### 3.6 恢复中断的项目

```bash
python scripts/reproctl.py resume --project /path/to/project
```

### 3.7 停止项目

```bash
python scripts/reproctl.py stop --project /path/to/project
```

### 3.8 验证启动证据

```bash
python scripts/reproctl.py verify --project /path/to/project
```

## 4. Legacy 命令（向后兼容）

### 4.1 检查能否启动训练

```bash
python scripts/reproctl.py can-launch
python scripts/reproctl.py can-launch --mode strict_repro
python scripts/reproctl.py can-launch --mode optimized_repro_safe
```

### 4.2 启动完整训练

```bash
python scripts/reproctl.py launch --seed 42 --epochs 300
python scripts/reproctl.py launch --mode optimized_repro_safe --seed 42 --epochs 300
python scripts/reproctl.py launch --config custom_config.yaml --seed 123
```

### 4.3 运行短循环测试

```bash
# 运行所有级别 (L0-L3)
python scripts/reproctl.py run-short-loop

# 只运行 L0
python scripts/reproctl.py run-short-loop --level L0

# 只运行 L1，指定步数
python scripts/reproctl.py run-short-loop --level L1 --overfit-steps 100

# 只运行 L2，指定轮数
python scripts/reproctl.py run-short-loop --level L2 --epochs 3
```

### 4.4 从检查点验证指标

```bash
python scripts/reproctl.py verify
python scripts/reproctl.py verify --run-id abc12345
```

### 4.5 生成报告

```bash
python scripts/reproctl.py report
```

### 4.6 手动更新 Gate 状态

```bash
python scripts/reproctl.py update-gate gate_0_paper_audit passed --evidence "paper_audit.md"
python scripts/reproctl.py update-gate gate_1_preflight failed
```

## 5. 实验跟踪

### 5.1 记录实验

```bash
python scripts/reproctl.py record-experiment EXP001 training-module running --run-id R001 --gpu-hours 12.5
```

### 5.2 更新实验

```bash
python scripts/reproctl.py update-experiment EXP001 --status success --metric-value 0.85
```

### 5.3 查询实验

```bash
python scripts/reproctl.py get-experiments --module training-module
python scripts/reproctl.py get-experiments --status success
python scripts/reproctl.py get-experiments --support-claim true
```

## 6. 人工检查点

### 6.1 检查检查点

```bash
python scripts/reproctl.py human-checkpoint
# 如果 HUMAN_CHECKPOINT=true，返回退出码 1
```

### 6.2 覆盖检查点

```bash
python scripts/reproctl.py human-checkpoint --action override --approved-by researcher_name --reason "已审查并批准"
```

## 7. 原则校验

```bash
# 从文件读取 spec
python scripts/reproctl.py check-principles --spec-file spec.json

# 从 stdin 读取
echo '{"mode":"strict_repro","repo_meta":{"is_official":true},"metrics_path":"metrics.json","commit_sha":"abc1234","reported_value":0.85,"recompute_value":0.84}' | python scripts/reproctl.py check-principles
```

## 8. Orchestrator 命令

### 8.1 运行控制器

```bash
python scripts/reproctl.py orchestrator run --project /path/to/project --plan output/PAPER_PLAN.md
python scripts/reproctl.py orchestrator run --project /path/to/project --plan output/PAPER_PLAN.md --mode optimized --resume
```

### 8.2 控制器状态

```bash
python scripts/reproctl.py orchestrator status --project /path/to/project
```

### 8.3 暂停/继续/停止

```bash
python scripts/reproctl.py orchestrator pause --project /path/to/project
python scripts/reproctl.py orchestrator continue --project /path/to/project
python scripts/reproctl.py orchestrator stop --project /path/to/project
```

### 8.4 事件日志

```bash
python scripts/reproctl.py orchestrator events --project /path/to/project
python scripts/reproctl.py orchestrator events --project /path/to/project --limit 100 --after-seq 50
```

### 8.5 审批工作流

```bash
# 查看待审批项
python scripts/reproctl.py orchestrator status --project /path/to/project

# 批准任务
python scripts/reproctl.py orchestrator approve --project /path/to/project apr_12345

# 拒绝任务
python scripts/reproctl.py orchestrator reject --project /path/to/project apr_12345 --reason "不符合要求"
```

### 8.6 后台守护进程

```bash
# 启动守护进程
python scripts/reproctl.py orchestrator daemon --project /path/to/project start --plan output/PAPER_PLAN.md

# 查看守护进程状态
python scripts/reproctl.py orchestrator daemon --project /path/to/project status

# 停止守护进程
python scripts/reproctl.py orchestrator daemon --project /path/to/project stop
```

### 8.7 迁移

```bash
# 检查迁移
python scripts/reproctl.py orchestrator migrate --project /path/to/project --check-only

# 执行迁移
python scripts/reproctl.py orchestrator migrate --project /path/to/project
```

### 8.8 备份和恢复

```bash
# 创建备份
python scripts/reproctl.py orchestrator backup --project /path/to/project
python scripts/reproctl.py orchestrator backup --project /path/to/project --include-checkpoints --output-dir /path/to/backup

# 恢复备份
python scripts/reproctl.py orchestrator restore --project /path/to/project --snapshot SNAPSHOT_ID
```

### 8.9 完整性检查

```bash
python scripts/reproctl.py orchestrator integrity-check --project /path/to/project
```

## 9. 存储治理

```bash
# 查看磁盘状态
python scripts/reproctl.py storage status --project /path/to/project

# 生成清理计划（预演）
python scripts/reproctl.py storage plan-cleanup --project /path/to/project

# 执行清理
python scripts/reproctl.py storage cleanup --project /path/to/project --approved-plan cleanup_plan.json

# 应用配置
python scripts/reproctl.py storage apply --project /path/to/project --config retention_config.json
```

## 10. 常见工作流

### 10.1 新项目流程

```bash
# 1. 初始化
python scripts/reproctl.py init --paper https://arxiv.org/abs/xxxx.xxxxx

# 2. 运行预检
python scripts/reproctl.py doctor --project .

# 3. 启动
python scripts/reproctl.py start --project . --plan output/PAPER_PLAN.md --mode strict
```

### 10.2 恢复中断流程

```bash
# 1. 检查状态
python scripts/reproctl.py status --project .

# 2. 恢复
python scripts/reproctl.py resume --project .

# 3. 验证
python scripts/reproctl.py verify --project .
```

### 10.3 训练验证流程

```bash
# 1. 检查能否训练
python scripts/reproctl.py can-launch

# 2. 运行短循环
python scripts/reproctl.py run-short-loop --level all

# 3. 启动训练
python scripts/reproctl.py launch --seed 42 --epochs 300

# 4. 验证结果
python scripts/reproctl.py verify
```
