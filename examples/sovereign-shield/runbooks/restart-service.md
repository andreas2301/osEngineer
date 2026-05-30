# Runbook: Restart a Service

## Pre-checks

1. Check current status: `docker ps | grep <service>`
2. Check logs for errors: `docker logs --tail 20 <container>`
3. Note any in-flight operations (AMQP consumers, active missions).

## Restart

```bash
# Graceful restart
docker compose restart <service>

# Or full recreate (if config changed)
docker compose up -d --force-recreate <service>
```

## Post-checks

1. `docker ps | grep <service>` — Status must be `(healthy)` or `(up)`.
2. `wget -qO- http://localhost:<port>/health` — Must return `ok`.
3. `wget -qO- http://localhost:<port>/metrics | grep <service>_` — Must show custom metrics.
4. Check AMQP consumers: `rabbitmqctl list_consumers | grep <service>`.

## Rollback

If restart fails:
```bash
docker compose stop <service>
docker start <container>  # Reverts to previous state
docker logs <container>   # Check why it failed
```
