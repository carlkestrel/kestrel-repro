"""Generate synthetic test data for golden_pointcloud_B fixture."""

import json, struct, torch
from pathlib import Path


def generate_point_cloud(n_points: int = 128, n_classes: int = 3) -> tuple[bytes, int]:
    """Generate a synthetic point cloud sample as binary format.

    Returns:
        Binary data: (n_points * 3 * 4 bytes float32) + (1 * 4 bytes int32 label)
        Label: integer class index
    """
    points = torch.randn(n_points, 3)
    label = torch.randint(0, n_classes, (1,)).item()

    buf = bytearray()
    for p in points:
        for coord in p:
            buf.extend(struct.pack("f", coord.item()))
    buf.extend(struct.pack("i", label))
    return bytes(buf), label


def main():
    out_dir = Path(__file__).parent / "test_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata = []
    for i in range(10):
        pc_bytes, label = generate_point_cloud(n_points=128, n_classes=3)
        filepath = out_dir / f"sample_{i:03d}.bin"
        filepath.write_bytes(pc_bytes)
        metadata.append({"filename": filepath.name, "label": label, "n_points": 128})
        print(f"Generated: {filepath} (label={label})")

    meta_path = out_dir / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved to {meta_path}")


if __name__ == "__main__":
    main()
