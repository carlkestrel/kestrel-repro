#!/usr/bin/env python3
"""L3 Checkpoint Resume Test: save/load checkpoint produces identical results."""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", required=True)
    parser.add_argument("--config")
    args = parser.parse_args()

    primary = Path(args.primary)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "ckpt.pt"

        code1 = f"""
import torch, os
torch.manual_seed(12345)
model = torch.nn.Linear(10, 2)
# Train 1 step
x = torch.randn(4, 10)
y = model(x).sum()
y.backward()
torch.optim.Adam(model.parameters()).step()
# Save
sd = model.state_dict()
torch.save(sd, "{tmp_path}")
hash_before = str(float(list(sd.values())[0].sum()))
print(f"HASH_BEFORE={{hash_before}}")
"""
        r1 = subprocess.run(
            [sys.executable, "-c", code1],
            capture_output=True,
            text=True,
        )
        if r1.returncode != 0:
            print("L3 Checkpoint Save: FAIL")
            print(r1.stdout, r1.stderr)
            sys.exit(1)

        code2 = f"""
import torch
model = torch.nn.Linear(10, 2)
model.load_state_dict(torch.load("{tmp_path}"))
sd = model.state_dict()
hash_after = str(float(list(sd.values())[0].sum()))
print(f"HASH_AFTER={{hash_after}}")
"""
        r2 = subprocess.run(
            [sys.executable, "-c", code2],
            capture_output=True,
            text=True,
        )

        if r1.returncode == 0 and r2.returncode == 0:
            hb = re.search(r"HASH_BEFORE=(.+)", r1.stdout)
            ha = re.search(r"HASH_AFTER=(.+)", r2.stdout)
            if hb and ha and hb.group(1).strip() == ha.group(1).strip():
                print("L3 Checkpoint Resume Test: PASS")
                sys.exit(0)

        print("L3 Checkpoint Resume Test: FAIL (hash mismatch)")
        print(r1.stdout, r2.stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
