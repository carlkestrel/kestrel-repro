# 中文转换报告

## 基本信息
- 源语言: English
- 目标语言: 简体中文 (zh-CN)
- 转换日期: 2026-07-16
- 插件版本: v0.2.0
- 插件路径: ~/.cursor/plugins/local/dl-paper-repro

## 文件统计
- index.html: 翻译完成
- complete_manual.html: 需要使用 build.py 重建
- pages/*.html: 20/20 完成
- assets/styles.css: 复制完成（无变化）
- assets/app.js: 翻译完成
- assets/search-index.json: 重建完成 (78 条)

## 术语一致性

| 英文 | 中文 | 状态 |
|------|------|------|
| Paper Reproduction | 论文复现 | ✓ |
| Deep Learning | 深度学习 | ✓ |
| Reproduction Toolkit | 复现工具包 | ✓ |
| Quick Start | 快速开始 | ✓ |
| Overview | 概述 | ✓ |
| Installation | 安装 | ✓ |
| Architecture | 架构 | ✓ |
| Commands | 命令 | ✓ |
| Configuration | 配置 | ✓ |
| Project Structure | 项目结构 | ✓ |
| New Project | 新项目 | ✓ |
| Takeover Project | 项目接管 | ✓ |
| Automation | 自动化 | ✓ |
| Reproduction Protocol | 复现协议 | ✓ |
| Search GitHub | GitHub 搜索 | ✓ |
| Performance | 性能 | ✓ |
| Backup & Recovery | 备份与恢复 | ✓ |
| Testing & CI | 测试与 CI | ✓ |
| Bug Repair | Bug 修复 | ✓ |
| Security | 安全 | ✓ |
| Troubleshooting | 故障排除 | ✓ |
| FAQ | 常见问题 | ✓ |
| Glossary | 术语表 | ✓ |
| Gate System | Gate 系统 | ✓ |
| L0-L3 Short Loop | L0-L3 短循环 | ✓ |
| Evidence Chain | 证据链 | ✓ |
| Human Checkpoint | 人工检查点 | ✓ |
| Secrets Redaction | 敏感信息脱敏 | ✓ |
| orchestrator | 编排器 | ✓ |
| doctor | Doctor（保持英文） | ✓ |
| reproctl | reproctl（保持英文） | ✓ |

## 未翻译保留项

### 技术命令和参数
- reproctl 及所有子命令 (doctor, start, status, resume, stop, verify, version, init, can-launch, launch, run-short-loop, orchestrator, storage 等)
- 所有 CLI 参数 (--project, --mode, --plan, --expected-cuda, --dry-run 等)
- 命令输出文本

### 技术术语（保持英文）
- PyTorch, CUDA, GPU, CPU, RAM, SSD
- AMP, DDP, mIoU, CI/CD
- SQLite, JSON, YAML, CSV, SQL
- PID, SIGKILL, SIGTERM
- API, CLI, SDK
- Gate_0, Gate_1, Gate_2, Gate_3, Gate_4, Gate_5
- L0, L1, L2, L3
- WAL, PASS, FAIL, PENDING, RUNNING, SKIPPED
- EXIT_DOCTOR_FAIL, EXIT_ALREADY_RUNNING, EXIT_LOCK_HELD
- strict, optimized, diagnose, test, extend 模式名
- safe-auto, manual, unattended 自动化模式
- .repro/, scripts/, schemas/, templates/ 目录名

### 文件路径
- ~/.cursor/plugins/local/dl-paper-repro
- scripts/reproctl.py
- .repro/execution/state.sqlite3
- output/PAPER_PLAN.md
- 所有配置文件路径

### 环境变量
- REPRO_FAKE_GPU, REPRO_FAKE_CUDA, REPRO_FAKE_DISK_FREE
- CUDA_VISIBLE_DEVICES, GITHUB_TOKEN

### URLs 和标识符
- GitHub URLs
- arXiv IDs
- DOI

## 问题记录

### 已解决
1. 无

### 待处理
1. complete_manual.html 需要使用 build.py 重建才能包含所有翻译内容
2. build.py 需要支持 --language 参数来指定语言

## 复查结果

### 语言审计
- [x] 所有用户可见文本已翻译
- [x] 无遗留英文字句
- [x] 命令、路径、配置字段保持不变
- [x] 技术术语正确保留

### 渲染检查（待执行）
- [ ] Chrome: 侧边栏正常
- [ ] Chrome: 搜索正常
- [ ] Chrome: 深色模式正常
- [ ] Chrome: 移动端(375px)正常
- [ ] Chrome: 打印正常

### 链接检查（待执行）
- [ ] index.html → 所有页面链接正常
- [ ] 所有页面 → index.html 链接正常
- [ ] 无断开的锚点链接

### 搜索检查（待执行）
- [ ] "论文复现" 找到结果
- [ ] "paper reproduction" 找到结果
- [ ] "reproctl" 找到结果
- [ ] "CUDA" 找到结果
- [ ] "Gate" 找到结果

### 离线检查（待执行）
- [ ] complete_manual.html 完整渲染
- [ ] 搜索功能正常
- [ ] 主题切换正常
- [ ] 复制按钮正常

### 编码检查（待执行）
- [ ] UTF-8 编码正确
- [ ] 无乱码

## 总体状态: 需要修改

**注意**: 需要使用 build.py 重建 complete_manual.html 以包含所有翻译内容。
