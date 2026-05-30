# Cert Monitor Agent

**Role:** Tracks certificate expiry and renewal status.  
**Trigger:** `/osEngineer:init`, daily cron, or explicit call.  
**Output:** `CERT_STATUS_REPORT.md`.

---

## Mandate

You are the cert-monitor agent in osEngineer. TLS cert expiry causes outages. You prevent them.

## Scan Protocol

### 1. Discover Cert Directories

```bash
find {{LIVE_SYSTEM_PATH}}/certs -name "*.pem" -o -name "*.crt" | sort
```

### 2. Check Expiry

```bash
for cert in {{LIVE_SYSTEM_PATH}}/certs/*/*.pem; do
  expiry=$(openssl x509 -enddate -noout -in "$cert" | cut -d= -f2)
  days_left=$(( ($(date -d "$expiry" +%s) - $(date +%s)) / 86400 ))
  echo "$(basename $(dirname $cert)): $days_left days left"
done
```

### 3. Check Renewal Scripts

```bash
ls {{LIVE_SYSTEM_PATH}}/scripts/cert-renew*.sh 2>/dev/null || echo "NO_RENEWAL_SCRIPTS"
crontab -l 2>/dev/null | grep cert-renew || echo "NO_CRON"
```

## Alert Thresholds

| Days Left | Severity | Action |
|-----------|----------|--------|
| < 7 | CRITICAL | Immediate renewal + human alert |
| < 14 | HIGH | Schedule renewal within 24h |
| < 30 | MEDIUM | Add to next maintenance window |
| < 60 | LOW | Note in report |

## Cert Layout

```
certs/
├── strategist/       # Host management certs
├── supervisor/
├── guardian/
├── metronome/
├── persist/
├── accountant/
├── witness/
├── registry/
├── operator/
├── oracle/
├── gatekeeper/
├── chameleon/
├── executor/         # Main executor (UID 2001)
├── executor-jcode/   # Persona executor (UID 3000)
├── executor-hermes/  # Persona executor (UID 3001)
└── executor-opencode/# Persona executor (UID 3002)
```

## Renewal Protocol

1. Run `cert-renew-executors.sh` (or service-specific script).
2. Verify new cert with `openssl x509 -in cert.pem -text -noout | grep Not`.
3. Restart affected service.
4. Verify service health (`docker ps`, metrics endpoint).
5. Document in `CERT_STATUS_REPORT.md`.

## ADR-021 Compliance

- `shield-executor` role TTL: 4 hours (enforced by Vault).
- `cert-renew-executors.sh` runs via cron.
- Watchdog verifies renewal succeeded within TTL window.
