# Claude-to-opencode Plugin Port Runbook

## Contract Metadata

- Status: canonical
- Runbook version: `1`
- Machine contract: `ports/<date>-<plugin>.json` (one per port cycle)
- Contract tool: `../../scripts/port_plugin.py`

## Purpose

This runbook is the required human procedure for bringing behavior from
`infiquetra-claude-plugins` into this opencode adapter repository. It owns judgment; the JSON
cycle record and `plugins/<name>/manifest.json` own the exhaustive machine contract.

Do not treat a prior classification, installed symlink farm, or current checkout as a
substitute for the current contract.

## Normative Language And Non-Goals

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative. The governing rule is: **port behavior,
not host-shaped files.**

This procedure does not authorize bulk mirroring, copying user credentials, changing external
systems, or declaring byte parity. A plugin version records exposed, tested opencode behavior
and its lineage; it does not assert that the Claude and opencode packages are identical.

## Surface Mapping

| Claude surface | opencode surface | Port rule |
|---|---|---|
| `skills/*/SKILL.md` (+ `references/`, `scripts/`) | same SKILL.md spec | Copy. Rewrite plugin-root paths to `${<NAME>_PLUGIN_ROOT}/...`, cross-skill file references to skill names, `AskUserQuestion`/`ToolSearch` -> `question`, `WebSearch` -> `websearch`. Truncate descriptions over 1024 chars at a word boundary and record the truncation. |
| `commands/*.md` | `commands/*.md` | Map frontmatter: drop `name` (filename is the name) and `argument-hint` (folded into `description`); rewrite `Load \`...\` -> skill-tool invocation; `$ARGUMENTS` is native on both sides. |
| `agents/*.md` | `agents/*.md` | Map frontmatter: `name` -> filename, `tools` list -> `permission` allow/deny keys, model tier -> provider-prefixed model id via the repo's tier map, drop `effort`, add `mode: subagent`. |
| `hooks/hooks.json` | JS/TS plugin events | Hand-author a bridge under `plugins/<name>/opencode/<name>-hooks.ts`. Map events per the table below. Declare the bridged/deferred split in `opencode/hook-manifest.json`. |
| `.mcp.json` | `mcp` config in `opencode.json` | Translate on port: stdio -> `{"type": "local", "command": [...]}`, http/sse -> `{"type": "remote", "url": ...}`. |
| `.claude-plugin/plugin.json`, marketplaces, LSP manifests | none | Drop. |

### Hook event mapping

| Claude event | opencode event | Notes |
|---|---|---|
| PreToolUse | `tool.execute.before` | Map opencode tool names to Claude names (`edit/write/patch` -> `Edit`/`Write`, `bash` -> `Bash`, `task` -> `Agent`). Fabricate `tool_input` with Claude snake_case keys. Await and throw on veto (exit 1/2). |
| PostToolUse | `tool.execute.after` | Fire-and-forget; log vetoes. |
| SessionStart `startup\|resume` | `session.created` | Runs per opencode session (Claude runs it once per startup); hooks must be idempotent. Pass `source: startup`. |
| SessionStart `compact` | `event` `session.compacted` | Post-compaction. Pass `source: compact`. |
| PreCompact | `experimental.session.compacting` | Pre-compaction on both sides. |
| SessionEnd | `session.deleted` | |
| Stop | none | No opencode equivalent of Claude's post-response loop. |
| SubagentStop | none | No per-subagent completion event. |
| Notification, PermissionRequest | none | Deferred. |

### Hook payload contract

The bridge fabricates the Claude stdin JSON with the fields opencode can supply:
`session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_input`, `source`, `trigger`.
`transcript_path` is **not** fabricatable; any hook that reads it is deferred until the bridge
synthesizes a transcript. Exit codes: 0 continue, 1 feedback (block, opencode cannot prompt),
2 block. The bridge exports `<NAME>_PLUGIN_ROOT` via `shell.env` so ported bodies resolve.

## Port Procedure

1. **Resolve source authority.** Verify the source checkout is at the commit you intend to pin
   (`git -C <source> rev-parse HEAD`). The port tool pins that SHA into the manifest.
2. **Check surface conflicts.** Skill names must be unique across all ported plugins (flat
   install directory). The validator enforces this.
3. **Port mechanically.** `uv run python scripts/port_plugin.py <plugin> --source <path>`.
   The tool regenerates the ported surface in place and never touches `plugins/<name>/opencode/`.
4. **Author or review the hook bridge.** If the source has `hooks/hooks.json`, the bridge and
   `hook-manifest.json` MUST already exist (hand-authored) before the port is considered
   complete. Classify each hook: bridged as-is, bridged with payload adaptation, or deferred
   with a recorded reason.
5. **Review the diff.** Every transform is recorded in the manifest under `transforms`. Read
   them. Reject silent surprises (e.g., a truncation you did not expect, a cross-skill rewrite
   that changed meaning).
6. **Write `plugins/<name>/PORTABILITY.md`** recording surface decisions: what is ported,
   what is deferred and why, and any behavioral deltas opencode imposes.
7. **Validate.** `uv run python scripts/validate_opencode_plugins.py` must pass, then
   `uv run pytest` and `uv run ruff check .`.
8. **Install and verify.** `uv run python scripts/install_opencode_plugins.py install
   --plugins <plugin>`, restart opencode, and confirm with `opencode debug skill` and
   `opencode debug agent` that the surface is discovered.
9. **Record the cycle.** The port tool writes `ports/<date>-<plugin>.json`. Update the matrix
   row for the plugin and the README table in the same commit.

## Stop Rules

- Stop if the source plugin's hooks read `transcript_path` or any other field this runbook
  marks not fabricatable: classify those hooks deferred rather than guessing payload shapes.
- Stop if two plugins claim the same skill name: decide the namespace policy before porting.
- Stop if a transform rewrites meaning (not just a name or path): the mechanical port is the
  floor, not a substitute for judgment.
