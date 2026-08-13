# AGENTS.md

## Purpose

`infiquetra-opencode-plugins` is the opencode-native adapter repo for selected Infiquetra
Claude Code plugins. It is **not** a full mirror of `infiquetra-claude-plugins`; it carries
the opencode-ready plugin surface (currently `saga` as the proof port). See
[README.md](README.md) for the surface/version table and layout.

## Commands

```bash
python3 scripts/validate_opencode_plugins.py
python3 scripts/install_opencode_plugins.py status
python3 -m pytest
python3 -m ruff check .
python3 -m mypy scripts/
```

`scripts/validate_opencode_plugins.py` checks every ported plugin against its
`manifest.json` contract (inventory matches disk, skill/command/agent shape rules, skill-name
uniqueness across plugins, hook-bridge deferred-set agreement, no leaked source artifacts).
Run it before opening a PR.

## Repo-Specific Rules

- The Claude-to-opencode port runbook at
  `docs/portability/claude-to-opencode-plugin-port-runbook.md` is mandatory for every new
  import or refresh. The machine contract is the per-cycle JSON under `docs/portability/ports/`;
  `plugins/<name>/manifest.json` is the installed-plugin contract.
- **The port is mechanical, the review is not.** `scripts/port_plugin.py` produces the ported
  surface; a human (or an agent acting under the runbook) must review the diff, classify each
  hook bridge mapping, update `docs/portability/matrix.md` and `plugins/<name>/PORTABILITY.md`,
  then install and validate.
- **Adapter-native artifacts live under `plugins/<name>/opencode/`** (hook bridges,
  `hook-manifest.json`). The port tool regenerates everything else and never touches them.
- **Port behavior, not host-shaped files.** A plugin version records exposed, tested opencode
  behavior and its lineage; it does not assert byte parity with the Claude source.
- Hook bridges follow the Claude exit-code protocol (0 continue, 1/2 block) and the bridge's
  `DEFERRED_HOOKS` list must match `manifest.json` `hooks.deferred` — the validator enforces it.
- Skill names must stay unique across all ported plugins: opencode installs skills into a flat
  directory keyed by name.
