"""train.py — minimal PyTorch training script for the dl-paper-repro fixture.

Works with PyTorch if installed; falls back to a numpy-only deterministic
"loss" surrogate so the pipeline can be exercised end-to-end without
PyTorch.

Usage:
    python train.py --epochs 2 --seed 42

Outputs (relative to --output-dir):
    checkpoints/epoch_001.pth | epoch_001.json
    logs/train.log
    metrics/raw_metrics.json
"""
import argparse, json, os, random, sys
from pathlib import Path


def set_seed(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch  # type: ignore
        torch.manual_seed(seed)
    except ImportError:
        pass


def _has_torch() -> bool:
    try:
        import torch  # type: ignore
        return True
    except ImportError:
        return False


def build_model(input_dim: int = 4, output_dim: int = 3):
    if not _has_torch():
        return None
    import torch.nn as nn  # type: ignore
    return nn.Sequential(
        nn.Linear(input_dim, 8),
        nn.ReLU(),
        nn.Linear(8, output_dim),
    )


def synthetic_batch(batch_size: int = 4, input_dim: int = 4, output_dim: int = 3):
    """Build a synthetic batch. Returns (x, y) compatible with both torch and numpy."""
    if _has_torch():
        import torch  # type: ignore
        x = torch.randn(batch_size, input_dim)
        y = torch.randint(0, output_dim, (batch_size,))
        return x, y
    import numpy as np
    rng = np.random.default_rng(0)
    x = rng.standard_normal((batch_size, input_dim)).astype(np.float32)
    y = rng.integers(0, output_dim, size=(batch_size,))
    class _Arr:
        def __init__(self, a): self._a = a
        @property
        def shape(self): return self._a.shape
    return _Arr(x), _Arr(y)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--steps-per-epoch", type=int, default=5)
    parser.add_argument("--output-dir", default="experiments/fixture-run")
    args = parser.parse_args()

    set_seed(args.seed)
    out = Path(args.output_dir)
    (out / "checkpoints").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    (out / "metrics").mkdir(parents=True, exist_ok=True)

    model = build_model()
    if _has_torch():
        import torch  # type: ignore
        import torch.nn as nn  # type: ignore
        import torch.optim as optim  # type: ignore
        opt = optim.SGD(model.parameters(), lr=0.01)
        loss_fn = nn.CrossEntropyLoss()
    else:
        opt = loss_fn = None

    raw_metrics = []
    log_lines = []
    for epoch in range(1, args.epochs + 1):
        epoch_losses = []
        for step in range(1, args.steps_per_epoch + 1):
            x, y = synthetic_batch(args.batch_size)
            try:
                opt.zero_grad()
                logits = model(x)
                loss = loss_fn(logits, y)
                loss.backward()
                opt.step()
                loss_val = float(loss)
            except Exception:
                # numpy fallback
                import numpy as np
                loss_val = float(np.abs(x._a).mean()) * 0.1 + 0.01 * epoch
            epoch_losses.append(loss_val)
            log_lines.append(f"epoch={epoch} step={step} loss={loss_val:.4f}")
        ckpt_path = out / "checkpoints" / f"epoch_{epoch:03d}.pth"
        try:
            if _has_torch():
                torch.save({"epoch": epoch, "model_state_dict": model.state_dict()}, str(ckpt_path))
            else:
                ckpt_path = ckpt_path.with_suffix(".json")
                ckpt_path.write_text(json.dumps({"epoch": epoch, "kind": "numpy-fixture"}))
        except Exception:
            ckpt_path = ckpt_path.with_suffix(".json")
            ckpt_path.write_text(json.dumps({"epoch": epoch, "kind": "fallback"}))
        raw_metrics.append({"epoch": epoch, "mean_loss": sum(epoch_losses) / len(epoch_losses)})

    (out / "logs" / "train.log").write_text("\n".join(log_lines) + "\n")
    (out / "metrics" / "raw_metrics.json").write_text(json.dumps(raw_metrics, indent=2))
    print(f"[fixture-train] {args.epochs} epochs, final mean_loss={raw_metrics[-1]['mean_loss']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())