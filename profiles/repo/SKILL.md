---
name: osengineer-repo-profile
description: Investigate, plan, implement, verify, or resume repository coding tasks with scoped context and evidence. Use for repository development and dispatch workflows; supports local sessions and explicit headless task contracts. Do not use for unrelated projects or autonomous production operations.
---

# Repo profile coding

The selected coding session owns the task. Read the target repository's policy file (setting `policy` in `.osengineer/profile.json`, default `POLICY.md`); it alone owns policy. Resolve available repository skills from the skill registry (setting `skillRegistry`, default `.osengineer/skill-registry.json`). This skill supplies a portable execution adapter, not another backlog, reviewer, rule catalog or source of product truth.

## Select the needed mode

- **Investigate:** read only the affected domain and consumers. Return findings with file/line evidence and unresolved gaps. No worktree or tracker mutation for a read-only explanation.
- **Plan:** define the observable outcome, scope, existing canonical domain and consumers, acceptance commands and blockers. Use the issue body and existing artifacts in the configured plan directory (setting `planDirectory`, default `.plans/`). Do not create root `planning/` or a second store.
- **Implement:** use the repository's dispatch workflow route when work selection or delivery state needs it. Preserve explicit user scope. Verify ownership and use the repository's worktree procedure for writers. Keep coupled implementation and final verification in the owner session.
- **Resume:** read the compact handoff, then re-read volatile issue/PR/HEAD evidence. A handoff annotates current state; it never proves ownership, priority or readiness.

For a bounded change, proceed directly with focused verification. For an existing domain, preserve the repository inventory's consumers, thresholds and trust boundaries. Delegate only bounded independent reads or isolated writers when authorized; do not add delivery reviewer, verifier or judge agents. Existing CI and human review remain the delivery path.

## Load only what changes the decision

Read one relevant repository skill phase and exact code or ADR excerpts. Fetch external context only when the task needs it; keep complete bulk evidence in local artifacts and return compact rows with completeness and timestamps. Unknown or truncated coverage cannot establish absence. Do not preload historical plans, generic roles, all MCP schemas or the whole board for a selected task.

- For local installation, runner invocation or task-contract preparation, read [execution](references/execution.md).
- For GitHub, Linear, Notion, secret injection or diagnostic capabilities, read [integrations](references/integrations.md).
- When preserving a usage failure or comparing profile versions, read [learning](references/learning.md).

## Verify and return

Run the acceptance checks on the final code state. Report actual pass, fail and not-run results with the result SHA, scope changes, blockers and next action. A hook warning, schema-valid handoff or successful model exit is not implementation evidence. Stop at required human decisions and name the missing action. Do not push, merge, publish, deploy or write trackers unless the current request and repository policy authorize it.

Record actionable learning without altering the executing skill. Propose narrow improvements from observed failures; use the repository's existing evaluation scripts for behavioral comparison.
