#!/usr/bin/env python3
"""Validate the Infiquetra opencode plugin adapter repo.

Checks every ported plugin against its ``manifest.json`` contract and the
opencode surface shape rules:

- manifest schema, semver version, lineage pin present;
- inventory lists match the filesystem exactly;
- every skill: ``SKILL.md`` exists, frontmatter ``name`` matches the folder,
  ``description`` present and 1-1024 chars;
- every command: frontmatter ``description`` present, body non-empty;
- every agent: frontmatter ``description`` and ``mode`` present;
- skill names unique across all ported plugins (opencode installs them flat);
- hook bridges declared in the manifest exist on disk and declare the same
  deferred-hook set as the manifest;
- no leaked source artifacts (``__pycache__``, ``.venv``, ``.claude-plugin``).

Exit code 0 = valid, 1 = violations found.
"""

from __future__ import annotations

import json
import re
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER_SUFFIX_RE = re.compile(r"^\d+\.\d+\.\d+\+opencode\.\d{14}$")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
DEFERRED_MARKER = "DEFERRED_HOOKS"


class Violations:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def add(self, message: str) -> None:
        self.errors.append(message)

    def report(self) -> int:
        if not self.errors:
            print("valid: all ported plugins pass")
            return 0
        for error in self.errors:
            print(f"  ERROR: {error}", file=sys.stderr)
        print(f"{len(self.errors)} violations", file=sys.stderr)
        return 1


def load_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields = yaml.safe_load(match.group(1)) or {}
    return dict(fields) if isinstance(fields, dict) else {}


def check_manifest(plugin: Path, violations: Violations) -> dict[str, Any]:
    manifest_path = plugin / "manifest.json"
    if not manifest_path.exists():
        violations.add(f"{plugin.name}: missing manifest.json")
        return {}
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as error:
        violations.add(f"{plugin.name}: manifest.json is not valid JSON: {error}")
        return {}
    if manifest.get("schema") != "opencode-plugin-port.v1":
        violations.add(f"{plugin.name}: manifest schema is not opencode-plugin-port.v1")
    if not SEMVER_SUFFIX_RE.match(str(manifest.get("version", ""))):
        violations.add(f"{plugin.name}: manifest version missing or malformed")
    lineage = manifest.get("lineage") or {}
    for field in ("source_repo", "source_commit", "source_version", "ported_at"):
        if not lineage.get(field):
            violations.add(f"{plugin.name}: manifest lineage missing {field}")
    if not manifest.get("inventory"):
        violations.add(f"{plugin.name}: manifest missing inventory")
    return dict(manifest)


def check_skill(skill_dir: Path, violations: Violations) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        violations.add(f"{skill_dir}: missing SKILL.md")
        return
    fields = load_frontmatter(skill_md.read_text())
    name = fields.get("name")
    if name != skill_dir.name:
        violations.add(
            f"{skill_dir}: SKILL.md name {name!r} does not match folder {skill_dir.name!r}"
        )
    if name and not SKILL_NAME_RE.match(str(name)):
        violations.add(f"{skill_dir}: skill name {name!r} is not lowercase kebab-case")
    description = fields.get("description")
    if not description or not (1 <= len(str(description)) <= 1024):
        violations.add(f"{skill_dir}: SKILL.md description missing or out of 1-1024 chars")


def check_command(command_file: Path, violations: Violations) -> None:
    text = command_file.read_text()
    fields = load_frontmatter(text)
    if not fields.get("description"):
        violations.add(f"{command_file}: command frontmatter missing description")
    body = FRONTMATTER_RE.sub("", text).strip()
    if not body:
        violations.add(f"{command_file}: command body is empty")


def check_agent(agent_file: Path, violations: Violations) -> None:
    fields = load_frontmatter(agent_file.read_text())
    if not fields.get("description"):
        violations.add(f"{agent_file}: agent frontmatter missing description")
    if fields.get("mode") not in ("primary", "subagent", "all"):
        violations.add(f"{agent_file}: agent frontmatter missing valid mode")


