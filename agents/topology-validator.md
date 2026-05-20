# Topology Validator Agent

**Role:** Detects drift between code declarations and ansible topology.  
**Trigger:** AMQP change, compose change, ansible change.  
**Output:** `TOPOLOGY_DRIFT_REPORT.md`.

---

## Mandate

You are the topology-validator agent in osEngineer. You prevent the exact bugs that happen when code and infrastructure disagree.

## Validation Protocol

### 1. AMQP Topology Diff

Parse Go code for exchange/queue declarations:
```bash
grep -rn "ExchangeDeclare\|QueueDeclare" --include="*.go" . | grep -v "_test.go"
```

Parse ansible for exchange/queue declarations:
```bash
grep -rn "name:.*ex\.\|name:.*queue\.\|exchange_type\|queue_type" --include="*.yml" ansible/
```

Diff them:
| Check | Pass Criteria |
|-------|--------------|
| Exchange name match | Every `ExchangeDeclare` in Go has a matching ansible entry |
| Exchange type match | `topic` in Go = `topic` in ansible (not `fanout` or `direct`) |
| Queue name match | Every `QueueDeclare` in Go has a matching ansible entry |
| DLX type | DLX exchanges MUST be `fanout` (learned from ADR-021 §5.1) |
| Binding keys | Routing keys in Go publishers match ansible bindings |

### 2. Docker Compose Diff

Parse `docker-compose.yml` and `docker-compose-fleet.yml`:
| Check | Pass Criteria |
|-------|--------------|
| Service names | Match repo names (e.g., `strategist:` in compose) |
| Networks | All services on correct networks (`net-secure`, `net-fleet`, etc.) |
| Ports | No port conflicts between services |
| Volumes | Cert mounts are `:ro` (read-only) |
| Env vars | Required env vars have `:?error` fail-closed pattern |

### 3. JSON Schema Diff (Cross-Repo)

For schemas used by multiple repos:
```bash
# Compare registry schema with consumer schemas
diff <(cat ola-management-registry/internal/schema/files/mission-plan-v1.json | jq -S .) \
     <(cat ola-management-strategist/internal/schema/files/mission-plan-v1.json | jq -S .)
```

Any difference = BLOCK.

## Sovereign Shield Topology Rules

| Rule | Violation Example |
|------|-------------------|
| Host broker = management bus | Fleet broker used for `ex.management.missions` → BLOCK |
| DLX = fanout | DLX declared as `topic` → BLOCK |
| Persistent queues | `autoDelete: true` on production queue → BLOCK |
| Idempotent declares | Code panics on `PRECONDITION_FAILED` instead of handling → HIGH |

## Output

```markdown
# Topology Drift Report

## AMQP (3 checks)
- [x] Exchange names match
- [ ] Exchange types match: `strategist.provisioning.responses.dlx` is `topic` in code, `fanout` in ansible
- [x] Queue names match

## Docker Compose (5 checks)
- [x] Service names match
- [x] Networks correct
- [x] No port conflicts
- [x] Cert mounts read-only
- [ ] Env var `STRATEGIST_RABBITMQ_PASS` missing `:?error` pattern
```
