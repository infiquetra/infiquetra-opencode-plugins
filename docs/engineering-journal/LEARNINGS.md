# Engineering Journal: Learnings

## 2026-08-13 — Hook Bridge Matcher Evaluation & Symlink Health Probes

### Hook Bridge Matcher Selectors
- **Evidence:** [`plugins/saga/opencode/saga-hooks.ts:76`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/plugins/saga/opencode/saga-hooks.ts#L76), [`plugins/saga/hooks/hooks.json:4-63`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/plugins/saga/hooks/hooks.json#L4-L63).
- **Mechanism:** Claude hook matchers match different payload fields depending on the event: `tool_name` for `PreToolUse`/`PostToolUse`, `source` (`startup|resume`, `compact`) for `SessionStart`, and `trigger` (`auto|manual`) for `PreCompact`. A bridge testing `group.matcher` exclusively against `toolName` evaluates `(!toolName || ...)` to `true` on session and compaction events, skipping them entirely.
- **Generalizable rule:** Event-driven hook bridges must extract the event-specific selector (`toolName ?? payload.source ?? payload.trigger`) before evaluating regex matchers.

### Python `Path.is_symlink()` on Dangling Links
- **Evidence:** [`scripts/install_opencode_plugins.py:140`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/scripts/install_opencode_plugins.py#L140).
- **Mechanism:** In Python's `pathlib`, `link.is_symlink()` returns `True` for dangling symbolic links whose targets do not exist. Only `link.is_symlink() and link.exists()` confirms a healthy, resolvable symbolic link.
- **Generalizable rule:** Always combine `link.is_symlink()` with `link.exists()` when auditing the health of filesystem symlinks.
