# Contributing to kestrel-repro

Thank you for contributing to kestrel-repro. This plugin enables evidence-driven deep learning paper reproduction. All contributors must follow these guidelines to ensure reproducibility and quality.

---

## 1. Development Environment Setup

### Prerequisites

- Python 3.8+
- PyTorch 1.10+
- NVIDIA GPU with CUDA 11.0+ (for GPU training)
- Git
- Cursor IDE

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/kestrel/dl-paper-repro.git \
  ~/.cursor/plugins/local/kestrel-repro

# Install in development mode
cd ~/.cursor/plugins/local/kestrel-repro
pip install -e .

# Or run directly without installation
python scripts/reproctl.py <command>
```

### Verify Installation

```bash
python scripts/reproctl.py doctor --project .
```

### Testing Your Changes

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run all tests with coverage
pytest tests/ --cov=scripts/

# Run pre-commit checks
./scripts/pre-commit.sh
```

---

## 2. Branch and Commit Conventions

### Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<short-description>` | `feature/add-parity-check` |
| Bug fix | `fix/<issue-description>` | `fix/gate-status-race` |
| Docs | `docs/<topic>` | `docs/update-quickstart` |
| Reproductions | `repro/<paper-name>/<phase>` | `repro/pointnet2/audit` |

### Commit Messages

Follow the Conventional Commits specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `chore`: Build process, tooling, CI/CD

**Examples:**

```
feat(agents): add hardware-fit auditor for GPU memory estimation
fix(reproctl): correct gate status transition logic
docs(contributing): add reproduction issue template guidelines
test(short-loop): add L2 mini-dataset validation test
refactor(scripts): extract gate enforcement to separate module
```

### Commit Message Rules

- Use imperative mood ("add feature" not "added feature")
- Keep the first line under 72 characters
- Reference issues and PRs in the footer: `Closes #123`
- Include evidence of test passes in the body when relevant

---

## 3. Test Commands

### Running Tests

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_state_store.py

# Specific test method
pytest tests/unit/test_doctor.py::test_check_gpu

# With verbose output
pytest tests/ -v

# With detailed failure info
pytest tests/ --tb=long

# Only last failed tests
pytest tests/ --lf
```

### Slow Tests

```bash
# Run slow tests (marked with @pytest.mark.slow)
pytest tests/ -m slow
```

### CI Simulation

```bash
# Pre-commit checks
./scripts/pre-commit.sh

# Full CI pipeline
./scripts/ci.sh
```

### Regression Tests

```bash
# Record command output
python scripts/reproctl.py doctor --project . > expected_output.txt

# Verify in CI
python scripts/reproctl.py doctor --project . | diff - expected_output.txt

# Schema validation
python scripts/reproctl.py integrity-check
```

---

## 4. Code Style (Lint/Type Check)

### Style Guide

- Python code follows PEP 8
- Use type hints for all function signatures
- Docstrings for public functions and classes
- Maximum line length: 88 characters (Black default)

### Formatting and Linting

```bash
# Format code (Black)
black scripts/ tests/

# Check formatting
black --check scripts/ tests/

# Lint code (Ruff)
ruff check scripts/ tests/

# Type check (mypy)
mypy scripts/ --ignore-missing-imports
```

### Pre-commit Hook

Install pre-commit hooks to run checks automatically:

```bash
pip install pre-commit
pre-commit install
```

### Code Review Checklist

Before opening a PR, verify:
- [ ] All new functions have type hints
- [ ] All public APIs have docstrings
- [ ] No hardcoded values (use constants/configuration)
- [ ] Tests cover new functionality
- [ ] Documentation updated if needed

---

## 5. Bug Report Guidelines

### Before Submitting

1. Check existing issues to avoid duplicates
2. Verify bug is reproducible with latest code
3. Check if it reproduces in `diagnose` mode

### Creating a Bug Report

Include the following in your issue:

**Required Information:**
- Python version (`python --version`)
- PyTorch version
- CUDA version
- GPU model
- Cursor IDE version
- Operating system

**Reproduction Steps:**
1. Step-by-step instructions
2. Exact command used
3. Expected behavior
4. Actual behavior

**Artifacts:**
- Output of `python scripts/reproctl.py doctor --project .`
- Relevant log files from `.repro/logs/`
- Gate status (`python scripts/reproctl.py status`)

**Example Bug Report:**

```markdown
## Environment
- Python: 3.10.12
- PyTorch: 2.1.0
- CUDA: 12.1
- GPU: NVIDIA RTX 3090
- OS: Ubuntu 22.04
- kestrel-repro: v0.3.2

## Bug Description
Gate 2 fails to transition to RUNNING state after L0 completes.

## Steps to Reproduce
1. Initialize project with `/repro-init paper=<url>`
2. Run `/repro-audit` - passes
3. Run `/repro-preflight` - passes
4. Run `/repro-short-loop --level L0` - completes
5. Observe gate_2_short_loop status remains "READY" instead of "RUNNING"

## Expected Behavior
Gate 2 should transition to RUNNING when L0 completes.

## Actual Behavior
Gate 2 stays in READY state.

## Relevant Logs
[Attach logs from .repro/logs/]
```

---

## 6. Paper Reproduction Issue Report Template

When reporting issues during paper reproduction, use this template:

```markdown
## Paper Information
- **Paper Title**: [Full title]
- **arXiv URL**: [URL]
- **Official Repository**: [URL]
- **Target Claim**: [Table X, metric Y]

