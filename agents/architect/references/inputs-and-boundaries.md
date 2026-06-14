# Inputs and Boundaries

## Inputs you read

1. `AGENTS.md` (your own scope's manifest) — defines who you route to.
2. `.osengineer/state.yml` — current phase, current team, budget used.
3. `.osengineer/handoffs/` — open cross-team or cross-repo handoffs.
4. `planning/active/*/PHASE_PLAN.md` — what work is in flight.
5. (Workbench only) Each repo's `AGENTS.md` to find the right repo.

## What you do NOT read

- Source code under `src/`, `internal/`, `cmd/`, `pkg/` — that's the coding team's domain.
- Test files — that's the testing team's domain.
- Ansible / docker-compose — that's the infra team's domain.

If you need to know "what does function X do," delegate to the researcher agent. Do not read it yourself.
