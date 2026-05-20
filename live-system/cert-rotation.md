# Runbook: ADR-021 Certificate Rotation

## Detection

```bash
for cert in /opt/<project>/certs/*/*.pem; do
  days=$(( ($(openssl x509 -enddate -noout -in "$cert" | cut -d= -f2 | date -f - +%s) - $(date +%s)) / 86400 ))
  echo "$(basename $(dirname $cert)): $days days"
done
```

## Rotation

1. Run renewal script:
   ```bash
   /opt/<project>/scripts/cert-renew-<service>.sh
   ```

2. Verify new certs:
   ```bash
   openssl x509 -in /opt/<project>/certs/<service>/cert.pem -noout -text | grep Not
   ```

3. Restart affected services:
   ```bash
   docker compose restart <service-1> <service-2> <service-3>
   ```

4. Verify health:
   ```bash
   docker ps | grep -E "<service-1>|<service-2>|<service-3>"
   ```

## Watchdog

The renewal cron runs automatically. If it fails, the watchdog alerts via journald.
