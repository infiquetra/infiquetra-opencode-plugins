# Adapter CI

`Adapter CI` adds one Linux job, `Adapter validation (Python 3.12)`, for pull
requests and pushes to `main`. Repository permissions are read-only, checkout
credentials are not persisted, and actions are pinned to immutable commits.
Only replaced runs for the same identified PR and workflow ref cancel; missing PR
identity and non-PR runs use independent run-ID/attempt groups without cancellation.
This remains an actively maintained source-of-truth adapter, as described in
the README; the proof-port label does not imply retirement.

Every run uses uv 0.13.6 to create a fresh Python 3.12 environment and install
the existing lock with `uv sync --locked --python 3.12`. It then executes the
real plugin validator, the complete configured pytest suite once, `ruff check .`
and exactly `mypy scripts/`. No test selection or assertion changes accompany
the gate. The preflight rejects missing/empty project or lock files and an
empty manifest set; pytest retains its normal empty-collection failure.

The validator preserves disk/inventory parity, flat skill-name uniqueness,
deferred bridge/manifest agreement and leaked-source rejection. Installer,
transform, validator and both bridge/runtime test modules remain configured.
The latter two retain their existing conditional skips when Bun or OpenCode 2
is absent. CI does not install either host or configure providers; a green
source gate with those skips is not host compatibility evidence. Host acceptance
remains a targeted release obligation. Tests use isolated homes and fixtures;
the gate also supplies an empty home and XDG directories rather than installing
into a user's OpenCode configuration.

The uv cache is limited to a runner-temporary dependency cache: package data,
metadata and source-built wheels can be archived. It excludes `.venv`, managed
Python installations, adapter/source oracles, home and authentication config.
Lockfile, platform, uv version and Python policy distinguish cache entries;
setup-uv determines the key's interpreter identity before the later explicit
Python install, so that key does not attest the eventual interpreter patch.
Fresh locked installation and every command execute on cache hits. GitHub PR-ref
isolation and the absence of privileged or release consumers bound cache reuse.
No runtime fixture download or moving upstream oracle is introduced.

The job deadline is ten minutes; bootstrap has three minutes, pytest and mypy
two each, and other commands one. Local command timings qualify these command
bounds only; cold/warm hosted bootstrap and total job headroom still need
measurement. Bash's `-e -o pipefail` preserves failures through diagnostic tees.
JUnit preserves case outcomes and skips; missing JUnit after a successful pytest
command is fatal. Up to six 64 KiB log tails and a job-status note accompany it in
a seven-day artifact attempted even on failure. The status note can survive early
bootstrap failure without pretending tests ran. Upload failures or a wholly missing
artifact fail the job; runner loss or force cancellation can prevent retention.
No environment dump, home or plugin
installation is uploaded. This adds compute; it makes no savings claim.

The local receipt records measured command times and every collected case outcome.
Existing source/tooling failures remain fatal; fixes require a separately owned
prerequisite rather than test skips, bundled-payload edits or relaxed validation.

## Neutral fixture follow-up

There is already a versioned neutral producer: the Claude Saga contract
`plugins/saga/references/outcome-cross-runtime.md` and six JSON examples under
`tests/fixtures/outcome-cross-runtime/v1/`. The Codex adapter owns a direct-port
cycle and consumes the same fixture bytes in its golden round-trip and rejection
tests. The OpenCode adapter bundles the contract reference but carries none of
those fixtures and has no corresponding consumer tests in its five modules.

That overlap is a concrete reuse candidate, not authorization to transfer
runtime implementations or silently refresh this adapter's lineage. A separate
port cycle must select the producer revision and fixture digests, classify the
OpenCode consumer behavior, record custody, and add adapter-owned conformance
tests. The existing producer owns the contract and fixture vocabulary; OpenCode owns
its pinned consumer and port-cycle evidence. Confirm the producer revision and
published fixture digests before that consumer work; no new producer platform is
needed. Keep native installer and hook execution tests alongside shared inputs.
Frontmatter, tool/path rewriting and host-hook mapping expectations also remain
adapter-owned. No new central platform or fixture download is needed for this
gate, and adding it alone does not complete the neutral-fixture recommendation.

Root owns review, hosted cold/warm qualification and observed required-check
enforcement after a green candidate. This workflow does not change repository
settings, publish artifacts for release consumption or prove host acceptance.
Rollback removes this workflow and note; runtime, manifests, lock, lineage and
existing tests retain their bytes.
