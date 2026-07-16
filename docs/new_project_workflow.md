# 新项目工作流

## 概述

新项目工作流用于从零开始复现一篇论文。

## 阶段 1：初始化

### 1.1 创建项目目录

```bash
mkdir my-paper-repro && cd my-paper-repro
git init
```

### 1.2 初始化 reproctl

```bash
python /path/to/reproctl.py init \
  --paper https://arxiv.org/abs/xxxx.xxxxx \
  --target "Table 3, mIoU"
```

这会创建：
- `.repro/` 目录
- `experiments/` 目录
- 初始状态文件

## 阶段 2：论文分析

### 2.1 运行发现命令

使用 Cursor 命令 `/repro-discover` 查找候选仓库。

### 2.2 分析仓库

检查每个候选仓库：
- 是否官方仓库
- 是否有 README
- 是否有训练脚本
- 许可证

## 阶段 3：预检

### 3.1 运行 Doctor

```bash
python scripts/reproctl.py doctor --project .
python scripts/reproctl.py doctor --project . --expected-cuda 12.0
```

### 3.2 解读报告

Doctor 报告包含：
- `PASS`: 检查通过
- `WARNING`: 警告（不阻塞）
- `FAIL`: 失败（阻塞 start）

## 阶段 4：创建计划

### 4.1 编写 PAPER_PLAN.md

创建 `output/PAPER_PLAN.md`，包含：
- 论文元数据
- 任务列表
- 依赖关系
- 预算

### 4.2 验证计划

```bash
python scripts/reproctl.py integrity-check
```

## 阶段 5：启动

### 5.1 启动项目

```bash
python scripts/reproctl.py start \
  --project . \
  --plan output/PAPER_PLAN.md \
  --mode strict
```

### 5.2 监控状态

```bash
# Startup 状态
python scripts/reproctl.py status --project .

# Orchestrator 状态
python scripts/reproctl.py orchestrator status --project .
```

## 阶段 6：执行任务

### 6.1 查看下一个任务

```bash
python scripts/reproctl.py orchestrator next \
  --project . \
  --plan output/PAPER_PLAN.md
```

### 6.2 运行任务

Orchestrator 自动执行任务，或手动运行：

```bash
# 手动运行
python scripts/reproctl.py orchestrator run \
  --project . \
  --plan output/PAPER_PLAN.md
```

### 6.3 处理审批

如果任务需要人工审批：

```bash
# 查看待审批
python scripts/reproctl.py orchestrator status --project .

# 批准
python scripts/reproctl.py orchestrator approve \
  --project . \
  apr_xxxxx

# 拒绝
python scripts/reproctl.py orchestrator reject \
  --project . \
  apr_xxxxx \
  --reason "需要修改"
```

## 阶段 7：验证

### 7.1 运行短循环测试

```bash
python scripts/reproctl.py run-short-loop --level all
```

### 7.2 验证指标

```bash
python scripts/reproctl.py verify
```

### 7.3 检查原则

```bash
echo '{
  "mode": "strict_repro",
  "repo_meta": {"is_official": true},
  "metrics_path": "experiments/run-001/metrics.json",
  "commit_sha": "abc1234",
  "reported_value": 0.85,
  "recompute_value": 0.84
}' | python scripts/reproctl.py check-principles
```

## 阶段 8：生成报告

```bash
python scripts/reproctl.py report
```

## 检查清单

- [ ] 项目已初始化
- [ ] Doctor 检查通过
- [ ] 计划已创建并验证
- [ ] 项目已启动
- [ ] 所有强制任务完成
- [ ] Gate 2 (短循环) 通过
- [ ] Gate 5 (证据) 通过
- [ ] 报告已生成
