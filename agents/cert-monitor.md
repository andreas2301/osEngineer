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
find /opt/<project>/certs -name "*.pem" -o -name "*.crt" | sort
```

### 2. Check Expiry

```bash
for cert in /opt/<project>/certs/*/*.pem; do
  expiry=$(openssl x509 -enddate -noout -in "$cert" | cut -d= -f2)
  days_left=$(( ($(date -d "$expiry" +%s) - $(date +%s)) / 86400 ))
  echo "$(basename $(dirname $cert)): $days_left days left"
done
```

### 3. Check Renewal Scripts

```bash
ls /opt/<project>/scripts/cert-renew*.sh 2>/dev/null || echo "NO_RENEWAL_SCRIPTS"
crontab -l 2>/dev/null | grep -E "cert|renew" || echo "NO_CRON"
```

## Alert Thresholds

| Days Left | Severity | Action |
|-----------|----------|--------|
| < 7 | CRITICAL | Immediate renewal + human alert |
| < 14 | HIGH | Schedule renewal within 24h |
| < 30 | MEDIUM | Add to next maintenance window |
| < 60 | LOW | Note in report |

## Cert Layout Discovery

Discover cert directories dynamically:

```bash
find /opt/<project>/certs -maxdepth 1 -type d | sort
```

Map each directory to its service in your local runbook.

## Renewal Protocol

1. Run the appropriate `cert-renew-*.sh` script (or service-specific script).
2. Verify new cert with `openssl x509 -in cert.pem -text -noout | grep Not`.
3. Restart affected service.
4. Verify service health (`docker ps`, metrics endpoint).
5. Document in `CERT_STATUS_REPORT.md`.

## ADR-021 Compliance

- Vault role TTL should be short (e.g., 4 hours) and enforced.
- Cert renewal scripts run via cron.
- Watchdog verifies renewal succeeded within TTL window.
