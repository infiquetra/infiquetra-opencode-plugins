#!/usr/bin/env python3
"""Install ported Infiquetra opencode plugins into an opencode config directory.

opencode auto-discovers, with no config entry needed:

- ``<cfg>/skills/<name>/SKILL.md``
- ``<cfg>/commands/<name>.md``
- ``<cfg>/agents/<name>.md``
- ``<cfg>/plugins/*.ts`` (and ``*.js``)

This installer builds a symlink farm from this repo's ``plugins/`` tree into
those directories, so the repo stays the source of truth and reinstalls after
a port/refresh need nothing but a re-run. Every symlink is recorded in
``<cfg>/.infiquetra-plugins.json``; ``uninstall`` removes exactly what a prior
``install`` created and never touches foreign files.

Usage:
    scripts/install_opencode_plugins.py install [--config ~/.config/opencode] [--plugins saga ...]
    scripts/install_opencode_plugins.py uninstall [--config ...]
    scripts/install_opencode_plugins.py status [--config ...]
"""

from __future__ import annotations

import json
import os
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE_NAME = ".infiquetra-plugins.json"
DEFAULT_CONFIG = Path.home() / ".config" / "opencode"


def plugin_dirs() -> list[Path]:
    return sorted(
        plugin
        for plugin in (REPO_ROOT / "plugins").iterdir()
        if plugin.is_dir() and (plugin / "manifest.json").is_file()
    )


def load_state(config_dir: Path) -> dict[str, Any]:
    state_path = config_dir / STATE_FILE_NAME
    if not state_path.exists():
        return {"schema": "infiquetra-opencode-install.v1", "links": []}
    return dict(json.loads(state_path.read_text()))


def save_state(config_dir: Path, state: dict[str, Any]) -> None:
    (config_dir / STATE_FILE_NAME).write_text(json.dumps(state, indent=2) + "\n")


def plan_links(config_dir: Path, selected: list[str]) -> list[tuple[Path, Path]]:
    """Return (target, link) pairs for the selected plugins."""
    links: list[tuple[Path, Path]] = []
    for plugin in plugin_dirs():
        if selected and plugin.name not in selected:
            continue
        skills_dir = plugin / "skills"
        if skills_dir.is_dir():
            for skill in sorted(skills_dir.iterdir()):
                if (skill / "SKILL.md").is_file():
                    links.append((skill, config_dir / "skills" / skill.name))
        commands_dir = plugin / "commands"
        if commands_dir.is_dir():
            for command in sorted(commands_dir.glob("*.md")):
                links.append((command, config_dir / "commands" / command.name))
        agents_dir = plugin / "agents"
        if agents_dir.is_dir():
            for agent in sorted(agents_dir.glob("*.md")):
                links.append((agent, config_dir / "agents" / agent.name))
        opencode_dir = plugin / "opencode"
        if opencode_dir.is_dir():
            for bridge in sorted(opencode_dir.glob("*.ts")) + sorted(opencode_dir.glob("*.js")):
                link_name = (
                    bridge.name
                    if bridge.name.startswith(f"{plugin.name}-")
                    else f"{plugin.name}-{bridge.name}"
                )
                links.append((bridge, config_dir / "plugins" / link_name))
    return links


def install(config_dir: Path, selected: list[str]) -> int:
    state = load_state(config_dir)
    existing = {(entry["link"], entry["target"]) for entry in state["links"]}
    created: list[dict[str, str]] = []
    errors: list[str] = []

    for target, link in plan_links(config_dir, selected):
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            current = os.readlink(link)
            if os.path.abspath(current) == str(target):
                continue
            errors.append(f"link exists with different target: {link} -> {current}")
            continue
        if link.exists():
            errors.append(f"refusing to overwrite non-symlink: {link}")
            continue
        link.symlink_to(target)
        record = {"target": str(target), "link": str(link)}
        if (str(link), str(target)) not in existing:
            state["links"].append(record)
        created.append(record)

    save_state(config_dir, state)
    print(f"installed {len(created)} links into {config_dir}")
    if errors:
        for error in errors:
            print(f"  ERROR: {error}", file=sys.stderr)
        return 1
    return 0


def uninstall(config_dir: Path) -> int:
    state = load_state(config_dir)
    removed = 0
    for entry in list(state["links"]):
        link = Path(entry["link"])
        if link.is_symlink():
            link.unlink()
            removed += 1
    state["links"] = []
    save_state(config_dir, state)
    print(f"removed {removed} links from {config_dir}")
    return 0


def status(config_dir: Path) -> int:
    state = load_state(config_dir)
    links = [Path(entry["link"]) for entry in state["links"]]
    if not links:
        print(f"nothing installed in {config_dir}")
        return 0
    for link in sorted(links):
        marker = "OK" if link.is_symlink() else "BROKEN/MISSING"
        target = os.readlink(link) if link.is_symlink() else "?"
        print(f"  {marker:14} {link.name:32} -> {target}")
    print(f"{len(links)} links recorded")
    return 0


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["install", "uninstall", "status"])
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="opencode config directory (default ~/.config/opencode)",
    )
    parser.add_argument(
        "--plugins",
        nargs="*",
        default=[],
        help="plugin names to install (default: all ported plugins)",
    )
    args = parser.parse_args()

    if not args.config.is_dir():
        raise SystemExit(f"config directory not found: {args.config}")
    if args.command == "install":
        raise SystemExit(install(args.config, args.plugins))
    if args.command == "uninstall":
        raise SystemExit(uninstall(args.config))
    raise SystemExit(status(args.config))


if __name__ == "__main__":
    main()
