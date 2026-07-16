"""conftest.py — pytest hook: set up sys.path before test imports."""

import sys
from pathlib import Path

# conftest.py lives in <project>/tests/conftest.py
# parent = tests/, parent.parent = project root
CONFTEST = Path(__file__)
PROJECT_ROOT = CONFTEST.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
