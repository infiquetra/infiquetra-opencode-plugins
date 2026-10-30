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

## Neutral fixture conformance

The [fixture-only cycle](portability/ports/2026-10-30-saga-outcome-cross-runtime-fixtures.json)
pins six unchanged Claude-owned `outcome-cross-runtime/v1` fixtures to
`972cc50ba8799d8d4663b893e008bb1bf318d4d7`, the bundled Saga lineage. OpenCode owns
`tests/test_outcome_cross_runtime.py`; Codex retains ownership of its own consumer.
No fixture download or moving upstream oracle is used in CI.

The new module contributes exactly six cases: four original-byte canonical round trips
through the bundled parser, validators and serializer, an unknown-field structural
rejection, and a structurally valid future-version negotiation rejection. Discovery
also asserts successful version-1 negotiation. Its isolated module loader restores
import state. The existing 24 cases and host-dependent skips are unchanged; the full
hosted candidate must collect all 30. Installer protection, transforms, inventory and
hook execution assertions remain adapter-owned.

The callable contract seam already existed. The CLI still has no peer-envelope ingress,
and golden fixtures do not prove negotiation at a host boundary, authority transfer,
protected handoff execution or host compatibility. Manifest, version, lineage, runtime,
lock and workflow/cache policy are unchanged. Regeneration and installed-host restart
are not applicable to this test-data cycle and are not claimed as executed.

Root owns review, full hosted validation of the new candidate and observed required-check
enforcement. The fixture-only change needs no additional controlled cache warm-up run.
Rollback of this cycle removes its six fixtures, test module and machine record and
restores its four documentation changes. It preserves the existing workflow and original
tests; completing the broader recommendation remains a separate acceptance decision.
