"""Plan validation: frontmatter, task-graph integrity, missing acceptance."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

EXIT_INVALID_PLAN = 5

_FRONT_MATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*(?:\n|$)", re.DOTALL
)


def _split_front_matter(text: str) -> tuple[dict, str]:
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text = m.group("fm")
    body = text[m.end():]
    if yaml is not None:
        try:
            data = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError as e:
            print(f"[startup] plan frontmatter YAML error: {e}", file=sys.stderr)
            sys.exit(EXIT_INVALID_PLAN)
    else:
        try:
            data = _mini_yaml(fm_text)
        except ValueError as e:
            print(f"[startup] plan frontmatter parse error: {e}",
                  file=sys.stderr)
            sys.exit(EXIT_INVALID_PLAN)
    if not isinstance(data, dict):
        print("[startup] plan frontmatter must be a YAML mapping", file=sys.stderr)
        sys.exit(EXIT_INVALID_PLAN)
    return data, body


def _mini_yaml(text: str) -> dict:
    out: dict = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"unparsable plan line: {line!r}")
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.lower() in ("true", "false"):
            out[k] = (v.lower() == "true")
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


def _detect_cycles(tasks: list[dict]) -> bool:
    """Return True if the dependency graph has any cycle."""
    by_id = {t.get("id"): t for t in tasks}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in by_id}

    def visit(node: str) -> bool:
        color[node] = GRAY
        deps = by_id.get(node, {}).get("depends_on", []) or []
        for d in deps:
            if d not in color:
                # Unknown dep is a hard error — treat as cycle-equivalent
                return True
            if color[d] == GRAY:
                return True
            if color[d] == WHITE and visit(d):
                return True
        color[node] = BLACK
        return False

    for tid in by_id:
        if color[tid] == WHITE and visit(tid):
            return True
    return False


def _missing_acceptance(tasks: list[dict]) -> list[str]:
    bad = []
    for t in tasks:
        tid = t.get("id")
        if not tid:
            continue
        acc = t.get("acceptance")
        if acc is None:
            bad.append(tid)
            continue
        if isinstance(acc, list) and len(acc) == 0:
            bad.append(tid)
        if isinstance(acc, str) and not acc.strip():
            bad.append(tid)
    return bad


def validate(plan_path: Path) -> str:
    """Validate the plan and return its SHA-256 hash.

    Exits with code 5 on any structural failure.
    """
    if not plan_path.exists():
        print(f"[startup] plan not found: {plan_path}", file=sys.stderr)
        sys.exit(EXIT_INVALID_PLAN)
    text = plan_path.read_text(encoding="utf-8")
    fm, body = _split_front_matter(text)
    if not fm:
        print("[startup] plan missing YAML frontmatter (--- ... ---)",
              file=sys.stderr)
        sys.exit(EXIT_INVALID_PLAN)
    if "name" not in fm or not str(fm.get("name", "")).strip():
        print("[startup] plan frontmatter requires a non-empty `name`",
              file=sys.stderr)
        sys.exit(EXIT_INVALID_PLAN)

    tasks = fm.get("tasks") or []
    if not isinstance(tasks, list):
        print("[startup] plan frontmatter `tasks` must be a list",
              file=sys.stderr)
        sys.exit(EXIT_INVALID_PLAN)

    if _detect_cycles(tasks):
        print("[startup] plan task graph has a cycle", file=sys.stderr)
        sys.exit(EXIT_INVALID_PLAN)

    miss = _missing_acceptance(tasks)
    if miss:
        print(
            f"[startup] plan tasks missing acceptance criteria: {miss}",
            file=sys.stderr,
        )
        sys.exit(EXIT_INVALID_PLAN)

    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return h
