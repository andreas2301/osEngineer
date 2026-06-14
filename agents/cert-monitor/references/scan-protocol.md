# Scan Protocol

## 1. Discover Cert Directories

```bash
find {{LIVE_SYSTEM_PATH}}/certs -name "*.pem" -o -name "*.crt" | sort
```

## 2. Check Expiry

```bash
for cert in {{LIVE_SYSTEM_PATH}}/certs/*/*.pem; do
  expiry=$(openssl x509 -enddate -noout -in "$cert" | cut -d= -f2)
  days_left=$(( ($(date -d "$expiry" +%s) - $(date +%s)) / 86400 ))
  echo "$(basename $(dirname $cert)): $days_left days left"
done
```

## 3. Check Renewal Scripts

```bash
ls {{LIVE_SYSTEM_PATH}}/scripts/cert-renew*.sh 2>/dev/null || echo "NO_RENEWAL_SCRIPTS"
crontab -l 2>/dev/null | grep cert-renew || echo "NO_CRON"
```
