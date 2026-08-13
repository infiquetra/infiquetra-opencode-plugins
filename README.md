# Infiquetra OpenCode Plugins

opencode-native adapter repo for selected Infiquetra Claude Code plugins.

This repo is **not** a full mirror of `infiquetra-claude-plugins`. It carries the opencode-ready
plugin surface, currently:

| Plugin | Version | Status |
|---|---:|---|
| `saga` | 0.131.1+opencode | proof-port |

`saga` is the lifecycle spine (Think, Plan & execute, Hand off, Review, Improve & route) and the
proof port for the full surface: skills, commands, agents, and the hook bridge. Other Claude
plugins are classified in `docs/portability/matrix.md` and ported on demand.

## What a port means

Claude Code plugins and opencode share the markdown surface formats but not the packaging:

| Claude surface | opencode surface | Port treatment |
|---|---|---|
| `skills/*/SKILL.md` | `skills/*/SKILL.md` (same spec) | copied; paths, tool names, and over-long descriptions rewritten |
| `commands/*.md` | `commands/*.md` | frontmatter mapped, bodies rewritten to invoke skills by name |
| `agents/*.md` | `agents/*.md` | frontmatter mapped (`tools` -> `permission`, model tier -> provider-prefixed model id, `mode: subagent`) |
| `hooks/hooks.json` (shell + stdin JSON) | JS/TS plugin events | hand-authored bridge per plugin under `opencode/` |
| `.claude-plugin/plugin.json`, marketplaces | none | dropped |

Every port records its lineage (source commit SHA), inventory, and every transform in
`plugins/<name>/manifest.json`, plus a machine-readable cycle at
`docs/portability/ports/<date>-<plugin>.json`.

## Installation

The installer builds a symlink farm from this repo into an opencode config directory, so the repo
stays the source of truth and a re-run after any port refresh is all that's needed:

```bash
uv run python scripts/install_opencode_plugins.py install            # all ported plugins
uv run python scripts/install_opencode_plugins.py install --plugins saga
uv run python scripts/install_opencode_plugins.py status
uv run python scripts/install_opencode_plugins.py uninstall          # removes only what it created
```

Default target is `~/.config/opencode`. Restart opencode after installing.

## Validate

```bash
uv run python scripts/validate_opencode_plugins.py
uv run pytest
uv run ruff check .
uv run mypy scripts/
```

## Port a plugin

The port is mechanical and rerunnable (adapter-native artifacts under `plugins/<name>/opencode/`
survive a re-port):

```bash
uv run python scripts/port_plugin.py <plugin-name> [--source ~/workspace/infiquetra/infiquetra-claude-plugins]
```

A port is a proof, not a sync: review the diff, update `docs/portability/matrix.md` and
`plugins/<name>/PORTABILITY.md`, then install and validate. The mandatory human procedure is
`docs/portability/claude-to-opencode-plugin-port-runbook.md`.

## Layout

- `plugins/<name>/skills|commands|agents/` — the ported opencode surface.
- `plugins/<name>/scripts|references|docs|hooks/` — bundled script and reference payload, copied
  so relative invocations resolve exactly as they do in the source.
- `plugins/<name>/opencode/` — adapter-native artifacts: the hook bridge (`<name>-hooks.ts`) and
  `hook-manifest.json` (bridged/deferred hook contract). Never overwritten by the port tool.
- `plugins/<name>/manifest.json` — port contract: lineage, inventory, transforms, hooks.
- `docs/portability/` — matrix, runbook, and per-cycle machine records.

## How the ported surface behaves

- Skill and command bodies reference `${SAGA_PLUGIN_ROOT}/scripts/...` etc. The hook bridge
  exports that variable into every shell via opencode's `shell.env` plugin hook, mirroring
  Claude's `CLAUDE_PLUGIN_ROOT` contract. For file reads the agent expands the variable first.
- Claude's `AskUserQuestion`/`ToolSearch`/`WebSearch` tool names are rewritten to opencode's
  `question`/`websearch`.
- Hook exit codes follow the Claude protocol: 0 continue, 1 feedback (blocks, since opencode
  plugins cannot prompt), 2 block. PreToolUse vetoes deny the tool call.
- Hooks with no faithful opencode equivalent are declared deferred in `hook-manifest.json` and
  skipped by the bridge; the validator enforces that the bridge and manifest agree.
