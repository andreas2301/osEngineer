# ADR-021 Compliance

- `shield-executor` role TTL: 4 hours (enforced by Vault).
- `cert-renew-executors.sh` runs via cron.
- Watchdog verifies renewal succeeded within TTL window.
