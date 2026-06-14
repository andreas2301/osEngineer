# Validation Protocol

## 1. AMQP Topology Diff

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

## 2. Docker Compose Diff

Parse `docker-compose.yml` and `docker-compose-fleet.yml`:

| Check | Pass Criteria |
|-------|--------------|
| Service names | Match repo names (e.g., `strategist:` in compose) |
| Networks | All services on correct networks (`net-secure`, `net-fleet`, etc.) |
| Ports | No port conflicts between services |
| Volumes | Cert mounts are `:ro` (read-only) |
| Env vars | Required env vars have `:?error` fail-closed pattern |

## 3. JSON Schema Diff (Cross-Repo)

For schemas used by multiple repos:
```bash
# Compare registry schema with consumer schemas
diff <(cat <registry-repo>/internal/schema/files/plan-v1.json | jq -S .) \
     <(cat <producer-repo>/internal/schema/files/plan-v1.json | jq -S .)
```

Any difference = BLOCK.
