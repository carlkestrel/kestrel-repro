# kestrel-repro

证据驱动的深度学习论文复现插件 for Cursor。

从 GitHub 仓库复现 PyTorch 深度学习论文，包含阶段性门控、硬件感知优化和完整的证据链。

## 项目定位

**kestrel-repro** (原名 dl-paper-repro) 是一个 **Experimental（实验性）** 的 Cursor 插件 + CLI 系统，用于：

- 发现和评估论文候选仓库
- 分阶段验证复现可能性（L0-L3）
- 执行受控训练和评估
- 生成可审计的证据链
- 支持点云和通用深度学习论文

**重要声明**：本项目 **不是** NORA (Night Owl Research Agent)、AI-Researcher 或 SiamKPConv 的复制品。本项目受这些项目的**工作流架构启发**，从零开始重新实现。所有代码均为原创，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 当前成熟度

| 状态 | 说明 |
|------|------|
| **Experimental** | 本项目处于实验阶段，API 和功能可能发生变化 |

## 功能特性

- **9 个专业 Agent** — 编排、源码审计、数据/指标审计、运行时优化、证据验证、仓库发现、硬件适配审计
- **4 个 Skill** — 论文复现、深度学习运行时优化、点云复现、仓库选择
- **6 阶段门控** — 必须全部通过才能声称复现成功
- **程序化门控执行** — `reproctl.py` 在门控未通过时拒绝启动训练
- **GitHub 仓库发现** — 按论文匹配度而非 star 数排序
- **硬件适配评估** — 匹配本地 GPU/CPU/RAM/磁盘需求
- **安全克隆** — 执行任何安装脚本前进行静态安全审计
- **多模式执行** — strict_repro、optimized_repro_safe、experimental_fast
- **证据链验证** — 验证每个结果从 commit 到报告指标的可追溯性
- **机器可读 + 人类可读报告** — JSON/CSV 和 Markdown

## 安装方法

### 前置要求

- Cursor IDE（最新版本）
- Python 3.8+
- PyTorch 1.10+
- NVIDIA GPU + CUDA 11.0+（GPU 训练需要）
- Git

### 安装步骤

1. 克隆到 Cursor 插件目录：

```bash
mkdir -p ~/.cursor/plugins/local
git clone https://github.com/kestrel/dl-paper-repro.git \
  ~/.cursor/plugins/local/kestrel-repro
```

2. 重新加载 Cursor（`Cmd/Ctrl+Shift+P` → "Reload Window"）

或直接使用 Python 运行：

```bash
cd ~/.cursor/plugins/local/kestrel-repro
pip install -e .
python scripts/reproctl.py <command>
```

## Cursor 使用

在 Cursor Agent 中使用插件命令：

```
/repro-init paper=https://arxiv.org/abs/2103.14641 target="Table 2, mIoU on S3DIS"
```

这会创建 `.repro/` 目录，包含 `repro_spec.yaml`、`repo_adapter.yaml` 和 `state.json`。

```
/repro-discover paper=https://arxiv.org/abs/2103.14641
/repro-acquire
/repro-fit-hardware
```

这会找到论文作者的官方仓库、安全克隆并评估硬件兼容性。

## CLI 使用

### 初始化和预检

```bash
# 初始化新项目
python scripts/reproctl.py init --paper https://arxiv.org/abs/xxxx.xxxxx --target "Table 3, mIoU"

# 运行预检（不修改状态）
python scripts/reproctl.py doctor --project /path/to/project

# 启动项目
python scripts/reproctl.py start --project /path/to/project --plan output/PAPER_PLAN.md --mode strict
```

### 运行阶段性门控

```bash
/repro-audit         # Gate 0: 论文与源码审计
/repro-preflight     # Gate 1: 环境与数据检查
/repro-short-loop    # Gate 2: L0–L3 短循环验证
/repro-benchmark     # Gate 3: 吞吐与 parity 测试
```

### 训练和验证

```bash
# 检查能否启动训练
python scripts/reproctl.py can-launch

# 启动完整训练（Gate 未通过则被阻止）
python scripts/reproctl.py launch --mode strict_repro --seed 42 --epochs 300

# 验证结果
python scripts/reproctl.py verify --run-id=<uuid>

# 生成决策报告
python scripts/reproctl.py report
```

## 项目接管

当项目被中断或需要在另一台机器继续时：

1. **评估状态**：
   ```bash
   python scripts/reproctl.py status --project .
   cat .repro/startup/doctor_report.json
   ```

2. **清理（如需要）**：
   ```bash
   python scripts/reproctl.py stop --project .
   rm -f .repro/run.lock
   ```

3. **恢复**：
   ```bash
   python scripts/reproctl.py resume --project .
   ```

4. **继续执行**：
   ```bash
   python scripts/reproctl.py orchestrator run --project . --plan output/PAPER_PLAN.md --resume
   ```

详见 [docs/takeover_workflow.md](docs/takeover_workflow.md)。

## 执行模式

| 模式 | 描述 | 可用于论文结果 |
|------|------|---------------|
| `strict_repro` | FP32，单 GPU，论文 batch size | ✅ 是 |
| `optimized_repro_safe` | AMP、DDP、batch 调整（需 parity 测试） | ✅ 是，需证据 |
| `experimental_fast` | torch.compile，激进变更 | ❌ 否 |

## Smoke / Fast / Strict / Statistical 模式说明

本项目使用四种模式进行验证：

| 模式 | 用途 | 说明 |
|------|------|------|
| **Smoke** | L0 烟雾测试 | 单批次前向+反向传播，快速验证代码可运行 |
| **Fast** | L1-L3 短循环 | 过拟合测试、小数据集循环、检查点恢复 |
| **Strict** | 完整训练 | FP32 严格复现，不做任何优化 |
| **Statistical** | Parity 测试 | 验证优化模式与 strict 模式的数值一致性 |

