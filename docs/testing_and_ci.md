# 测试与 CI

## 测试框架

### 测试结构

```
tests/
├── unit/
│   ├── test_state_store.py
│   ├── test_doctor.py
│   └── test_scheduler.py
├── integration/
│   ├── test_startup.py
│   └── test_orchestrator.py
└── fixtures/
    ├── sample_plan.yaml
    └── sample_state.json
```

## 运行测试

### 运行所有测试

```bash
pytest tests/
```

### 运行单元测试

```bash
pytest tests/unit/
```

### 运行集成测试

```bash
pytest tests/integration/
```

### 运行特定测试

```bash
pytest tests/unit/test_state_store.py
pytest tests/unit/test_doctor.py::test_check_gpu
```

## 单元测试

### 测试 StateStore

```python
def test_state_store_init():
    """Test StateStore initialization."""
    store = StateStore(project_root)
    assert store.db_path.exists()

def test_task_transition():
    """Test valid task state transitions."""
    store = StateStore(project_root)
    store.initialize_plan(plan)
    task = store.list_tasks()[0]
    result = store.transition(task["id"], "READY")
    assert result["status"] == "READY"
```

### 测试 Doctor

```python
def test_check_gpu():
    """Test GPU detection."""
    result = _check_gpu()
    assert result["name"] == "gpu"
    assert result["status"] in ("PASS", "WARNING")
```

### 测试 Scheduler

```python
def test_scheduler_next_task():
    """Test next task selection."""
    store = StateStore(project_root)
    scheduler = Scheduler(store)
    task = scheduler.next_task()
    assert task is not None
```

## 集成测试

### 测试 Startup

```python
def test_startup_flow(tmp_path):
    """Test complete startup flow."""
    project = tmp_path / "project"
    project.mkdir()
    
    # Initialize
    result = cli.main(["start", "--project", str(project), "--dry-run"])
    assert result == 0
```

### 测试 Orchestrator

```python
def test_orchestrator_run(tmp_path):
    """Test orchestrator run."""
    project = tmp_path / "project"
    project.mkdir()
    plan = tmp_path / "plan.yaml"
    plan.write_text(PLAN_YAML)
    
    result = cli.main(["run", "--project", str(project), "--plan", str(plan)])
    assert result == 0
```

## 持续集成

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

### 本地 CI 检查

```bash
# 预提交检查
./scripts/pre-commit.sh

# 完整 CI 模拟
./scripts/ci.sh
```

## 覆盖范围

### 覆盖目标

| 模块 | 目标覆盖率 |
|------|-----------|
| StateStore | 90% |
| Doctor | 80% |
| Scheduler | 80% |
| CLI | 70% |

### 生成覆盖率报告

```bash
pytest tests/ --cov=scripts --cov-report=html
open htmlcov/index.html
```

## 测试数据

### Fixtures

使用 pytest fixtures 提供测试数据：

```python
@pytest.fixture
def sample_plan():
    return {
        "plan_id": "test-001",
        "mode": "test",
        "tasks": [...]
    }

@pytest.fixture
def project_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    return root
```

### 示例文件

`tests/fixtures/` 包含示例：
- `sample_plan.yaml`: 测试计划
- `sample_state.json`: 测试状态
- `sample_config.yaml`: 测试配置

## Mock 和 Stub

### Mock GPU 检测

```python
def test_no_gpu(monkeypatch):
    monkeypatch.setenv("REPRO_FAKE_GPU", "0")
    result = _check_gpu()
    assert result["status"] == "WARNING"
```

### Mock 时间

```python
def test_timeout(monkeypatch):
    def fake_time():
        return 1000
    monkeypatch.setattr(time, "time", fake_time)
```

## 回归测试

### 命令输出稳定性

```bash
# 记录命令输出
python scripts/reproctl.py doctor --project . > expected_output.txt

# 在 CI 中验证
python scripts/reproctl.py doctor --project . | diff - expected_output.txt
```

### Schema 验证

```bash
python scripts/reproctl.py integrity-check
```

## 性能测试

### 慢测试标记

```python
@pytest.mark.slow
def test_full_training():
    """Full training test (slow)."""
    pass
```

### 运行慢测试

```bash
pytest tests/ -m slow
```

## 调试失败的测试

### 详细输出

```bash
pytest tests/unit/test_state_store.py -v -s
```

### 详细失败信息

```bash
pytest tests/ --tb=long --pdb
```

### 仅运行上次失败的测试

```bash
pytest tests/ --lf
```
