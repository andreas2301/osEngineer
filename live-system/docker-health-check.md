# Runbook: Docker Health Check

## Full System Check

```bash
# All containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Unhealthy only
docker ps --filter health=unhealthy

# Recent restarts (high restart count)
docker ps --format "{{.Names}}: {{.Status}}" | grep -E "Restarting|Exited"
```

## Per-Container Diagnostics

```bash
# Logs
docker logs --tail 50 <container>

# Resource usage
docker stats <container> --no-stream

# Filesystem
docker exec <container> df -h

# Network
docker network inspect net-secure
```

## Recovery Actions

| Symptom | Action |
|---------|--------|
| Container `Restarting` | Check logs, fix config, recreate |
| Container `Unhealthy` | Check healthcheck command, restart |
| Port conflict | Stop conflicting service, remap port |
| Network isolated | Reconnect to correct docker network |
