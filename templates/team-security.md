---
scope: team
schema_version: 1
team_id: security
parent_repo: ../
agents: [red-team-local, red-team-architect]
owns_paths: [".github/codeql/**", "security/**", ".secretscanignore", ".base64scanignore"]
reads_paths: ["**"]
---

# Security team

Owns SAST configuration, secret-scan allowlists, and cross-cutting security
invariants. Reads everything; writes very little — most of the team's output is
PR-time pass/fail verdicts on other teams' work.

## Members

- **red-team-local** — per-PR security scan: SAST findings, secrets, base64
  blobs, allowlist enforcement, dependency CVEs
- **red-team-architect** — cross-repo invariant checks: topology drift, ADR
  violations, SOLID-wall enforcement, contract drift between producer and
  consumer

## Escalates to

- **coding** — when a code change introduces a vulnerability class (SQL
  injection, command injection, XSS, prompt injection)
- **infra** — when a deployment change introduces a privilege-escalation
  vector or exposes a new port
- **docs** — when a contract change introduces a new untrusted-input surface
  that needs threat-modelling

## Hard rules in this team

- `InsecureSkipVerify: true` is FORBIDDEN in production code. Red-team-local
  BLOCKS PRs that introduce it. See memory: `fail-closed-on-tls-error`.
- New HTTP egress requires an ADR amendment. Red-team-local BLOCKS PRs that
  add `http.Get` / `http.Post` / `httpx.AsyncClient` / `requests.get` without
  a matching `adr_ref` in service-manifest.yml.
- Service-to-service HTTP is FORBIDDEN in Observer Shield. AMQP only.
  Red-team-architect BLOCKS PRs that introduce inter-service HTTP.
- Secrets in env vars only, sourced from Vault. Never literal in code, ansible,
  compose, or test fixtures. Secret-scan blocks commits with literal secrets.
