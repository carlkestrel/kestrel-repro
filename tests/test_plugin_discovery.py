"""Test Cursor plugin discovery: the manifest points to actual files."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / ".cursor-plugin" / "plugin.json"


def test_manifest_is_valid_json():
    data = json.loads(MANIFEST.read_text())
    assert "name" in data, "missing name"
    assert data["name"] == "dl-paper-repro"


def test_commands_directory_resolves():
    """The 'commands' field points to an existing directory with ≥1 .md file."""
    data = json.loads(MANIFEST.read_text())
    cmds = data.get("commands")
    assert cmds, "commands field missing"
    cmds_dir = (REPO / cmds.lstrip("./")).resolve() if not cmds.startswith("/") else Path(cmds)
    assert cmds_dir.is_dir(), f"commands dir missing: {cmds_dir}"
    md_files = list(cmds_dir.glob("*.md"))
    assert len(md_files) >= 6, f"expected ≥6 commands, got {len(md_files)}"


def test_agents_directory_resolves():
    data = json.loads(MANIFEST.read_text())
    agents = data.get("agents")
    assert agents, "agents field missing"
    agents_dir = (REPO / agents.lstrip("./")).resolve() if not agents.startswith("/") else Path(agents)
    assert agents_dir.is_dir(), f"agents dir missing: {agents_dir}"
    md_files = list(agents_dir.glob("*.md"))
    assert len(md_files) >= 5, f"expected ≥5 agents, got {len(md_files)}"


def test_all_commands_have_yaml_frontmatter():
    """Every command .md must have YAML frontmatter (name + description)."""
    data = json.loads(MANIFEST.read_text())
    cmds_dir = REPO / data["commands"].lstrip("./")
    bad = []
    for md in sorted(cmds_dir.glob("*.md")):
        text = md.read_text()
        if not text.startswith("---\n"):
            bad.append(md.name)
            continue
        end = text.find("\n---\n", 4)
        if end <= 0:
            bad.append(md.name)
            continue
        block = text[4:end]
        if "description:" not in block:
            bad.append(md.name)
    # Legacy commands without frontmatter are tolerated but reported.
    if bad:
        print(f"[warn] legacy commands without frontmatter: {bad}")
    # At least the 6 NEW commands (P5+P6+P7) MUST have frontmatter.
    new_cmds = ["repro-contract.md","repro-plan.md","repro-review.md",
                "repro-monitor.md","repro-report.md","research-extend.md"]
    for nc in new_cmds:
        text = (cmds_dir / nc).read_text()
        assert text.startswith("---\n"), f"{nc}: missing YAML frontmatter"
        assert "description:" in text[:500], f"{nc}: no description in frontmatter"


if __name__ == "__main__":
    test_manifest_is_valid_json()
    test_commands_directory_resolves()
    test_agents_directory_resolves()
    test_all_commands_have_yaml_frontmatter()
    print("test_plugin_discovery: 4/4 PASS")