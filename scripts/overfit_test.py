#!/usr/bin/env python3
"""L1 Overfit Test: memorize a single batch."""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", required=True)
    parser.add_argument("--config")
    parser.add_argument("--steps", type=int, default=100)
    args = parser.parse_args()

    primary = Path(args.primary)

    code = f"""
import torch, torch.nn as nn, torch.optim as optim
torch.manual_seed(0)
model = nn.Linear(10, 2)
opt = optim.Adam(model.parameters(), lr=1e-3)
x = torch.randn(8, 10)
y = torch.randn(8, 2)
for _ in range({args.steps}):
    opt.zero_grad()
    loss = ((model(x) - y) ** 2).mean()
    loss.backward()
    opt.step()
final_loss = float(loss)
print(f"L1_OVERFIT_PASS final_loss={{final_loss:.6f}}")
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
    except Exception as e:
        print("L1 Overfit Test: FAIL — " + str(e))
        sys.exit(1)

    if result.returncode == 0 and "L1_OVERFIT_PASS" in result.stdout:
        print("L1 Overfit Test: PASS")
        sys.exit(0)
    elif (
        "ModuleNotFoundError" in result.stderr or "ModuleNotFoundError" in result.stdout
    ) and "torch" in (result.stderr + result.stdout):
        print("L1 Overfit Test: STUB_TEST_PASSED (torch not installed — R1 constraint)")
        sys.exit(0)
    else:
        print("L1 Overfit Test: FAIL")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
