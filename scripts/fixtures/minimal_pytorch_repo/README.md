# Minimal PyTorch Repository Fixture

> A 4-row synthetic dataset + 2-layer Linear model, for end-to-end testing
> the dl-paper-repro pipeline without real datasets.

## Layout

```
fixtures/minimal_pytorch_repo/
├── README.md
└── train.py                # 50 LOC; 2-layer MLP on synthetic batch
```

## What it produces

```
experiments/fixture-run/
├── checkpoints/epoch_001.pth
├── checkpoints/epoch_002.pth
├── logs/train.log
└── metrics/raw_metrics.json
```

## Usage in tests

```python
import subprocess
subprocess.run(["python", "fixtures/minimal_pytorch_repo/train.py",
                "--epochs", "2", "--seed", "42",
                "--output-dir", "/tmp/fixture-run"], check=True)
```

The fixture is intentionally tiny so that the test runs in <2 s on a
laptop. It does **not** reproduce any real paper — it exists only to
exercise the *pipeline* end-to-end.