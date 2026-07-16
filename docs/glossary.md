# 术语表

## A

### AMP (Automatic Mixed Precision)
混合精度训练，自动在 fp16 和 fp32 之间切换以提高性能。

### API (Application Programming Interface)
应用程序编程接口，本系统通过 CLI 和 Python API 提供功能。

## B

### Backup
备份，包含状态文件和检查点的快照，用于恢复。

### BUG
软件缺陷或错误。

## C

### CLI (Command Line Interface)
命令行界面，本系统的 `reproctl.py` 命令行工具。

### Controller
控制器，Orchestrator 子系统的核心组件，负责任务调度和执行。

### CUDA
NVIDIA 的并行计算平台和编程模型。

### Cursor Commands
Cursor IDE 中的命令，存储在 `commands/` 目录下的 Markdown 文件。

## D

### DDP (Distributed Data Parallel)
分布式数据并行，多 GPU 训练方法。

### Doctor
预检系统，运行一系列检查确保环境正确。

## E

### Event Journal
事件日志，记录系统中所有重要事件。

### Evidence Chain
证据链，证明复现结果可追溯的完整记录。

## F

### Fail
失败，任务或检查未通过。

## G

### Gate
门控，阶段性验收点，必须通过才能继续。

### Git Commit
Git 提交，唯一标识代码状态的哈希值。

### GPU
图形处理器，深度学习训练的主要硬件。

## H

### Heartbeat
心跳，控制器定期发送的信号，表示进程存活。

## I

### Integrity Check
完整性检查，验证系统文件和配置的有效性。

## L

### L0-L3
短循环测试的四个级别：
- L0: 冒烟测试
- L1: 过拟合测试
- L2: 小数据集循环
- L3: 检查点恢复

### Legacy Commands
遗留命令，向后兼容的旧命令。

### Lock
锁，防止并发访问的机制。

## M

### Migration
迁移，更新系统状态以兼容新版本。

### Mode
模式，执行环境或策略的配置。

## O

### Orchestrator
编排器，负责任务调度和执行控制的子系统。

### OOM (Out Of Memory)
内存不足错误。

## P

### Parity
奇偶性，不同配置下结果的等同性。

### PASS
通过，任务或检查成功完成。

### Pending
待处理，等待中。

### PID (Process ID)
进程标识符，唯一标识运行中的进程。

### Plan
计划，定义任务和依赖的文件。

### Policy
策略，控制任务执行和审批的规则。

### Preflight
预检，启动前的环境检查。

### Process Manager
进程管理器，管理系统进程的生命周期。

## R

### Recovery
恢复，从中断或故障中继续。

### Redactor
脱敏器，移除日志中的敏感信息。

### Reproctl
系统的 CLI 工具名称。

### Rollback
回滚，恢复到之前的状态或版本。

## S

### Scheduler
调度器，决定任务执行顺序的组件。

### Schema
模式，JSON 文件的结构定义。

### Secrets
敏感信息，需要保护的凭证或密钥。

### STABLE
稳定版本，已通过充分测试。

### Startup
启动系统，负责初始化和预检的子系统。

### State Store
状态存储，SQLite 数据库保存系统状态。

## T

### Task
任务，计划中定义的最小工作单元。

### Task Executor
任务执行器，运行任务命令的组件。

### Tolerance
容差，允许的结果偏差范围。

### Training Loop
训练循环，模型的完整训练过程。

## V

### Verify
验证，检查结果是否符合预期。

### VERSION
版本，系统的版本标识符。

## W

### WAL (Write-Ahead Logging)
预写日志，SQLite 的日志模式，提高并发性能。

### Watchdog
看门狗，监控任务超时和异常的组件。

## X

### eXperimental
实验性，功能尚未稳定。

## 其他

### ±0.5 pp
允许 0.5 个百分点的偏差。

### `safe-auto`
默认自动化策略，需要关键决策时暂停。

### `unattended`
无监控模式，不等待审批继续执行。
