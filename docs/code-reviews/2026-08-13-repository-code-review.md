# Code Review: Repository Surface (infiquetra-opencode-plugins)

- **Target:** Full repository working tree (`master` branch)
- **Reviewed Revision:** Working tree (uncommitted initial state)
- **Status:** BLOCKED (1 P1 finding must be resolved before production usage)
- **Date:** 2026-08-13
- **Review Mode:** Interactive

## Built vs Planned & Scope Audit

- **Intent:** opencode-native adapter repository for Infiquetra plugins, establishing proof-port tooling (`scripts/port_plugin.py`), validation harness (`scripts/validate_opencode_plugins.py`), symlink installer (`scripts/install_opencode_plugins.py`), and the proof port of the `saga` plugin surface.
- **Scope Check:** CLEAN. No extraneous packages or unrelated changes detected.
- **Plan Completion:**
  - `port_plugin.py`: DONE (Transforms skills, commands, agents, copies payloads, records manifest).
  - `validate_opencode_plugins.py`: DONE (Validates schema, inventory, uniqueness, deferred hooks).
  - `install_opencode_plugins.py`: DONE (Symlink management, roundtrip install/uninstall).
  - `plugins/saga/opencode/saga-hooks.ts`: PARTIAL (PreToolUse/PostToolUse bridged, but SessionStart/PreCompact matcher evaluation has a logic bug).

---

## Review Findings

### P1 Findings (High Impact)

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 1 | `plugins/saga/opencode/saga-hooks.ts:76` | `matchingEntries` ignores `SessionStart` and `PreCompact` hooks with matchers | Correctness, Reliability | 100 | safe_auto -> review-fixer |

#### Finding #1: SessionStart and PreCompact hooks with matchers are silently skipped
- **File:** [`plugins/saga/opencode/saga-hooks.ts:76`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/plugins/saga/opencode/saga-hooks.ts#L76)
- **Why it matters:** In `matchingEntries`, the check `if (group.matcher && (!toolName || !new RegExp(group.matcher).test(toolName)))` relies exclusively on `toolName`. When `SessionStart` (`source: "startup" | "compact"`) or `PreCompact` (`trigger: "auto"`) fire, `toolName` is `undefined`, so `(!toolName || ...)` is `true` and the entire hook group is skipped. None of the four `SessionStart` hooks (`stale_main_session_hook.py`, `compact_spore_session_hook.py`, `ship_teardown.py`, `team_teardown_hook.py`) or the `PreCompact` hook (`precompact_spore_hook.py`) ever run.
- **Evidence:** `saga-hooks.ts:76`, `saga-hooks.ts:160-180`, `plugins/saga/hooks/hooks.json:4-63`.
- **Suggested Fix:** Pass a selector parameter representing `toolName ?? payload.source ?? payload.trigger` to `matchingEntries`.

---

### P2 Findings (Moderate Impact)

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 2 | `scripts/validate_opencode_plugins.py:156` | Crash on plugins lacking `skills` directory | Maintainability, Reliability | 95 | safe_auto -> review-fixer |
| 3 | `scripts/install_opencode_plugins.py:140` | `status` command marks broken symlinks as `OK` | Correctness | 90 | safe_auto -> review-fixer |
| 4 | `tests/` | Missing unit test suite for `validate_opencode_plugins.py` | Testing | 85 | safe_auto -> review-fixer |

#### Finding #2: Validation script crashes if a plugin has no skills directory
- **File:** [`scripts/validate_opencode_plugins.py:156,209`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/scripts/validate_opencode_plugins.py#L156)
- **Why it matters:** Calling `(plugin / "skills").iterdir()` raises `FileNotFoundError` if a future ported plugin does not have a `skills/` directory (e.g., commands-only or hooks-only plugins).
- **Suggested Fix:** Guard directory existence with `(plugin / "skills").is_dir()`.

#### Finding #3: Symlink installer status reports dangling symlinks as OK
- **File:** [`scripts/install_opencode_plugins.py:140`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/scripts/install_opencode_plugins.py#L140)
- **Why it matters:** `Path.is_symlink()` is `True` even for dead or dangling symlinks. Broken links are misreported as `OK`.
- **Suggested Fix:** Check `link.is_symlink() and link.exists()`.

#### Finding #4: No automated unit tests for validate_opencode_plugins.py
- **File:** [`tests/`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/tests/)
- **Why it matters:** The validator is the gating mechanism for plugin compliance, but has no tests verifying violation detection, edge cases, or schema validation.
- **Suggested Fix:** Add `tests/test_validate.py`.

---

### P3 Findings (Low Impact / Polish)

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 5 | `scripts/install_opencode_plugins.py:97` | Installer does not sync existing matching symlinks into state | Reliability | 85 | safe_auto -> review-fixer |
| 6 | `AGENTS.md:17` | Command example uses raw python3 instead of uv run for mypy | Maintainability | 95 | safe_auto -> review-fixer |

#### Finding #5: State file recovery gap on re-install
- **File:** [`scripts/install_opencode_plugins.py:97-107`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/scripts/install_opencode_plugins.py#L97)
- **Why it matters:** If `.infiquetra-plugins.json` is missing but links exist, `install` skips without recording links into `state["links"]`.
- **Suggested Fix:** Append `record` to `state["links"]` if not present when matching link is found.

#### Finding #6: AGENTS.md verification command missing type stubs without uv
- **File:** [`AGENTS.md:17`](file:///Users/jefcox/workspace/infiquetra/infiquetra-opencode-plugins/AGENTS.md#L17)
- **Why it matters:** `python3 -m mypy scripts/` fails without globally installed `types-pyyaml`.
- **Suggested Fix:** Update to `uv run mypy scripts/`.

---

## Coverage and Residual Risks

- **Suppressed Findings:** 0 findings below anchor 75 confidence.
- **Residual Risks:** TypeScript hook bridge `saga-hooks.ts` is executed in opencode's Node runtime; unit testing TypeScript hooks requires a Node/TypeScript test runner or mock harness.
- **Testing Gaps:** Need unit tests for `validate_opencode_plugins.py`.

> **Review Verdict:** BLOCKED on Finding #1 (`saga-hooks.ts` matcher evaluation logic bug). Once Finding #1 is fixed, along with P2 improvements (#2, #3, #4), the codebase will be clean and safe to merge.
