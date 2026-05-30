# Runbook: Emergency Vault Unseal

## Detection

Vault is sealed when:
```bash
curl -s http://127.0.0.1:8200/v1/sys/health | jq '.sealed'
# Returns: true
```

## Procedure

1. Locate unseal keys: `/root/vault_unseal_keys.txt` (or secure offline backup).
2. Run unseal (requires 3 of 5 keys):
   ```bash
   vault operator unseal <key-1>
   vault operator unseal <key-2>
   vault operator unseal <key-3>
   ```
3. Verify:
   ```bash
   vault status
   # Should show: Sealed: false
   ```

## Post-Unseal

1. Verify all services can read secrets (restart if needed).
2. Check cert renewal cron is still active.
3. Document incident in `memory/retrospectives/`.
