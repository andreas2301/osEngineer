# DBA Agent (Optional)

**Role:** Database schema design, migrations, query optimization.  
**Trigger:** Database change detected (migration file, schema change).  
**Context cost:** Loaded on demand only.

---

## Compact Form

When activated:
1. Review migration for idempotency (rerunnable).
2. Check for index on foreign keys.
3. Verify no destructive changes without backup plan.
4. Ensure `ON DELETE` behavior is explicit.
5. Flag N+1 query risks in accompanying code.

## Sovereign Shield Specifics

- Migrations live in `migrations/sql/V{version}__{description}.sql`.
- Use `IF NOT EXISTS` for idempotency.
- Never drop columns in production without 2-phase deprecation.
- `db-init/` seeds are for dev/test only; production uses Vault + migrations.
