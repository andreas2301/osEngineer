# Routing Protocol

## Routing protocol (repo scope)

For every incoming task or user prompt, decide which team it belongs to using this priority:

1. **Match by owns_paths.** If the task mentions a file path, find the team whose `owns_paths` glob matches. Route to that team's agents (`developer`, `qa`, `topology-validator`, etc.).
2. **Match by classification.** If the task is `fix` or `feature` of code → coding. If `test coverage` → testing. If `docker-compose`, `ansible`, `port`, `volume` → infra. If `OpenAPI`, `README`, `ADR` → docs. If `secret`, `SAST`, `dependency CVE` → security.
3. **Multi-team task.** Decompose into per-team subtasks. Open a handoff for each.
4. **Cannot decide?** Ask the user. NEVER guess on a multi-team task.

## Routing protocol (workbench scope)

For every cross-repo task:
1. **Find the right repo** by reading the workbench `repos:` list and each repo's `AGENTS.md` to learn its `project_classification` and team composition.
2. **Invoke the repo's architect** by writing `<workbench>/.osengineer/handoffs/XR-<n>-<slug>.md` naming the target repo.
3. **Block until the cross-repo handoff closes.**
