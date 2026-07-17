"""
VAL-010 REPOSITORY_INVENTORY — Scan all source, config, test, CLI and Cursor files.
Generate repository_inventory.json with counts and line counts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def count_lines(path):
    try:
        return len(path.read_text(errors="ignore").splitlines())
    except Exception:
        return 0


def is_valid_json(path):
    try:
        json.loads(path.read_text())
        return True
    except Exception:
        return False


EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".tox", "build", "dist",
}


def run(project_root=None):
    project = (Path(project_root) if project_root else Path.cwd()).resolve()
    audit_dir = project / ".repro" / "audit"

    inventory = {
        "audit_id": _get_audit_id(audit_dir),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project),
    }

    # Python files
    py_files = []
    for p in sorted(project.rglob("*.py")):
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        if p.name.endswith(".pyc"):
            continue
        rel = str(p.relative_to(project))
        py_files.append({"path": rel, "lines": count_lines(p), "size": p.stat().st_size})
    inventory["python_files"] = py_files
    inventory["python_file_count"] = len(py_files)
    inventory["python_line_count"] = sum(f["lines"] for f in py_files)

    # Config files
    cfg_patterns = ["*.yaml", "*.yml", "*.json", "*.toml", "*.ini", "*.cfg"]
    cfg_files = []
    for pat in cfg_patterns:
        for p in sorted(project.rglob(pat)):
            if any(ex in p.parts for ex in EXCLUDE_DIRS):
                continue
            cfg_files.append({
                "path": str(p.relative_to(project)),
                "type": p.suffix.lstrip("."),
                "lines": count_lines(p),
                "valid": is_valid_json(p) if p.suffix == ".json" else None,
            })
    inventory["config_files"] = cfg_files
    inventory["config_file_count"] = len(cfg_files)

    # Shell scripts
    sh_files = []
    for p in sorted(project.rglob("*.sh")):
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        sh_files.append({"path": str(p.relative_to(project)), "lines": count_lines(p)})
    inventory["shell_scripts"] = sh_files
    inventory["shell_script_count"] = len(sh_files)

    # Markdown files
    md_files = []
    for p in sorted(project.rglob("*.md")):
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        md_files.append({"path": str(p.relative_to(project)), "lines": count_lines(p)})
    inventory["markdown_files"] = md_files
    inventory["markdown_file_count"] = len(md_files)

    # Cursor commands
    cmd_dir = project / "commands"
    cursor_cmds = []
    if cmd_dir.exists():
        for p in sorted(cmd_dir.glob("*.md")):
            cursor_cmds.append({"path": str(p.relative_to(project)), "name": p.stem,
                                 "lines": count_lines(p)})
    inventory["cursor_commands"] = cursor_cmds
    inventory["cursor_command_count"] = len(cursor_cmds)

    # Test files
    test_dir = project / "tests"
    test_files = []
    if test_dir.exists():
        for p in sorted(test_dir.rglob("test_*.py")):
            test_files.append({"path": str(p.relative_to(project)), "lines": count_lines(p)})
    inventory["test_files"] = test_files
    inventory["test_file_count"] = len(test_files)

    # Schemas
    schema_dir = project / "schemas"
    schemas = []
    if schema_dir.exists():
        for p in sorted(schema_dir.glob("*.json")):
            schemas.append({"path": str(p.relative_to(project)),
                            "valid": is_valid_json(p), "lines": count_lines(p)})
    inventory["schemas"] = schemas
    inventory["schema_count"] = len(schemas)

    # Totals
    inventory["total_files"] = (
        inventory["python_file_count"]
        + inventory["config_file_count"]
        + inventory["shell_script_count"]
        + inventory["markdown_file_count"]
        + inventory["cursor_command_count"]
        + inventory["test_file_count"]
    )
    inventory["total_lines"] = (
        inventory["python_line_count"]
        + sum(f["lines"] for f in cfg_files)
        + sum(f["lines"] for f in sh_files)
        + sum(f["lines"] for f in md_files)
    )

    inventory["total_lines"] = int(inventory["total_lines"])

    path = audit_dir / "repository_inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")

    _write_node_state(audit_dir, "VAL-010", "PASSED", [str(path)])

    return {
        "status": "PASSED",
        "inventory": str(path),
        "python_file_count": inventory["python_file_count"],
        "python_line_count": inventory["python_line_count"],
        "total_files": inventory["total_files"],
        "total_lines": inventory["total_lines"],
        "test_file_count": inventory["test_file_count"],
        "cursor_command_count": inventory["cursor_command_count"],
        "schema_count": inventory["schema_count"],
        "evidence_files": [str(path)],
    }


def _get_audit_id(audit_dir):
    m = audit_dir / "audit_manifest.json"
    if m.exists():
        return json.loads(m.read_text()).get("audit_id", "unknown")
    return "unknown"


def _write_node_state(audit_dir, node_id, status, evidence):
    node_dir = audit_dir / "nodes"
    node_dir.mkdir(parents=True, exist_ok=True)
    (node_dir / f"{node_id}.json").write_text(json.dumps({
        "node_id": node_id,
        "status": status,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "evidence_files": evidence,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys
    result = run()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "PASSED" else 1)
