# 安全

## 敏感信息脱敏

### 敏感信息检测

Doctor 检查会扫描敏感信息：

```bash
python scripts/reproctl.py doctor --project .
# 查看 security 检查项
```

### 脱敏规则

`scripts/startup/secrets_redactor.py` 脱敏以下模式：

| 模式 | 替换 |
|------|------|
| `Bearer <token>` | `Bearer [REDACTED]` |
| `password=*` | `password=[REDACTED]` |
| `token=*` | `token=[REDACTED]` |
| `Authorization: *` | `Authorization: [REDACTED]` |
| `AWS_SECRET*` | `[REDACTED]` |
| `OPENAI_API_KEY*` | `[REDACTED]` |

### 日志脱敏

```python
from startup.secrets_redactor import SecretsRedactor

redactor = SecretsRedactor()
safe_log = redactor.redact(sensitive_log)
```

## 凭证管理

### 环境变量

```bash
# 设置 API token
export GITHUB_TOKEN=ghp_xxxxx

# 在配置中使用
# repro.yaml
github:
  token: ${GITHUB_TOKEN}
```

### 凭证安全

1. **不要硬编码**：使用环境变量或密钥管理服务
2. **不要提交**：确保 `.gitignore` 包含敏感文件
3. **不要日志**：敏感信息会被脱敏，但尽量避免记录

## 依赖安全

### 安全检查

```bash
# 使用 pip-audit
pip install pip-audit
pip-audit

# 使用 safety
pip install safety
safety check
```

### 最小权限

```yaml
# repro.yaml
security:
  allow_network: true  # 仅在需要时启用
  require_git_pin: true
  sandbox_mode: limited
```

## 访问控制

### 文件权限

```bash
# 设置权限
chmod 600 .repro/run.lock
chmod 600 .repro/execution/state.sqlite3

# 限制目录访问
chmod 700 .repro/
```

### 多用户环境

对于多用户共享项目：

1. 使用 POSIX ACL 或
2. 为每个用户创建独立项目目录

## 安全最佳实践

### 1. 使用 HTTPS

```bash
# 克隆使用 HTTPS
git clone https://github.com/user/repo.git

# 避免 SSH 密钥泄露
```

### 2. 验证来源

```bash
# 检查仓库签名
git verify-commit <commit-sha>

# 检查提交者
git log --show-signature
```

### 3. 限制网络访问

```yaml
# repro.yaml
security:
  allow_network: false  # 离线环境
```

### 4. 沙箱模式

```yaml
# repro.yaml
security:
  sandbox_mode: strict
  # 限制文件系统访问
  # 限制网络访问
  # 限制进程创建
```

## 安全事件响应

### 检测到敏感信息泄露

1. **立即轮换凭证**
2. **删除泄露内容**
3. **检查 git 历史**
4. **报告安全事件**

### 清理敏感信息

```bash
# 使用 BFG 清理
git clone --mirror repo-url
java -jar bfg.jar --replace-text passwords.txt repo.git
git push --force
```

## 合规性

### 数据保留

| 数据类型 | 保留时间 | 说明 |
|----------|----------|------|
| 实验数据 | 项目周期 | 根据需要 |
| 日志 | 30 天 | 可配置 |
| 备份 | 90 天 | 可配置 |
| 凭证 | 不存储 | 使用环境变量 |

### 审计日志

所有敏感操作都会记录到事件日志：

```bash
# 查看审计日志
python scripts/reproctl.py orchestrator events --project . | grep -E "SECURITY|CREDENTIAL"
```

## 报告安全问题

如发现安全问题，请：

1. 不要在公开 issue 中报告
2. 发送邮件到 security@example.com
3. 提供详细复现步骤
4. 等待修复确认
