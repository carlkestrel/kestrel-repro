# Roadmap

## 版本 0.2.0 (当前版本)

### 已完成

- [x] 统一 CLI 入口 (`reproctl.py`)
- [x] Startup 子系统 (start/doctor/status/resume/stop/verify/version)
- [x] Orchestrator 子系统 (run/pause/continue/stop/status/events)
- [x] StateStore (SQLite WAL)
- [x] Task 状态机
- [x] 审批工作流
- [x] 后台守护进程
- [x] 备份和恢复
- [x] 状态迁移
- [x] 存储治理
- [x] Doctor 预检 (16 项检查)
- [x] Gate 系统 (Gate 0-5)
- [x] 短循环测试 (L0-L3)
- [x] 实验跟踪器
- [x] 人工检查点
- [x] 原则校验

## 版本 0.3.0 (计划中)

### 预期功能

- [ ] 增强的实验跟踪
  - [ ] 自动指标提取
  - [ ] 训练曲线可视化
  - [ ] 实验对比面板

- [ ] 改进的 Orchestrator
  - [ ] 更好的错误恢复
  - [ ] 任务重试策略
  - [ ] 并行任务支持

- [ ] 增强的存储治理
  - [ ] 自动清理策略
  - [ ] 存储配额
  - [ ] 多存储后端支持

- [ ] 更好的调试工具
  - [ ] 交互式调试器
  - [ ] 性能分析器
  - [ ] 可视化 DAG

## 版本 0.4.0 (计划中)

### 预期功能

- [ ] 云支持
  - [ ] AWS S3 检查点
  - [ ] GCP Storage 集成
  - [ ] Azure Blob 集成

- [ ] 增强的复现能力
  - [ ] 自动化数据集下载
  - [ ] 预处理管道
  - [ ] 模型下载和缓存

- [ ] 多用户支持
  - [ ] 用户认证
  - [ ] 访问控制
  - [ ] 审计日志

## 版本 0.5.0 (长期目标)

### 预期功能

- [ ] 协作功能
  - [ ] 实时状态同步
  - [ ] 团队仪表板
  - [ ] 评论和讨论

- [ ] 高级分析
  - [ ] 结果预测
  - [ ] 超参数搜索
  - [ ] 自动调优

- [ ] 集成
  - [ ] Slack/Discord 通知
  - [ ] Weights & Biases 集成
  - [ ] MLflow 集成

## 未确定的功能

以下功能尚未确定是否会实现：

- [ ] Jupyter Notebook 支持
- [ ] Web UI
- [ ] REST API
- [ ] Kubernetes 支持
- [ ] 实时协作编辑

## 已废弃的功能

暂无

## 贡献

欢迎贡献代码！请查看 CONTRIBUTING.md 了解如何开始。

## 反馈

如有问题或建议，请：
1. 在 GitHub 上开 issue
2. 在 Discussions 中讨论
3. 提交 Pull Request
