---
scope: team
schema_version: 1
team_id: coding
parent_repo: ../
agents: [developer, reviewer]
owns_paths: ["internal/**", "cmd/**", "pkg/**", "src/**"]
reads_paths: ["api/**", "contracts/**", "ansible/**", "docs/**"]
---

# Coding team

Owns production code. Implements features and fixes under strict TDD
(red → green → refactor → atomic commits). Reads — but does not edit —
infrastructure config, contracts, and docs.

## Members

- **developer** — primary implementer; writes code, tests, commits
- **reviewer** — per-PR review; style, correctness, test coverage

## Escalates to

- **testing** — when a new behaviour needs corresponding test coverage
- **infra** — when a deployment-config change is required to ship code
- **docs** — when an API or contract surface changes
- **security** — when handling secrets, auth, or input from untrusted sources

## Hard rules in this team

- No production code without a preceding red test commit in the same branch.
- No edits to `ansible/`, `docker-compose*.yml`, `roles/` — open a handoff to **infra**.
- No edits to `contracts/`, `*.openapi.yaml`, `*.schema.json` — open a handoff to **docs**.
- `OSE_BYPASS=1` only with an audit-logged justification.
