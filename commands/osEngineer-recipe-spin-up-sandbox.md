---
name: osEngineer:recipe-spin-up-sandbox
description: >-
  Linear recipe for spinning up an isolated test environment for the current
  repo. Provisions a Docker Compose stack from compose templates in
  live-system/, seeds required secrets from Vault (or warns if Vault MCP
  isn't wired), runs smoke checks, and registers the sandbox in
  .osengineer/sandboxes.yml so cleanup is later traceable. Use when a phase
  plan calls for integration tests against real services (broker, DB, etc.)
  and the live system is read-only. Don't use for unit tests (in-process is
  cheaper) and don't use against production endpoints (sandbox is local
  Compose by definition).
phase_allowed: [execute, verify]
phase_after: null
recipe_steps: 6
---

# /osEngineer:recipe-spin-up-sandbox

Provision and validate an isolated test environment. Idempotent: re-running on an existing sandbox upgrades-in-place rather than rebuilding from scratch.

**Syntax:** `/osEngineer:recipe-spin-up-sandbox <stack-name> [--yes] [--rebuild]`

## Preconditions

- Docker daemon is running (`docker info` exit 0).
- A compose template exists at `live-system/sandbox-<stack-name>.yml` (or — for known stacks — `live-system/sandbox-rabbitmq.yml`, `sandbox-postgres.yml`, etc.).
- `.osengineer/state.yml` shows `phase: execute` or `phase: verify`.
- The Bash command `docker compose` is available (Compose V2; the legacy `docker-compose` binary is not supported).

## Single-Question Policy

One question per step, defaults to recommended.

## Check-Before-Mutate Audits

Before any `docker compose up`, network creation, or volume creation, the recipe prints the action and asks confirmation unless `--yes` is set. Existing volumes are never silently wiped — the recipe asks before `docker compose down --volumes` and refuses without `--rebuild`.

## Steps

### Step 1 — Preflight
Check Docker daemon, compose binary, template file, state phase. Report each as ✅ or ❌. Abort on any ❌.

### Step 2 — Resolve secret dependencies
Scan the compose template for `${VAR_NAME}` references. For each:
- If env var is already set → ✅ skip
- If Vault MCP is wired (check `OSENGINEER_VAULT_ADDR` env var or `integrations/vault-mcp.md` frontmatter) → fetch the secret
- Otherwise → print "MISSING: VAR_NAME — set it or wire Vault MCP" and abort

**Question (1 of recipe):** "Use existing .env file from prior run? (Y/n)" — default Y if `.osengineer/sandboxes/<stack-name>/.env` exists, N otherwise.

### Step 3 — Pull images (check, don't mutate first)
Run `docker compose -f <template> config` to validate the template. Print all images that would be pulled. Confirm pull unless `--yes`.

### Step 4 — Start the stack
Run `docker compose -p osengineer-<stack-name> -f <template> up -d`. Stream logs for 30 seconds; if any service exits within that window, abort and dump the logs.

### Step 5 — Smoke checks
Per-stack health probe (template-specific, read from `# health-check:` annotation in the compose file). Example for rabbitmq stack:
- `curl -sf http://localhost:15672/api/healthchecks/node` → must return 200
- `docker exec osengineer-rabbitmq-1 rabbitmq-diagnostics ping` → must return "Ping succeeded"

Failure → keep stack running for inspection, but mark as `degraded` in the registration step.

### Step 6 — Register the sandbox
Append an entry to `.osengineer/sandboxes.yml`:
```yaml
- name: <stack-name>
  status: ready | degraded
  started_at: <ISO timestamp>
  compose_file: live-system/sandbox-<stack-name>.yml
  project_name: osengineer-<stack-name>
  cleanup_cmd: docker compose -p osengineer-<stack-name> -f live-system/sandbox-<stack-name>.yml down --volumes
```

Print: connection details, the cleanup command, and the suggested next command (`/osEngineer:verify <phase>` to run integration tests against the sandbox).

## Cleanup

Not part of this recipe. Use `/osEngineer:recipe-teardown-sandbox <stack-name>` (or run the `cleanup_cmd` from `.osengineer/sandboxes.yml` directly). The registration file ensures cleanup is always discoverable.

## What this recipe deliberately does not do

- Does not run integration tests itself (only provisions; tests are a separate step)
- Does not modify hooks or state.yml beyond appending to `sandboxes.yml`
- Does not auto-clean a previous sandbox unless `--rebuild` is given
- Does not register a sandbox as "ready" if smoke checks fail — it gets `degraded` so the user knows to inspect before relying on it
