---
scope: team
schema_version: 1
team_id: infra
parent_repo: ../
agents: [topology-validator, live-system-operator, cert-monitor, health-verifier]
owns_paths: ["ansible/**", "roles/**", "playbooks/**", "docker-compose*.yml", "Dockerfile*", "scripts/**", ".github/workflows/**"]
reads_paths: ["**/*.yml", "**/Dockerfile", "service-manifest.yml", "contracts/**"]
---

# Infra team

Owns deployment topology, container definitions, ansible roles, CI workflows,
and certificate / secret material. Reads code to validate that declared topology
matches actual producer/consumer behaviour.

## Members

- **topology-validator** — code vs ansible diff; schema consistency
- **live-system-operator** — docker ops, hotfixes, log inspection, AMQP/Vault checks
- **cert-monitor** — expiry tracking, renewal scripts, ADR-021 compliance
- **health-verifier** — container health, metrics endpoints, AMQP consumers

## Escalates to

- **coding** — when an ansible declaration depends on code that doesn't exist yet
  (Observer Shield rule: "Install-guide ahead of services" — declaring topology
  without deployed service code is a silent 100% non-functional install)
- **security** — when adding new secrets, new ports, or new privileged operations
- **docs** — when a service-manifest.yml change requires an ADR amendment

## Hard rules in this team

- ALL ansible / compose edits start with a 4-part plan (Touch / Change / Impact / Rollback)
  per the install-guide CLAUDE.md convention. Pre-bash-guard hook enforces this for
  destructive ops.
- NEVER edit `/opt/sovereign-shield/` directly on the live system — workbench → PR.
  Hotfixes require a backport ticket.
- Cross-UID ownership in bind-mounted trees: root-side git ops MUST chown-back
  `.git/*` to the outer-dir owner or the container-UID reader silently breaks.
- New egress / HTTP client call requires `adr_ref` in service-manifest.yml.
  Red-team-local BLOCKS PRs that introduce egress without the ADR.
