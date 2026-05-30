---
scope: team
schema_version: 1
team_id: docs
parent_repo: ../
agents: [tech-writer]
owns_paths: ["docs/**", "README*.md", "**/*.openapi.yaml", "contracts/**", "**/*.schema.json", "**/service-manifest.yml", "**/message-contract*.yaml"]
reads_paths: ["**"]
---

# Docs team

Owns all contract surfaces: OpenAPI specs (for the few HTTP /metrics & /healthz
endpoints), AMQP message contracts, service manifests, JSON Schemas, ADRs, and
prose documentation. Authors the *contract first*, before any production code
is written that uses it.

## Members

- **tech-writer** — contract-first author; ADR amendments; OpenAPI / message
  contract authoring; doc-first gate enforcement

## Escalates to

- **coding** — when a contract change requires updating producer or consumer code
- **infra** — when a contract change requires an ansible topology amendment
- **security** — when a contract introduces new exposed surface

## Hard rules in this team

- No production code without a preceding contract. If a developer starts writing
  code that touches a contract surface (`contracts/`, `api/`, `service-manifest.yml`)
  and the contract doesn't exist, the developer agent STOPS and routes to this team.
- Contracts are append-only-optional: adding fields is safe, removing or renaming
  fields breaks downstream tooling. Red-team-architect BLOCKS PRs that violate this.
- For this project: service-to-service comms are configured in the META repo ADRs. The doc-first
  artifact for inter-service is `message-contract.yaml`, NOT OpenAPI.
  OpenAPI applies to the small HTTP surface (/metrics, /healthz) only.
- Every new exchange / routing key / queue declared in install-guide ansible
  MUST have a matching `contracts/produced/MC-*.yaml` AND a matching
  `contracts/consumed/MC-*.yaml` for each subscribing service.
