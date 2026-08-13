#!/usr/bin/env python3
"""Port one Infiquetra Claude Code plugin into the opencode adapter repo.

The port is mechanical and deterministic:

- skills: copied verbatim (the SKILL.md spec is shared with opencode) with a
  tool-name rewrite of Claude's ``AskUserQuestion`` to opencode's ``question``;
- commands: frontmatter mapped to opencode fields (``name`` dropped, filename
  is the command name; ``argument-hint`` folded into ``description``), bodies
  rewritten from "Load ``<plugin>/skills/<skill>/SKILL.md``" to a skill-tool
  invocation, ``$ARGUMENTS`` preserved;
- agents: frontmatter mapped (``name`` -> filename, Claude tool list ->
  opencode permission keys, model tier -> provider-prefixed model id, ``mode:
  subagent`` added), body verbatim;
- hooks: ``hooks.json`` copied as lineage; the opencode-native bridge is a
  hand-authored TypeScript file that this repo version-controls under
  ``plugins/<name>/hooks/<name>-hooks.ts`` (see docs/portability runbook);
- plugin-level ``scripts/``, ``references/``, and ``docs/`` are copied so
  skill bodies and bundled scripts resolve exactly as they do in the source.

Every run writes ``plugins/<name>/manifest.json`` and a port-cycle JSON at
``docs/portability/ports/<date>-<plugin>.json``. The manifest pins the source
commit and records every transform; the validator treats both as contract.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path.home() / "workspace" / "infiquetra" / "infiquetra-claude-plugins"

MODEL_TIER_MAP = {
    "fable": "anthropic/claude-opus-4-6",
    "opus": "anthropic/claude-opus-4-6",
    "sonnet": "anthropic/claude-sonnet-4-6",
    "haiku": "anthropic/claude-haiku-4-6",
}

CLAUDE_TOOL_TO_PERMISSION = {
    "Read": "read",
    "Glob": "glob",
    "Grep": "grep",
    "Bash": "bash",
    "WebFetch": "webfetch",
    "WebSearch": "websearch",
    "Write": "edit",
    "Edit": "edit",
    "MultiEdit": "edit",
    "NotebookEdit": "edit",
    "Task": "task",
    "Agent": "task",
    "TodoWrite": "todowrite",
    "AskUserQuestion": "question",
}

ALL_PERMISSION_KEYS = (
    "read",
    "edit",
    "glob",
    "grep",
    "list",
    "bash",
    "task",
    "todowrite",
    "webfetch",
    "websearch",
    "lsp",
    "skill",
    "question",
)

COPIED_PLUGIN_DIRS = ("scripts", "references", "docs", "hooks")
SKIPPED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    ".DS_Store",
    ".git",
}

LOAD_REFERENCE = re.compile(
    r"Load\s+`(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?(?:plugins/)?"
    r"(?P<plugin>[a-z0-9-]+)/skills/(?P<skill>[a-z0-9-]+)/SKILL\.md`\.?",
    re.IGNORECASE,
)


def plugin_root_rewrites(body: str, plugin_name: str) -> tuple[str, list[str]]:
    """Rewrite Claude plugin-root path and tool references onto opencode equivalents.

    Claude Code resolves these paths against the plugin install root
    (``CLAUDE_PLUGIN_ROOT``). opencode has no plugin root, so the ported hook
    bridge exports ``<NAME>_PLUGIN_ROOT`` through the ``shell.env`` plugin
    hook and these bodies reference that variable instead. Tool names that do
    not exist in opencode are rewritten to their opencode equivalents.
    """
    env_var = f"{plugin_name.upper().replace('-', '_')}_PLUGIN_ROOT"
    name = re.escape(plugin_name)
    rewrites: list[str] = []

    def skill_ref(match: re.Match[str]) -> str:
        rewrites.append(f"SkillRef->name:{match.group('skill')}")
        return f"`{match.group('skill')}` skill"

    def agent_ref(match: re.Match[str]) -> str:
        rewrites.append(f"AgentRef->name:{match.group('agent')}")
        return f"`{match.group('agent')}` agent (dispatch by name)"

    def root_path(subdir: str, suffix: str) -> str:
        rewrites.append(f"PluginRootPath->env:{env_var}/{subdir}{suffix}")
        return f"${{{env_var}}}/{subdir}{suffix}"

    patterns = [
        # `plugins/<p>/skills/<n>/SKILL.md` or bare `saga/skills/<n>/SKILL.md`
        (
            re.compile(rf"`(?:plugins/)?{name}/skills/(?P<skill>[a-z0-9-]+)/SKILL\.md`"),
            skill_ref,
        ),
        # `plugins/<p>/agents/<n>.md` -> agent-by-name reference
        (re.compile(rf"`(?:plugins/)?{name}/agents/(?P<agent>[a-z0-9-]+)\.md`"), agent_ref),
        # `(plugins/)?saga/skills/<n>/<rest>` -> env-rooted file path
        (
            re.compile(
                rf"`(?:plugins/)?{name}/skills/(?P<skill>[a-z0-9-]+)/(?P<rest>[a-z0-9/._-]+)`"
            ),
            lambda m: root_path(f"skills/{m.group('skill')}/{m.group('rest')}", ""),
        ),
        # `(plugins/)?saga/<subdir>/<rest>` (backtick-quoted dir path) -> env-rooted
        (
            re.compile(
                rf"`(?:plugins/)?{name}/(?P<subdir>scripts|references|docs|hooks)/(?P<rest>[a-z0-9/._,{{}}-]*)`"
            ),
            lambda m: root_path(f"{m.group('subdir')}/{m.group('rest')}", ""),
        ),
        # ../../<fixed-dir>/ from within skills/references -> plugin root
        (
            re.compile(r"\.\./\.\./(?P<subdir>references|scripts|docs|hooks)/"),
            lambda m: root_path(m.group("subdir"), "/"),
        ),
        # ../../<sibling-skill>/ from within skills/references -> plugin root skills dir
        (
            re.compile(r"\.\./\.\./(?P<skill>[a-z0-9-]+)/"),
            lambda m: root_path(f"skills/{m.group('skill')}", "/"),
        ),
        # bare (unquoted) saga/<subdir>/ -> env-rooted dir
        (
            re.compile(
                rf"(?<![\w`])(?:plugins/)?{name}/(?P<subdir>scripts|references|docs|hooks)(?=$|[/`\s'\"])"
            ),
            lambda m: root_path(m.group("subdir"), ""),
        ),
    ]
    for pattern, replacement in patterns:
        body = pattern.sub(replacement, body)

    if "ToolSearch" in body:
        body = body.replace("ToolSearch", "question")
        rewrites.append("ToolSearch->question")
    if "WebSearch" in body:
        body = body.replace("WebSearch", "websearch")
        rewrites.append("WebSearch->websearch")
    return body, rewrites


YAML_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = YAML_FRONTMATTER.match(text)
    if not match:
        return {}, text
    fields = yaml.safe_load(match.group(1)) or {}
    if not isinstance(fields, dict):
        raise ValueError(f"frontmatter is not a mapping: {fields!r}")
    return dict(fields), text[match.end() :]


def write_yaml_frontmatter(fields: dict[str, Any]) -> str:
    body = yaml.safe_dump(fields, sort_keys=False, default_flow_style=False)
    return f"---\n{body}---\n"


def git_head(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def load_plugin_json(plugin_dir: Path) -> dict[str, Any]:
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    if manifest.exists():
        return dict(json.loads(manifest.read_text()))
    return {}


def rewrite_ask_user_question(text: str) -> str:
    return text.replace("AskUserQuestion", "question")


def port_skills(source: Path, dest: Path, plugin_name: str) -> list[dict[str, Any]]:
    """Copy skill directories verbatim, rewriting Claude host references."""
    skills: list[dict[str, Any]] = []
    source_skills = source / "skills"
    if not source_skills.is_dir():
        return skills
    for skill_dir in sorted(source_skills.iterdir()):
        if not (skill_dir / "SKILL.md").is_file():
            continue
        target = dest / "skills" / skill_dir.name
        shutil.copytree(
            skill_dir,
            target,
            ignore=shutil.ignore_patterns(*SKIPPED_NAMES),
            dirs_exist_ok=True,
        )
        rewrites: list[str] = []
        for md_file in target.rglob("*.md"):
            original = md_file.read_text()
            file_rewrites: list[str] = []
            rewritten, root_rewrites = plugin_root_rewrites(original, plugin_name)
            file_rewrites.extend(root_rewrites)
            if "AskUserQuestion" in rewritten:
                rewritten = rewrite_ask_user_question(rewritten)
                file_rewrites.append("AskUserQuestion->question")
            if md_file.name == "SKILL.md":
                fields, body = split_frontmatter(rewritten)
                description = str(fields.get("description") or "")
                if len(description) > 1024:
                    truncated = description[:1024].rsplit(" ", 1)[0]
                    fields["description"] = truncated
                    rewritten = write_yaml_frontmatter(fields) + "\n" + body
                    file_rewrites.append(
                        f"DescriptionTruncated:{len(description)}->{len(truncated)}"
                    )
            if file_rewrites:
                md_file.write_text(rewritten)
                if md_file.name == "SKILL.md":
                    rewrites.extend(file_rewrites)
        skills.append({"name": skill_dir.name, "rewrites": rewrites})
    return skills


def rewrite_load_references(body: str) -> tuple[str, list[str]]:
    """Rewrite ``Load `<plugin>/skills/<skill>/SKILL.md``` into a skill-tool call."""
    rewrites: list[str] = []

    def rewrite_one(match: re.Match[str]) -> str:
        skill = match.group("skill")
        rewrites.append(f"LoadReference->skill-tool:{skill}")
        return (
            f"Use the skill tool to load the `{skill}` skill "
            f"(name: `{skill}`), then follow its instructions."
        )

    return LOAD_REFERENCE.sub(rewrite_one, body), rewrites


def port_commands(source: Path, dest: Path, plugin_name: str) -> list[dict[str, Any]]:
    """Transform command markdown: frontmatter map + body rewrites."""
    commands: list[dict[str, Any]] = []
    source_commands = source / "commands"
    if not source_commands.is_dir():
        return commands
    for command_file in sorted(source_commands.glob("*.md")):
        fields, body = split_frontmatter(command_file.read_text())
        description = " ".join(str(fields.get("description") or "").split())
        argument_hint = str(fields.get("argument-hint") or "")
        if argument_hint:
            description = f"{description} Arguments: {argument_hint}"

        body, rewrites = rewrite_load_references(body)
        root_body, root_rewrites = plugin_root_rewrites(body, plugin_name)
        body = root_body
        rewrites.extend(root_rewrites)
        if "AskUserQuestion" in body:
            body = rewrite_ask_user_question(body)
            rewrites.append("AskUserQuestion->question")

        target = dest / "commands" / command_file.name
        target.write_text(write_yaml_frontmatter({"description": description}) + "\n" + body)
        commands.append({"name": command_file.stem, "rewrites": rewrites})
    return commands


def port_agents(source: Path, dest: Path) -> list[dict[str, Any]]:
    """Transform agent markdown: Claude frontmatter to opencode frontmatter."""
    agents: list[dict[str, Any]] = []
    source_agents = source / "agents"
    if not source_agents.is_dir():
        return agents
    for agent_file in sorted(source_agents.glob("*.md")):
        fields, body = split_frontmatter(agent_file.read_text())
        name = str(fields.get("name") or agent_file.stem)
        description = " ".join(str(fields.get("description") or "").split())
        model_tier = str(fields.get("model") or "sonnet").strip()
        if model_tier not in MODEL_TIER_MAP:
            raise ValueError(
                f"agent {name}: unknown model tier {model_tier!r}; "
                f"known tiers: {sorted(MODEL_TIER_MAP)}"
            )

        tool_list = [
            tool.strip() for tool in str(fields.get("tools") or "").split(",") if tool.strip()
        ]
        allowed = set()
        for tool in tool_list:
            permission_key = CLAUDE_TOOL_TO_PERMISSION.get(tool)
            if permission_key is None:
                raise ValueError(
                    f"agent {name}: no opencode permission mapping for Claude tool {tool!r}"
                )
            allowed.add(permission_key)

        permission: dict[str, str] = {
            key: ("allow" if key in allowed else "deny") for key in ALL_PERMISSION_KEYS
        }

        mapped = {
            "description": description,
            "mode": "subagent",
            "model": MODEL_TIER_MAP[model_tier],
            "permission": permission,
        }
        dropped = [key for key in ("name", "tools", "model", "effort") if key in fields]
        target = dest / "agents" / f"{name}.md"
        target.write_text(write_yaml_frontmatter(mapped) + "\n" + body)
        agents.append(
            {
                "name": name,
                "source_file": agent_file.name,
                "model_tier": model_tier,
                "mapped_model": MODEL_TIER_MAP[model_tier],
                "dropped_fields": dropped,
            }
        )
    return agents


def copy_plugin_dirs(source: Path, dest: Path, plugin_name: str) -> list[str]:
    copied: list[str] = []
    for dir_name in COPIED_PLUGIN_DIRS:
        source_dir = source / dir_name
        if not source_dir.is_dir():
            continue
        shutil.copytree(
            source_dir,
            dest / dir_name,
            ignore=shutil.ignore_patterns(*SKIPPED_NAMES),
            dirs_exist_ok=True,
        )
        for md_file in (dest / dir_name).rglob("*.md"):
            original = md_file.read_text()
            rewritten, _ = plugin_root_rewrites(original, plugin_name)
            if rewritten != original:
                md_file.write_text(rewritten)
        copied.append(dir_name)
    return copied


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("plugin", help="plugin directory name to port, e.g. saga")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="path to infiquetra-claude-plugins checkout",
    )
    args = parser.parse_args()

    source_plugin = args.source / "plugins" / args.plugin
    if not source_plugin.is_dir():
        raise SystemExit(f"source plugin not found: {source_plugin}")

    source_commit = git_head(args.source)
    claude_manifest = load_plugin_json(source_plugin)
    upstream_version = claude_manifest.get("version", "0.0.0")

    dest = REPO_ROOT / "plugins" / args.plugin
    if dest.exists():
        # Regenerate the ported surface in place, but never touch
        # adapter-native artifacts (opencode/ holds hand-authored bridges).
        for ported in (
            "skills",
            "commands",
            "agents",
            "scripts",
            "references",
            "docs",
            "hooks",
            "manifest.json",
        ):
            path = dest / ported
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "skills").mkdir()
    (dest / "commands").mkdir()
    (dest / "agents").mkdir()

    skills = port_skills(source_plugin, dest, args.plugin)
    commands = port_commands(source_plugin, dest, args.plugin)
    agents = port_agents(source_plugin, dest)
    copied_dirs = copy_plugin_dirs(source_plugin, dest, args.plugin)

    manifest: dict[str, Any] = {
        "schema": "opencode-plugin-port.v1",
        "name": args.plugin,
        "version": f"{upstream_version}+opencode.{dt.datetime.now(dt.UTC):%Y%m%d%H%M%S}",
        "status": "proof-port",
        "lineage": {
            "source_repo": "infiquetra/infiquetra-claude-plugins",
            "source_commit": source_commit,
            "source_version": upstream_version,
            "ported_at": dt.datetime.now(dt.UTC).isoformat(),
        },
        "inventory": {
            "skills": [skill["name"] for skill in skills],
            "commands": [command["name"] for command in commands],
            "agents": [agent["name"] for agent in agents],
            "copied_plugin_dirs": copied_dirs,
            "hook_bridges": [],
        },
        "transforms": {
            "skills": {skill["name"]: skill["rewrites"] for skill in skills},
            "commands": {command["name"]: command["rewrites"] for command in commands},
            "agents": agents,
            "dropped_claude_dirs": [".claude-plugin", "marketplace artifacts"],
        },
        "hooks": {"bridged": [], "deferred": []},
    }

    opencode_dir = REPO_ROOT / "plugins" / args.plugin / "opencode"
    hook_manifest_path = opencode_dir / "hook-manifest.json"
    if hook_manifest_path.exists():
        hook_manifest = json.loads(hook_manifest_path.read_text())
        bridges = sorted(
            path.name for path in opencode_dir.iterdir() if path.suffix in (".ts", ".js")
        )
        manifest["inventory"]["hook_bridges"] = bridges
        manifest["hooks"] = {
            "bridged": hook_manifest.get("bridged", {}),
            "deferred": hook_manifest.get("deferred_hooks", []),
            "deferred_reasons": hook_manifest.get("deferred_reasons", {}),
        }

    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    cycle = {
        "schema": "opencode-port-cycle.v1",
        "plugin": args.plugin,
        "source_commit": source_commit,
        "source_version": upstream_version,
        "ported_at": dt.datetime.now(dt.UTC).isoformat(),
        "manifest_version": manifest["version"],
        "skills": len(skills),
        "commands": len(commands),
        "agents": len(agents),
        "copied_plugin_dirs": copied_dirs,
    }
    cycle_path = (
        REPO_ROOT
        / "docs"
        / "portability"
        / "ports"
        / f"{dt.date.today().isoformat()}-{args.plugin}.json"
    )
    cycle_path.write_text(json.dumps(cycle, indent=2) + "\n")

    print(f"ported {args.plugin} {upstream_version} @ {source_commit[:12]}")
    print(f"  skills={len(skills)} commands={len(commands)} agents={len(agents)}")
    print(f"  copied dirs: {', '.join(copied_dirs) or 'none'}")
    print(f"  manifest: plugins/{args.plugin}/manifest.json")
    print(f"  cycle:    docs/portability/ports/{cycle_path.name}")


if __name__ == "__main__":
    main()
