"""Tests for the plugin validator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import validate_opencode_plugins as validator


def test_validate_current_repo(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "REPO_ROOT", Path(__file__).resolve().parent.parent)
    monkeypatch.setattr(sys, "argv", ["validate_opencode_plugins.py"])
    assert validator.main() == 0


def test_manifest_validation(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    violations = validator.Violations()

    # Missing manifest
    assert validator.check_manifest(plugin_dir, violations) == {}
    assert any("missing manifest.json" in err for err in violations.errors)

    # Invalid JSON
    violations.errors.clear()
    (plugin_dir / "manifest.json").write_text("{invalid json")
    assert validator.check_manifest(plugin_dir, violations) == {}
    assert any("not valid JSON" in err for err in violations.errors)

    # Schema & lineage checks
    violations.errors.clear()
    (plugin_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "wrong-schema",
                "version": "1.0.0",
                "lineage": {"source_repo": "repo"},
            }
        )
    )
    validator.check_manifest(plugin_dir, violations)
    assert any("manifest schema is not" in err for err in violations.errors)
    assert any("manifest version missing or malformed" in err for err in violations.errors)
    assert any("manifest lineage missing source_commit" in err for err in violations.errors)
    assert any("manifest missing inventory" in err for err in violations.errors)


def test_skill_validation(tmp_path: Path) -> None:
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    violations = validator.Violations()

    # Missing SKILL.md
    validator.check_skill(skill_dir, violations)
    assert any("missing SKILL.md" in err for err in violations.errors)

    # Name mismatch and bad characters
    violations.errors.clear()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Other_Name\ndescription: A valid description.\n---\nBody"
    )
    validator.check_skill(skill_dir, violations)
    assert any("does not match folder" in err for err in violations.errors)
    assert any("not lowercase kebab-case" in err for err in violations.errors)

    # Missing description
    violations.errors.clear()
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: ''\n---\nBody")
    validator.check_skill(skill_dir, violations)
    assert any("description missing or out of 1-1024 chars" in err for err in violations.errors)

    # Overly long description (>1024)
    violations.errors.clear()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: my-skill\ndescription: {'x' * 1025}\n---\nBody"
    )
    validator.check_skill(skill_dir, violations)
    assert any("description missing or out of 1-1024 chars" in err for err in violations.errors)


def test_command_validation(tmp_path: Path) -> None:
    cmd_file = tmp_path / "test-cmd.md"
    violations = validator.Violations()

    # Missing description
    cmd_file.write_text("---\n---\nSome body")
    validator.check_command(cmd_file, violations)
    assert any("missing description" in err for err in violations.errors)

    # Empty body
    violations.errors.clear()
    cmd_file.write_text("---\ndescription: Has description\n---\n   \n")
    validator.check_command(cmd_file, violations)
    assert any("body is empty" in err for err in violations.errors)


def test_agent_validation(tmp_path: Path) -> None:
    agent_file = tmp_path / "test-agent.md"
    violations = validator.Violations()

    # Missing description & invalid mode
    agent_file.write_text("---\nmode: invalid-mode\n---\nAgent instructions")
    validator.check_agent(agent_file, violations)
    assert any("missing description" in err for err in violations.errors)
    assert any("missing valid mode" in err for err in violations.errors)

    # Valid agent
    violations.errors.clear()
    agent_file.write_text("---\ndescription: Valid agent\nmode: subagent\n---\nAgent instructions")
    validator.check_agent(agent_file, violations)
    assert violations.errors == []


def test_hook_bridge_validation(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "test-plugin"
    opencode_dir = plugin_dir / "opencode"
    opencode_dir.mkdir(parents=True)
    bridge_file = opencode_dir / "test-hooks.ts"
    bridge_file.write_text('const DEFERRED_HOOKS = ["hook1.py", "hook2.py"]\n')

    violations = validator.Violations()
    manifest: dict[str, Any] = {
        "inventory": {"hook_bridges": ["test-hooks.ts"]},
        "hooks": {"deferred": ["hook1.py"]},
    }
    validator.check_hook_bridges(plugin_dir, manifest, violations)
    assert any("DEFERRED_HOOKS" in err for err in violations.errors)

    # Agreeing deferred lists
    violations.errors.clear()
    manifest["hooks"]["deferred"] = ["hook1.py", "hook2.py"]
    validator.check_hook_bridges(plugin_dir, manifest, violations)
    assert violations.errors == []


def test_inventory_without_skills_dir(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    violations = validator.Violations()
    manifest: dict[str, Any] = {
        "inventory": {
            "skills": [],
            "commands": [],
            "agents": [],
        }
    }
    validator.check_inventory(plugin_dir, manifest, violations)
    assert violations.errors == []


def test_leak_detection(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "test-plugin"
    (plugin_dir / "__pycache__").mkdir(parents=True)
    (plugin_dir / ".venv").mkdir(parents=True)
    violations = validator.Violations()
    validator.check_leaks(plugin_dir, violations)
    assert any("leaked __pycache__" in err for err in violations.errors)
    assert any("leaked .venv" in err for err in violations.errors)
