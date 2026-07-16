"""Small PointNet for golden test B.

Uses real torch.utils.data.Dataset with synthetic point clouds.
Included in fixtures/ directory for testing purposes only.
"""

import argparse, json, os, torch, torch.nn as nn, torch.nn.functional as F
from pathlib import Path
from torch.utils.data import DataLoader, Dataset


class RandomPointCloud(Dataset):
    """Tiny synthetic point cloud dataset for testing."""

    def __init__(self, n_samples=20, n_points=128, n_classes=3):
        self.n_samples = n_samples
        self.n_points = n_points
        self.n_classes = n_classes

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        points = torch.randn(self.n_points, 3)
        label = torch.randint(0, self.n_classes, (1,)).item()
        return points, label


class SimplePointNet(nn.Module):
    """Simplified PointNet for classification."""

    def __init__(self, n_classes=3):
        super().__init__()
        self.conv1 = nn.Conv1d(3, 64, 1)
        self.conv2 = nn.Conv1d(64, 128, 1)
        self.conv3 = nn.Conv1d(128, 256, 1)
        self.fc = nn.Linear(256, n_classes)

    def forward(self, x):
        # x: (B, N, 3) -> (B, 3, N)
        x = x.transpose(1, 2)
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = F.adaptive_max_pool1d(x, 1)
        x = x.squeeze(2)
        return self.fc(x)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="checkpoints")
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    ds = RandomPointCloud(n_samples=20, n_points=128, n_classes=3)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, num_workers=0)

    model = SimplePointNet(n_classes=3)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(args.epochs):
        total_loss = 0
        correct = 0
        total = 0
        for batch_idx, (points, labels) in enumerate(loader):
            logits = model(points)
            loss = criterion(logits, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            _, predicted = logits.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

        avg_loss = total_loss / len(loader)
        accuracy = correct / total if total > 0 else 0.0
        print(f"epoch {epoch}: avg_loss={avg_loss:.4f}, accuracy={accuracy:.4f}")

    model_path = Path(args.output_dir) / "pointnet.pt"
    torch.save(model.state_dict(), model_path)

    metrics = {
        "final_loss": avg_loss,
        "accuracy": accuracy,
        "epochs": args.epochs,
        "dataset_size": len(ds),
        "point_count": ds.n_points,
        "num_classes": ds.n_classes,
    }
    metrics_path = Path(args.output_dir) / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved: {model_path}, {metrics_path}")
    print(f"Final loss: {avg_loss:.4f}, Accuracy: {accuracy:.4f}")


if __name__ == "__main__":
    main()
