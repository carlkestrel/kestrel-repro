"""Tiny PyTorch training for golden test A."""

import argparse, json, os, sys, torch, torch.nn as nn, torch.optim as optim
from pathlib import Path


class TinyNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(10, 2)

    def forward(self, x):
        return self.fc(x)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="checkpoints")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    model = TinyNet()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    X = torch.randn(100, 10)
    y = torch.randn(100, 2)
    losses = []

    for epoch in range(args.epochs):
        optimizer.zero_grad()
        out = model(X)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()
        losses.append(loss.item())
        print(f"epoch {epoch}: loss={loss.item():.4f}")

    # Save model
    model_path = Path(args.output_dir) / "model.pt"
    torch.save(model.state_dict(), model_path)

    # Save metrics
    metrics = {
        "final_loss": float(losses[-1]),
        "epochs": args.epochs,
        "seed": args.seed,
        "losses": [float(l) for l in losses],
    }
    metrics_path = Path(args.output_dir) / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved: {model_path}, {metrics_path}")
    print(f"Final loss: {losses[-1]:.4f}")


if __name__ == "__main__":
    main()
