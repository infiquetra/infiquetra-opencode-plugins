# Portability Matrix

Verified: 2026-08-13

Source snapshot: `infiquetra-claude-plugins` plugin directories at commit `972cc50ba879`
(the U-series orchestrate cycle; saga source version 0.131.1).

Allowed opencode statuses: `included`, `proof-port`, `deferred`, `blocked`, `unsupported`.

Review trigger: rerun this matrix review when the source catalog adds, removes, renames, or
changes a plugin host boundary such as skills, scripts, MCP servers, command files, or hooks.

| Plugin | opencode Status | Reason | opencode Treatment |
|---|---|---|---|
| `saga` | proof-port | Lifecycle spine; richest surface (22 skills, 24 commands, 2 agents, 10 hooks) and the natural proof for all four surface types. | Ported in full: skills/commands/agents transformed, scripts/references/docs bundled, 9 hook bindings bridged; delegation stop-audit deferred (needs transcript). |
| `fleet-core` | deferred | Shared tier/effort policy library consumed by saga via its bundled shim. Saga already carries `fleet_commons_shim.py`; a standalone fleet-core port adds nothing until another plugin needs it. | Port when a consumer plugin's scripts cannot load through their own shim. |
| `deploy` | deferred | Tag-promotion deploy with mutation gates; needs a proof that the skill-plus-script payload and its confirmation gates behave under opencode before activation. | Next proof-port candidate after saga settles. |
| `mission-control` | deferred | SDLC board/issue manager (CLI-backed skills). Portable surface, but board mutation paths need dry-run/preview review under opencode. | Port with confirmation gates; scripts are already repo-relative. |
| `home-lab-ops` | deferred | Skills-plus-references content with no hooks; low risk, low urgency. | Cheap port when requested. |
| `unifi` | deferred | Skill-plus-script CLI payload; mutation paths need confirmation-gate review. | Cheap port when requested. |
| `team-execution` | deferred | Two-phase plan execution with reviewer consensus; the orchestration machinery is Claude-agent shaped and needs an opencode subagent design first. | Design review before porting. |
| `redis-channel` | deferred | Ships an MCP server plus channel bridge; needs a server-boundary proof (MCP manifest maps to opencode `mcp` config, service packaging is separate). | Server-boundary proof first. |
| `hermes-profile-evolution` | deferred | Profile-evolution advisory with a PreToolUse edit-guard hook; hooks bridge per plugin and need their own review. | Small hook bridge; low urgency. |
| `codex` | deferred | Bridge plugin delegating to an external Codex engine; not opencode-relevant (opencode replaces the engine it delegates to). | Skip unless cross-engine delegation is wanted from opencode sessions. |
| `agy` | deferred | Antigravity delegation bridge with guarded wrapper; same external-engine argument as `codex`. | Skip unless delegation is wanted from opencode sessions. |
| `orchestrate` | unsupported | New session-lifecycle plugin built on Claude-native session semantics and herdr event clients; opencode owns session lifecycle natively. | Reassess if an opencode herdr overlay is wanted. |

## Notes

- 2026-08-13: `saga` 0.131.1 lands as the proof port (first cycle
  `docs/portability/ports/2026-08-13-saga.json`). Skills and commands were mechanically
  transformed; the hook bridge covers PreToolUse, PostToolUse (Bash), SessionStart,
  SessionEnd, and PreCompact. `delegation_stop_audit_hook.py` is deferred: it reads
  `transcript_path` (a Claude JSONL transcript opencode does not produce) and fires on
  Stop/SubagentStop events with no faithful opencode equivalent.
- opencode installs skills into a flat name-keyed directory; all 45 source skill names are
  unique across the 10 source plugins (verified), so no namespacing is needed for ports.
- Skill descriptions over opencode's 1024-char cap are truncated at a word boundary and the
  truncation is recorded in the manifest transforms (first case: `retro`, 1088 -> 1018).
