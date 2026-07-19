"""Allow ``python -m scripts.reproctl ...`` from any cwd.

The console script ``reproctl`` resolves to ``scripts.reproctl:main``.
Mirroring that entry point here makes the package itself executable
via ``python -m scripts.reproctl`` so tests and developers can invoke
the CLI without relying on PATH being set up.
"""

from scripts.reproctl import main

if __name__ == "__main__":
    raise SystemExit(main())
