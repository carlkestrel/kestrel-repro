# 备份、迁移与恢复

## 备份

### 创建备份

```bash
python scripts/reproctl.py orchestrator backup \
  --project . \
  --include-checkpoints \
  --output-dir /path/to/backup
```

### 备份内容

备份包含：
- `.repro/execution/state.sqlite3`
- `.repro/startup/`
- `experiments/experiment_tracker.csv`
- 检查点（可选）

### 备份策略

```yaml
# repro.yaml
backup:
  enabled: true
  interval_hours: 24
  retention_days: 30
  include_checkpoints: false
  output_dir: /path/to/backup
```

## 迁移

### 检查迁移

```bash
python scripts/reproctl.py orchestrator migrate \
  --project . \
  --check-only
```

### 执行迁移

```bash
python scripts/reproctl.py orchestrator migrate \
  --project . \
  --target-version 2.0
```

### 迁移场景

#### 场景 1: 版本升级

```bash
# 备份
python scripts/reproctl.py orchestrator backup --project . --output-dir backup/

# 检查迁移
python scripts/reproctl.py orchestrator migrate --project . --check-only

# 执行迁移
python scripts/reproctl.py orchestrator migrate --project . --target-version 2.0
```

#### 场景 2: 跨目录迁移

```bash
# 在原目录备份
python scripts/reproctl.py orchestrator backup --project /old/path --output-dir /backup/path

# 在新目录恢复
python scripts/reproctl.py orchestrator restore --project /new/path --snapshot SNAPSHOT_ID
```

## 恢复

### 从备份恢复

```bash
# 列出备份
ls /path/to/backup/

# 恢复
python scripts/reproctl.py orchestrator restore \
  --project . \
  --snapshot SNAPSHOT_ID
```

### 恢复流程

1. 停止当前实例
2. 创建备份（防止数据丢失）
3. 执行恢复
4. 验证状态
5. 重新启动

### 恢复到特定版本

```bash
python scripts/reproctl.py orchestrator rollback-version \
  --project . \
  --backup-dir /path/to/backup/SNAPSHOT_ID
```

## 存储治理

### 检查磁盘状态

```bash
python scripts/reproctl.py storage status --project .
```

### 生成清理计划

```bash
python scripts/reproctl.py storage plan-cleanup --project .
```

输出示例：
```json
{
  "files_to_delete": [
    {"path": ".repro/execution/checkpoints/old-checkpoint.pth", "size_mb": 500}
  ],
  "space_to_free_mb": 500
}
```

### 执行清理

```bash
# 保存计划
python scripts/reproctl.py storage plan-cleanup --project . > cleanup_plan.json

# 审查计划
cat cleanup_plan.json

# 执行清理
python scripts/reproctl.py storage cleanup \
  --project . \
  --approved-plan cleanup_plan.json
```

### 应用保留策略

```bash
# 创建保留配置
cat > retention_config.json <<EOF
{
  "retention_days": 30,
  "checkpoint_retention": "latest_only",
  "log_retention_days": 7,
  "min_free_space_gb": 10
}
EOF

# 应用配置
python scripts/reproctl.py storage apply \
  --project . \
  --config retention_config.json
```

## 灾难恢复

### 完全系统故障

1. **在新系统上克隆仓库**

```bash
git clone <repo-url>
```

2. **安装依赖**

```bash
pip install -e .
```

3. **恢复最新备份**

```bash
python scripts/reproctl.py orchestrator restore \
  --project . \
  --snapshot latest \
  --output-dir /path/to/restore
```

4. **验证状态**

```bash
python scripts/reproctl.py status --project .
python scripts/reproctl.py verify --project .
```

### 数据库损坏

1. **检查备份**

```bash
ls -la /path/to/backup/
```

2. **恢复数据库**

```bash
python scripts/reproctl.py orchestrator restore \
  --project . \
  --snapshot <snapshot-id>
```

3. **如果无备份，尝试 WAL**

```bash
# 保存当前 WAL
cp .repro/execution/state.sqlite3-wal /tmp/backup.wal

# 重建数据库
sqlite3 .repro/execution/state.sqlite3 "PRAGMA integrity_check;"
```

## 完整性检查

### 运行完整性检查

```bash
python scripts/reproctl.py orchestrator integrity-check --project .
```

### 检查项目

- Schema 文件有效性
- 状态文件完整性
- 配置文件有效性
- 备份目录完整性

### 输出示例

```json
{
  "summary": "PASS",
  "checks_passed": [
    "schemas_valid",
    "state_valid",
    "config_valid"
  ],
  "warnings": [],
  "issues": []
}
```

## 最佳实践

### 定期备份

```bash
# Cron job
0 */6 * * * python /path/to/reproctl.py orchestrator backup --project /path/to/project --output-dir /backup/path
```

### 保留策略

| 类型 | 保留时间 |
|------|----------|
| 每日备份 | 7 天 |
| 每周备份 | 4 周 |
| 每月备份 | 6 个月 |
| 重大版本备份 | 永久 |

### 验证备份

```bash
# 验证备份完整性
python scripts/reproctl.py orchestrator integrity-check --project . --backup /path/to/backup

# 测试恢复
python scripts/reproctl.py orchestrator restore --project /tmp/test --snapshot <id>
```
