# Saga PORTABILITY

- Source: `infiquetra-claude-plugins` `plugins/saga` 0.131.1 at commit
  `972cc50ba879` (recorded in `manifest.json`).
- Status: proof-port. This is the first opencode adapter port and proves the full surface.

## Surface

| Surface | Ported | Notes |
|---|---|---|
| Skills | 22 | Copied with path/tool-name rewrites (see manifest `transforms.skills`). `retro` description truncated 1088 -> 1018 (opencode cap). |
| Commands | 24 | Frontmatter mapped; bodies rewritten to invoke skills by name; `$ARGUMENTS` preserved. |
| Agents | 2 | `mechanical-executor` (bash-only, haiku) and `readonly-verifier` (read-only, sonnet). `effort` dropped (opencode has no equivalent; model carries tier). |
| Scripts/references/docs | bundled | Copied so `${SAGA_PLUGIN_ROOT}/...` invocations resolve; the bridge exports the var into every shell. |
| Hook bridge | `opencode/saga-hooks.ts` | See below. |

## Hook bridge

Bridged (manifest `hooks.bridged`): PreToolUse `validate_json_hook`, `pre_push_gate_hook`,
`team_spawn_residency_hook`, `delegation_tripwire_hook`; PostToolUse `journal_nudge_hook`
(Bash); SessionStart `stale_main_session_hook`, `compact_spore_session_hook`, `ship_teardown`,
`team_teardown_hook`; SessionEnd `team_teardown_hook`; PreCompact `precompact_spore_hook`.

Deferred (manifest `hooks.deferred`): `delegation_stop_audit_hook.py` — reads
`transcript_path`, a Claude JSONL transcript opencode does not produce; its Claude binding
points (Stop, SubagentStop) have no faithful opencode event. Revisit when the bridge can
synthesize a transcript or opencode gains per-subagent completion events.

## Behavioral deltas

- SessionStart hooks fire per opencode session, not once per startup. All bridged SessionStart
  hooks are idempotent teardown/reclaim passes (audited at port time); a non-idempotent
  SessionStart hook would require rate-limiting in the bridge.
- Hook exit 1 (Claude "ask user") blocks with the hook's message instead of prompting:
  opencode plugins cannot prompt mid-tool. An operator can override by removing the veto path.
- `effort` on agents is dropped; tier selection runs through the repo's model tier map
  (`sonnet` -> `anthropic/claude-sonnet-4-6`, `haiku` -> `anthropic/claude-haiku-4-6`).
- Skill bodies that read `${SAGA_PLUGIN_ROOT}/...` files directly (not via bash) need the
  variable expanded first; it is exported into every shell, so `echo $SAGA_PLUGIN_ROOT`
  resolves it. For file reads the agent should expand it before reading.
- `question` replaces `AskUserQuestion`/`ToolSearch`; `websearch` replaces `WebSearch`.
  Channel-inline conventions that named Claude tool behavior were left as prose.
