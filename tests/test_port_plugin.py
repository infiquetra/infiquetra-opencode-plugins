"""Tests for the mechanical port transforms."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import port_plugin as pp


def test_split_frontmatter_plain() -> None:
    fields, body = pp.split_frontmatter("---\nname: x\ndescription: hello\n---\nBody")
    assert fields == {"name": "x", "description": "hello"}
    assert body == "Body"


def test_split_frontmatter_block_scalar() -> None:
    text = "---\ndescription: |\n  First line\n  Second line\nmodel: haiku\n---\nBody"
    fields, body = pp.split_frontmatter(text)
    assert fields["description"] == "First line\nSecond line\n"
    assert fields["model"] == "haiku"
    assert body == "Body"


def test_load_reference_rewrite() -> None:
    body, rewrites = pp.rewrite_load_references("Load `saga/skills/brainstorm/SKILL.md`. Then act.")
    assert "`brainstorm` skill" in body
    assert "instructions. Then act" in body
    assert "LoadReference->skill-tool:brainstorm" in rewrites


def test_plugin_root_rewrites_paths() -> None:
    body, rewrites = pp.plugin_root_rewrites(
        "Run `python3 plugins/saga/scripts/saga.py scan`. Read `saga/references/x.md`."
        "See `saga/skills/handoff/SKILL.md` and ../../references/formatting-style.md"
        " and ../../loop/ dispatch-table.md.",
        "saga",
    )
    assert "python3 ${SAGA_PLUGIN_ROOT}/scripts/saga.py" in body
    assert "Read ${SAGA_PLUGIN_ROOT}/references/x.md" in body
    assert "`handoff` skill" in body
    assert "${SAGA_PLUGIN_ROOT}/references/formatting-style.md" in body
    assert "${SAGA_PLUGIN_ROOT}/skills/loop/ dispatch-table.md" in body
    assert "PluginRootPath->env:SAGA_PLUGIN_ROOT/scripts" in rewrites
    assert "SkillRef->name:handoff" in rewrites


def test_plugin_root_rewrites_tool_names() -> None:
    body, rewrites = pp.plugin_root_rewrites("Call `ToolSearch` and use `WebSearch`.", "saga")
    assert "`question`" in body
    assert "`websearch`" in body
    assert "ToolSearch->question" in rewrites


def test_agent_transform(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    (source / "agents").mkdir(parents=True)
    (dest / "agents").mkdir(parents=True)
    (source / "agents" / "executor.md").write_text(
        "---\nname: executor\ndescription: Cheap executor.\nmodel: haiku\ntools: Bash\n"
        "---\nRun one op."
    )
    agents = pp.port_agents(source, dest)
    assert agents[0]["name"] == "executor"
    assert agents[0]["mapped_model"] == "anthropic/claude-haiku-4-6"
    out = (dest / "agents" / "executor.md").read_text()
    assert "mode: subagent" in out
    assert "bash: allow" in out
    assert "read: deny" in out
    assert "Run one op." in out


def test_agent_unknown_tier_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    (source / "agents").mkdir(parents=True)
    (dest / "agents").mkdir(parents=True)
    (source / "agents" / "bad.md").write_text(
        "---\nname: bad\ndescription: x\nmodel: mystery\n---\nBody"
    )
    try:
        pp.port_agents(source, dest)
        raise AssertionError("expected ValueError for unknown model tier")
    except ValueError as error:
        assert "mystery" in str(error)


def test_command_transform(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    (source / "commands").mkdir(parents=True)
    (dest / "commands").mkdir(parents=True)
    (source / "commands" / "brainstorm.md").write_text(
        '---\nname: brainstorm\ndescription: Deep dive\nargument-hint: "[topic]"\n---\n'
        "Load `saga/skills/brainstorm/SKILL.md`. Use $ARGUMENTS.\n"
    )
    commands = pp.port_commands(source, dest, "saga")
    assert commands[0]["name"] == "brainstorm"
    out = (dest / "commands" / "brainstorm.md").read_text()
    assert "Deep dive Arguments: [topic]" in out
    assert "`brainstorm` skill" in out
    assert "$ARGUMENTS" in out
    assert "name:" not in out.split("---")[1]


def test_skill_description_truncation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    (source / "skills" / "long").mkdir(parents=True)
    long_description = "word " * 400  # 2000 chars, > 1024
    (source / "skills" / "long" / "SKILL.md").write_text(
        f"---\nname: long\ndescription: {long_description}\n---\nBody"
    )
    skills = pp.port_skills(source, dest, "saga")
    assert "DescriptionTruncated:" in str(skills[0]["rewrites"])
    fields, _ = pp.split_frontmatter((dest / "skills" / "long" / "SKILL.md").read_text())
    assert len(str(fields["description"])) <= 1024
