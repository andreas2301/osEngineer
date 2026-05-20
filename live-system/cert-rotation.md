# Runbook: ADR-021 Certificate Rotation

## Detection

```bash
for cert in /opt/sovereign-shield/certs/*/*.pem; do
  days=$(( ($(openssl x509 -enddate -noout -in "$cert" | cut -d= -f2 | date -f - +%s) - $(date +%s)) / 86400 ))
  echo "$(basename $(dirname $cert)): $days days"
done
```

## Rotation

1. Run renewal script:
   ```bash
   /opt/sovereign-shield/scripts/cert-renew-executors.sh
   ```

2. Verify new certs:
   ```bash
   openssl x509 -in /opt/sovereign-shield/certs/strategist/cert.pem -noout -text | grep Not
   ```

3. Restart affected services:
   ```bash
   docker compose restart strategist supervisor guardian
   ```

4. Verify health:
   ```bash
   docker ps | grep -E "strategist|supervisor|guardian"
   ```

## Watchdog

The renewal cron runs automatically. If it fails, the watchdog alerts via journald.
