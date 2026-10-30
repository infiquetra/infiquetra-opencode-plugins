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

## OpenCode 2

The hook bridge exposes a V1 `server()` entrypoint and a V2 `setup()` entrypoint.
For V2, shell creation, tool execution, compaction and server events are wired
through their respective domains. Some V2 location plugins are loaded after the
session is created, so the bridge also runs startup hooks on a session's first
prompt, tool call or compaction. It keeps one in-flight startup per session and
forgets the session after deletion. A resumed session may run these idempotent
startup hooks again after a server restart. Failed V2 tool calls do not run the
successful PostToolUse hooks.

Run `uv run pytest tests/test_saga_hooks.py tests/test_saga_v2_runtime.py` for
the isolated bridge checks. The V2 runtime test uses a local OpenCode 2 server
with a temporary home and `resume=false`; it makes no model request. It skips
when OpenCode 2 is unavailable and accepts `OPENCODE_V2_BIN` to select a binary.

## Neutral Outcome fixtures

The [2026-10-30 fixture-only cycle](../../docs/portability/ports/2026-10-30-saga-outcome-cross-runtime-fixtures.json)
pins six producer-owned `outcome-cross-runtime/v1` fixtures to Claude commit
`972cc50ba8799d8d4663b893e008bb1bf318d4d7`. OpenCode owns the test harness, which loads
the bundled `scripts/outcome_compat.py` under an isolated module name and restores import
state. Four cases validate and canonically serialize the original bytes; two cases reject
an unknown field and an unsupported protocol range at their respective stages. Valid
version-1 negotiation is also asserted.

This cycle imports only repository test data. Regeneration, installation and host restart
are not applicable to the unchanged installed surface and were not performed. Manifest,
version, lineage, runtime and bridge behavior remain unchanged, including the inherited
`RUNTIME_LABEL="claude"`. The CLI has no peer-envelope input, and these pure assertions do
not prove authority transfer, protected handoff execution or host compatibility. Existing
installer, transform, validator and bridge tests remain alongside the shared fixtures.