## Reproduction Environment
- **Hardware**: GPU model, RAM, disk space
- **Python**: Version
- **PyTorch**: Version
- **CUDA**: Version
- **Dataset Version**: [Exact version/hash used]

## Execution Mode
- [ ] strict_repro
- [ ] optimized_repro_safe
- [ ] experimental_fast

## Gate Status
| Gate | Status | Evidence |
|------|--------|----------|
| Gate 0: Paper & Source Audit | PASS/FAIL | [file] |
| Gate 1: Preflight | PASS/FAIL | [file] |
| Gate 2: Short Loop (L0-L3) | PASS/FAIL | [file] |
| Gate 3: Parity Testing | PASS/FAIL | [file] |
| Gate 4: Full Training | PASS/FAIL | [file] |
| Gate 5: Evidence Verification | PASS/FAIL | [file] |

## Issue Description
[Detailed description of the problem]

## Evidence Chain
- **Commit**: [git hash]
- **Config**: [path or inline]
- **Seed**: [value]
- **Command**: [exact command]
- **Checkpoints**: [paths]
- **Raw Metrics**: [path to metrics file]

## Expected vs Actual Results
| Metric | Expected | Actual | Difference |
|--------|----------|--------|------------|
| [mIoU] | [0.85] | [0.82] | [-0.03] |

## Failure Analysis
[Root cause analysis if known]

## Attempted Solutions
1. [Solution 1]
2. [Solution 2]

## Questions for Authors
[Any clarifications needed from paper authors]
```

---

## 7. Fast vs Strict Result Labeling Requirements

All reproduction results must be clearly labeled with their execution mode.

### Result Mode Definitions

| Mode | Description | Valid for Paper Claims |
|------|-------------|----------------------|
| `strict_repro` | FP32, single GPU, paper batch size, exact commit | ✅ Yes |
| `optimized_repro_safe` | AMP, DDP, batch changes (after parity testing) | ✅ Yes, with evidence |
| `experimental_fast` | torch.compile, aggressive changes | ❌ Never |

### Labeling Requirements

**Every result file must include:**

```yaml
mode: strict_repro  # or optimized_repro_safe or experimental_fast
evidence:
  commit: abc1234
  config: path/to/config.yaml
  seed: 42
  command: python train.py --config config.yaml --seed 42
  gpu: NVIDIA RTX 3090
  cuda: 12.1
```

### When to Use Each Mode

| Scenario | Mode |
|----------|------|
| Validating paper's main claim | `strict_repro` |
| Checking implementation correctness | `strict_repro` |
| Optimizing for hardware after parity | `optimized_repro_safe` |
| Exploratory experiments | `experimental_fast` |
| Proposing improvements | ❌ Never use experimental results |

### Parity Requirements for optimized_repro_safe

Before claiming results with optimizations:
1. Run `strict_repro` baseline (1-5 epochs)
2. Run `optimized_repro_safe` with same epochs
3. Verify metric difference < 0.5% for segmentation
4. Document the optimization and parity evidence

---

## 8. Prohibitions

### No Hardcoded Values

Never hardcode in reproduction scripts:
- ❌ `batch_size = 16` (use config value)
- ❌ `learning_rate = 0.001` (use config value)
- ❌ `num_workers = 4` (detect from system)
- ❌ Paths like `/home/user/data` (use environment/config)

### No Simulated Metrics

Never submit fabricated or simulated results:
- ❌ Results from `random()` or `np.random()`
- ❌ Metrics copied from the paper without verification
- ❌ "Representative" results claiming to be reproducible
- ❌ Modified ground truth to match paper claims

### Permitted Placeholder Values

These are acceptable for testing without GPU:
```python
# In test fixtures only
MOCK_GPU_MEMORY = 24 * 1024**3  # 24 GB
MOCK_METRICS = {"mIoU": 0.85}   # For unit tests only
```

### Enforcement

- CI checks for hardcoded paths with regex
- Evidence chain verification rejects missing artifacts
- Human checkpoint required for final report

---

## 9. Third-Party Code Requirements

### Source Attribution

All third-party code must be:
1. Licensed (no unpublished code)
2. Attributed in documentation
3. Isolated from core reproduction logic

### Adding Dependencies

New dependencies must:
1. Be listed in `setup.py` or `pyproject.toml`
2. Include version constraints
3. Have security review for new dependencies > 1MB
4. Be documented in README if user-facing

### Forked Repositories

If forking a paper's code:
1. Document the fork in `sources.lock.yaml`
2. Pin to specific commit
3. Track modifications in `CHANGES_FORKED.md`

### Citation Requirements

If reproducing results from another project:
1. Cite the original paper
2. Cite the original repository
3. Note any modifications made

### Code License Compatibility

All code must be MIT, Apache 2.0, or BSD compatible:
- ❌ GPL/AGPL code in core logic
- ❌ Proprietary dependencies
- ✅ Public domain contributions
- ✅ Permissive open-source licenses

---

## Quick Reference

```bash
# Development setup
git clone ~/.cursor/plugins/local/kestrel-repro
cd ~/.cursor/plugins/local/kestrel-repro
pip install -e .

# Make changes
git checkout -b feature/my-feature

# Test
pytest tests/unit/ -v
black --check scripts/
ruff check scripts/

# Commit
git commit -m "feat(scope): description"

# Push and create PR
git push -u origin feature/my-feature
```

---

## Questions?

- Open an issue for bugs or questions
- Check `docs/` for detailed documentation
- Review `CHANGELOG.md` for recent changes