def check_hook_bridges(plugin: Path, manifest: dict[str, Any], violations: Violations) -> None:
    opencode_dir = plugin / "opencode"
    bridge_files = list(opencode_dir.glob("*.ts")) + list(opencode_dir.glob("*.js"))
    declared = manifest.get("inventory", {}).get("hook_bridges", [])
    if not bridge_files and not declared:
        return
    actual = {bridge.name for bridge in bridge_files}
    missing = set(declared) - actual
    undeclared = actual - set(declared)
    if missing:
        violations.add(f"{plugin.name}: manifest declares missing hook bridges {sorted(missing)}")
    if undeclared:
        violations.add(
            f"{plugin.name}: hook bridges on disk not declared in manifest {sorted(undeclared)}"
        )
    hooks = manifest.get("hooks", {})
    for bridge in bridge_files:
        text = bridge.read_text()
        match = re.search(rf"{DEFERRED_MARKER}\s*=\s*\[(.*?)\]", text, re.DOTALL)
        bridge_deferred = set()
        if match:
            bridge_deferred = set(re.findall(r'"([^"]+)"', match.group(1)))
        manifest_deferred = set(hooks.get("deferred", []))
        if bridge_deferred != manifest_deferred:
            violations.add(
                f"{plugin.name}: {bridge.name} DEFERRED_HOOKS {sorted(bridge_deferred)} "
                f"do not match manifest {sorted(manifest_deferred)}"
            )


def check_inventory(plugin: Path, manifest: dict[str, Any], violations: Violations) -> None:
    inventory = manifest.get("inventory", {})
    actual_skills = sorted(
        skill.name for skill in (plugin / "skills").iterdir() if (skill / "SKILL.md").is_file()
    )
    declared_skills = sorted(inventory.get("skills", []))
    if actual_skills != declared_skills:
        violations.add(
            f"{plugin.name}: skills on disk {actual_skills} != manifest {declared_skills}"
        )
    actual_commands = sorted(command.stem for command in (plugin / "commands").glob("*.md"))
    declared_commands = sorted(inventory.get("commands", []))
    if actual_commands != declared_commands:
        violations.add(
            f"{plugin.name}: commands on disk {actual_commands} != manifest {declared_commands}"
        )
    actual_agents = sorted(agent.stem for agent in (plugin / "agents").glob("*.md"))
    declared_agents = sorted(inventory.get("agents", []))
    if actual_agents != declared_agents:
        violations.add(
            f"{plugin.name}: agents on disk {actual_agents} != manifest {declared_agents}"
        )


def check_leaks(plugin: Path, violations: Violations) -> None:
    for leaked in plugin.rglob("__pycache__"):
        violations.add(f"{plugin.name}: leaked {leaked.relative_to(plugin)}")
    for name in (".venv", "venv", ".claude-plugin", ".pytest_cache"):
        if (plugin / name).exists():
            violations.add(f"{plugin.name}: leaked {name}")


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", action="append", default=[], help="validate one plugin only")
    args = parser.parse_args()

    plugins_dir = REPO_ROOT / "plugins"
    if not plugins_dir.is_dir():
        raise SystemExit(f"no plugins directory at {plugins_dir}")

    violations = Violations()
    seen_skill_names: dict[str, str] = {}

    plugins = sorted(plugins_dir.iterdir())
    for plugin in plugins:
        if not (plugin / "manifest.json").is_file():
            continue
        if args.plugin and plugin.name not in args.plugin:
            continue
        manifest = check_manifest(plugin, violations)
        if not manifest:
            continue
        check_inventory(plugin, manifest, violations)
        check_hook_bridges(plugin, manifest, violations)
        check_leaks(plugin, violations)
        for skill in (plugin / "skills").iterdir():
            if (skill / "SKILL.md").is_file():
                check_skill(skill, violations)
                if skill.name in seen_skill_names:
                    violations.add(
                        f"skill name {skill.name!r} is claimed by both "
                        f"{seen_skill_names[skill.name]} and {plugin.name}"
                    )
                seen_skill_names[skill.name] = plugin.name
        for command in (plugin / "commands").glob("*.md"):
            check_command(command, violations)
        for agent in (plugin / "agents").glob("*.md"):
            check_agent(agent, violations)

    return violations.report()


if __name__ == "__main__":
    raise SystemExit(main())
