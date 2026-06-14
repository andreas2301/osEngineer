# Output Format

```markdown
# Architectural Audit — Phase phase-XXX

## Invariant Violations (0)
(None found)

## Topology Drift (1)
- **Repo:** <management-service-repo>
- **File:** `internal/api/amqp_mission_publisher.go:45`
- **Drift:** Exchange `ex.management.missions` declared as `topic` in code, but ansible declares `direct`
- **Fix:** Align code with ansible (topic is correct per ADR-018)

## Warnings (2)
- New schema `retry-policy-v1.yaml` not yet in registry allowlist
- `<persistence-repo>` added Docker volume not declared in ansible
```
