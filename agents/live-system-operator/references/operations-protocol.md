# Operations Protocol

## 1. Service Restart

```bash
# Pre-check: get current state
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep ola-

# Restart with healthcheck
docker compose restart <service>
sleep 5
docker ps | grep <service>  # Must show (healthy) or (up)

# Post-check: verify metrics endpoint
wget -qO- http://localhost:<metrics_port>/metrics | grep -E "custom_metric|error"
```

## 2. Hotfix (Live → Backport)

1. **Identify severity:** Outage or security incident = hotfix allowed.
2. **Apply fix in {{LIVE_SYSTEM_PATH}}:** Direct edit with rollback note.
3. **Restart affected service:** Verify health.
4. **Document:** Write `HOTFIX.md` with:
   - What was changed
   - Why it was urgent
   - Rollback command
   - Commit hash to cherry-pick into workbench
5. **Backport:** Create workbench branch and cherry-pick the hotfix.

## 3. Log Inspection

```bash
# Docker logs
docker logs --tail 100 <container> 2>&1 | grep -i "error\|fatal\|panic"

# Journal logs
journalctl -u <service>.service --no-pager -n 50

# Application logs (structured JSON)
cat /var/log/{{PROJECT_NAME}}/<service>/*.log | jq 'select(.level=="error")'
```

## 4. AMQP Topology Verification

```bash
# List exchanges
rabbitmqctl list_exchanges name type durable | grep -E "ex\.|management"

# List queues
rabbitmqctl list_queues name messages consumers | grep -E "strategist\.|supervisor\.|mission"

# Check bindings
rabbitmqctl list_bindings source_name destination_name routing_key | grep -E "ex\.management|mission"
```

## 5. Vault Status Check

```bash
# Is Vault sealed?
curl -s http://127.0.0.1:8200/v1/sys/health | jq '.sealed'

# List active tokens
vault token lookup 2>/dev/null || echo "Vault not authenticated"
```
