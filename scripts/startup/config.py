"""Configuration priority resolver.

Highest priority first:
  1. CLI flags
  2. ``<PROJECT>/.repro/config.yaml``
  3. ``<PROJECT>/repro.yaml``
  4. plugin defaults (built-in)
  5. auto-detection

Env vars (lower than CLI but above YAML):
  REPRO_PROJECT_ROOT, REPRO_PLAN_PATH, REPRO_MODE, REPRO_CONFIG, REPRO_LOG_LEVEL

Never hard-codes user paths.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover — tests use only dict-shaped YAML
    yaml = None

DEFAULTS: dict[str, Any] = {
    "mode": "strict",
    "log_level": "INFO",
    "expected_cuda": "",
    "auto_proceed": False,
    "human_checkpoint": True,
}

YAML_CANDIDATES: tuple[str, ...] = (
    ".repro/config.yaml",
    "repro.yaml",
)

EXIT_BAD_CONFIG = 2


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            print(f"[startup] config parse error in {path}: {e}", file=sys.stderr)
            sys.exit(EXIT_BAD_CONFIG)
        if not isinstance(data, dict):
            print(
                f"[startup] config {path} must be a YAML mapping, got {type(data).__name__}",
                file=sys.stderr,
            )
            sys.exit(EXIT_BAD_CONFIG)
        return data
    # Fallback: minimal YAML loader for the very small subset we use
    return _mini_yaml(text)


def _mini_yaml(text: str) -> dict:
    """Parse the subset of YAML we actually use:
    ``key: value`` pairs where value is a string or number.
    """
    out: dict = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"unparsable config line: {line!r}")
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.lower() in ("true", "false"):
            out[k] = v.lower() == "true"
        elif v.lower() in ("null", "~", ""):
            out[k] = None
        else:
            try:
                out[k] = int(v)
            except ValueError:
                try:
                    out[k] = float(v)
                except ValueError:
                    out[k] = v
    return out


def resolve(*, project_root: Path, plan_path: Path, cli: dict | None = None) -> dict:
    """Build the merged configuration.

    Priority order: cli > env > yaml (project-local) > defaults.
    """
    cli = dict(cli or {})
    cfg: dict = dict(DEFAULTS)

    # 3+4: yaml files
    for rel in YAML_CANDIDATES:
        cfg.update(_load_yaml(project_root / rel))

    # 2: env overrides
    env_map = {
        "REPRO_MODE": "mode",
        "REPRO_LOG_LEVEL": "log_level",
        "REPRO_CONFIG": "_config_path",
    }
    for k, target in env_map.items():
        v = os.environ.get(k)
        if v:
            cfg[target] = v

    # 1: CLI overrides everything
    for k, v in cli.items():
        if v not in (None, ""):
            cfg[k] = v

    # 5: auto-detection
    if "expected_cuda" in cli and cli["expected_cuda"]:
        cfg["expected_cuda"] = cli["expected_cuda"]

    # If REPRO_CONFIG points at a file, merge it on top of yaml but under cli
    cfg_path = cfg.pop("_config_path", None)
    if cfg_path:
        cfg.update(_load_yaml(Path(cfg_path)))

    cfg["project_root"] = str(project_root)
    cfg["plan_path"] = str(plan_path)
    return cfg
