# Verification Protocol

## 1. Container Health

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep ola-
```

Status must be `(healthy)` not just `(up)`.

## 2. Metrics Endpoint Check

For each service with a metrics port:
```bash
wget -qO- http://localhost:<port>/metrics | grep -E "<service_name>_" | head -5
```

Must return CUSTOM metrics (not just Go runtime). If only `go_` metrics → service has not incremented any counters yet.

## 3. AMQP Consumer Check

```bash
# List consumers per queue
rabbitmqctl list_consumers | grep -E "strategist\.|supervisor\.|mission"

# Check queue depth (should be near 0 in steady state)
rabbitmqctl list_queues name messages | grep -E "strategist\.|supervisor\.|mission"
```

## 4. API Health Checks

```bash
# HTTP health endpoints
curl -sf http://localhost:8080/health || echo "FAIL: strategist health"
curl -sf http://localhost:8080/health || echo "FAIL: supervisor health"
```

## 5. Vault Connectivity

```bash
curl -sf http://127.0.0.1:8200/v1/sys/health | jq -e '.sealed == false' || echo "FAIL: Vault sealed"
```
