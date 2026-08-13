---
description: "Strict read-only cross-source fleet audit \u2014 leaked resources, unledgered\
  \ spawns, receiptless delegations, evidence errors. Reports and exits; never repairs.\
  \ Arguments: [--repo-root PATH] [--lease-store PATH] [--audit-store PATH] [--format\
  \ text|json] [--show-local-paths]"
---


Use the skill tool to load the `fleet-doctor` skill (name: `fleet-doctor`), then follow its instructions. and run one point-in-time fleet audit.

Run `python3 ${SAGA_PLUGIN_ROOT}/scripts/fleet_doctor.py` with the operator's arguments. The doctor
independently correlates Git worktree state, the outcome worktree registries, the retired #356 broker
registry (deleted #677/U7, always absent), the chain-verified #351 run-fact ledger, outcome dispatch commit events, and the
durable delegation audit store into `fleet_doctor_report.v1` — three disease classes
(`leaked-resource`, `unledgered-spawn`, `receiptless-delegation`) plus explicit evidence
errors.

Exit 0 is a complete scan with zero findings and zero evidence errors; exit 1 is a complete
scan with disease findings; exit 2 is incomplete proof (config error, corrupt/unsafe evidence,
broken chain, capacity overflow, or a source changing mid-scan). The run-facts verdict
`verified-prefix` is deliberately named: the hash chain proves the surviving prefix, and
whole-record trailing truncation is undetectable by design. Findings name the owning
recovery surface (`/outcome status` — worktree reclamation, B8 `status/recover`,
`/delegation-audit`; lease-broker `inspect` retired #677/U7) — the doctor never repairs, settles, retries, releases, reaps, or removes
anything, and there is no `--fix`, `--watch`, or fixture mode.

Treat `$ARGUMENTS` as fleet_doctor.py CLI arguments.

`$ARGUMENTS`