**短循环测试详情 (Gate 2)**：

| Level | 测试 | 描述 |
|-------|------|------|
| L0 | Smoke Test | 单批次前向+反向传播 |
| L1 | Overfit Test | 单批次过拟合（验证模型容量） |
| L2 | Mini-Loop Test | 小数据集端到端循环 |
| L3 | Checkpoint Test | 检查点保存/加载验证 |

## 配置示例

### repro.yaml

```yaml
github:
  token: ${GITHUB_TOKEN}

security:
  allow_network: true
  require_git_pin: true
  sandbox_mode: limited

automation: safe-auto
mode: strict
```

### 环境变量

| 变量 | 描述 |
|------|------|
| `REPRO_FAKE_GPU` | 设为 `0` 模拟无 GPU |
| `REPRO_FAKE_CUDA` | 模拟 CUDA 版本 |
| `REPRO_FAKE_DISK_FREE` | 模拟可用磁盘空间（字节） |
| `REPRO_ORCHESTRATOR_DAEMON` | 设为 `1` 表示 daemon 进程 |
| `GITHUB_TOKEN` | GitHub API token |

详见 [docs/configuration_reference.md](docs/configuration_reference.md)。

## 数据和 Checkpoint 说明

### 数据集处理

- **S3DIS**、**ScanNet**、**SemanticKITTI** 数据集处理
- PLY 文件读取和标签映射
- KPConv、PointNet++、DGCNN 架构感知

### Checkpoint 管理

- 自动保存训练检查点
- 支持从检查点恢复训练
- 检查点完整性验证
- 使用 `HUMAN_CHECKPOINT` 环境变量强制人工检查

### 数据协议

```bash
# 验证数据集可用性
python scripts/reproctl.py doctor --project . | grep -i data
```

## 测试命令

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行特定测试
pytest tests/unit/test_state_store.py

# 生成覆盖率报告
pytest tests/ --cov=scripts --cov-report=html
```

### CI 检查

```bash
# 预提交检查
./scripts/pre-commit.sh

# 完整 CI 模拟
./scripts/ci.sh
```

详见 [docs/testing_and_ci.md](docs/testing_and_ci.md)。

## CI 说明

### GitHub Actions 配置

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest tests/ --cov=scripts/
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## 证据链

每个实验结果必须包含以下 8 个必需字段：

| 字段 | 描述 | 示例 |
|------|------|------|
| **commit** | Git commit SHA | `a1b2c3d4...` |
| **config** | 配置文件哈希 | `config_v2.yaml` |
| **data_manifest** | 数据集清单 | `S3DIS_area5.yaml` |
| **seed** | 随机种子 | `42` |
| **command** | 完整训练命令 | `python train.py --cfg ...` |
| **checkpoint** | 模型检查点路径 | `checkpoints/epoch_300.pth` |
| **raw_metrics** | 原始指标 JSON | `metrics.json` |
| **recomputed** | 复现指标值 | `mIoU: 0.723` |

验证证据链完整性：

```bash
python scripts/reproctl.py check-principles --spec-file spec.json
```

## 已知限制

本项目**无法**自动解决以下问题：

- 没有公开数据的论文
- 需要数据协议或申请的论文
- 评估协议不完整的论文
- GPU 架构相关数值差异的论文
- 原始实现有 bug 的论文

其价值在于使失败**可定位和可记录**，而非保证成功。

## 第三方致谢

本项目受以下项目的架构启发（**非复制品**）：

- **NORA (Night Owl Research Agent)** — MIT License
  - GRIND-Lab-Core/night_owl_research_agent
  - 架构灵感：Specialist Agent、Auto-review Loop、Approval Gate
  - 所有 NORA 启发组件均从零重实现

详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)（如存在）或 [github_prep/third_party_audit.md](github_prep/third_party_audit.md)。

## 引用方式

如果本项目对你的研究有帮助，请引用：

```bibtex
@software{kestrel-repro,
  title = {kestrel-repro: Evidence-driven Deep Learning Paper Reproduction},
  author = {kestrel},
  version = {0.2.0},
  year = {2026},
  url = {https://github.com/kestrel/dl-paper-repro}
}
```

## 安全说明

### 敏感信息处理

- Doctor 检查会扫描敏感信息
- 使用 `scripts/startup/secrets_redactor.py` 进行脱敏
- 敏感模式：`Bearer <token>`、`password=`、`token=`、`Authorization:`、`AWS_SECRET*`、`OPENAI_API_KEY*`

### 凭证管理

- 使用环境变量而非硬编码
- 确保 `.gitignore` 包含敏感文件
- 敏感信息会被自动脱敏

### 依赖安全

```bash
pip install pip-audit
pip-audit
```

### 安全最佳实践

1. 使用 HTTPS 克隆仓库
2. 验证提交来源
3. 限制网络访问
4. 使用沙箱模式

详见 [docs/security.md](docs/security.md)。

## 相关文档

- [README.md](README.md) — 英文版 README
- [docs/quickstart.md](docs/quickstart.md) — 快速上手指南
- [docs/architecture.md](docs/architecture.md) — 系统架构
- [docs/configuration_reference.md](docs/configuration_reference.md) — 配置参考
- [docs/takeover_workflow.md](docs/takeover_workflow.md) — 项目接管工作流
- [docs/security.md](docs/security.md) — 安全文档
- [docs/testing_and_ci.md](docs/testing_and_ci.md) — 测试与 CI

## License

MIT
