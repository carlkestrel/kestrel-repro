# 搜索与 GitHub

## GitHub 搜索爬虫

### 基本用法

```bash
python scripts/research_crawler.py --query "semantic segmentation pytorch" --max-results 50
```

### 参数

| 参数 | 描述 | 默认值 |
|------|------|--------|
| `--query` | 搜索查询 | 必需 |
| `--max-results` | 最大结果数 | 50 |
| `--language` | 编程语言 | python |
| `--stars-min` | 最低星数 | 0 |
| `--stars-max` | 最高星数 | 无限制 |
| `--sort` | 排序方式 | stars |
| `--output` | 输出文件 | stdout |

### 搜索示例

```bash
# 搜索点云分割
python scripts/research_crawler.py \
  --query "point cloud segmentation pytorch" \
  --max-results 100 \
  --language python

# 搜索 3D 检测
python scripts/research_crawler.py \
  --query "3D object detection" \
  --stars-min 100 \
  --max-results 50
```

## 仓库发现

### 自动发现流程

1. 解析论文中的 GitHub 链接
2. 搜索相关关键词
3. 按星数排序
4. 过滤官方仓库

### 仓库评估标准

| 标准 | 描述 | 权重 |
|------|------|------|
| is_official | 是否官方仓库 | 高 |
| stars | Star 数 | 中 |
| has_train | 是否有训练脚本 | 高 |
| has_readme | 是否有 README | 中 |
| license | 许可证类型 | 中 |
| last_commit | 最后提交时间 | 低 |

## Cursor 命令

### /repro-discover

在 Cursor 中使用：
```
/repro-discover
```

会提示输入论文 URL 或关键词。

### /repro-contract

评估并选择仓库：
```
/repro-contract
```

显示评估结果供选择。

## 搜索语法

### GitHub 搜索操作符

```bash
# 精确搜索
"semantic segmentation"

# OR 搜索
semantic OR instance OR panoptic segmentation

# 排除
pytorch -tensorflow

# 主题搜索
topic:segmentation language:python

# 星级范围
stars:100..1000

# 最近更新
pushed:>2024-01-01
```

### 在 research_crawler.py 中使用

```bash
python scripts/research_crawler.py \
  --query "segmentation in:name OR description pushed:>2024-01-01 stars:>50"
```

## 过滤和排序

### 过滤选项

```bash
# 按语言过滤
--language python

# 按星数过滤
--stars-min 100

# 按更新时间过滤
--pushed-after 2024-01-01
```

### 排序选项

| 选项 | 描述 |
|------|------|
| stars | 按星数 |
| forks | 按 fork 数 |
| updated | 按更新时间 |

## 输出格式

### JSON 输出

```bash
python scripts/research_crawler.py \
  --query "segmentation pytorch" \
  --output results.json
```

### CSV 输出

```bash
python scripts/research_crawler.py \
  --query "segmentation pytorch" \
  --format csv \
  --output results.csv
```

## 仓库评估

### 评估脚本

```bash
python scripts/research_crawler.py \
  --evaluate \
  --repo https://github.com/author/repo
```

### 评估报告

输出包含：
- 基本信息（stars, forks, 描述）
- 代码质量指标
- 复现可能性评分
- 依赖分析

## 最佳实践

### 搜索策略

1. **从论文开始**：论文通常包含 GitHub 链接
2. **关键词扩展**：同义词、行业术语
3. **多轮搜索**：迭代细化搜索结果
4. **官方优先**：优先选择官方实现

### 评估策略

1. **完整性**：是否有训练、评估、推理代码
2. **活跃度**：最后一次提交时间
3. **社区**：Star 数、Issue 反馈
4. **兼容性**：依赖是否易安装

### 注意事项

1. **不要只看星数**：高星项目可能不完整
2. **验证许可证**：确保可合法复现
3. **检查分支**：主分支是否是最新的
4. **测试克隆**：在开始前测试克隆是否成功
