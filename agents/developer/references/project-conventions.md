# Project-Specific Conventions

Your project may define additional constraints in its META repo ADRs or team manifests. Common examples include:

- **Fail-closed:** Any init error (TLS, AMQP, Vault) logs WARN and disables the feature. Do not panic.
- **Prometheus metrics:** Use `promauto` on default registry. Test with `testutil.GatherAndCount` after incrementing.
- **AMQP:** Declare exchanges/queues idempotently. Use `QueueDeclare` before `Consume`.
- **Docker:** Use `dockertest` for integration tests. Never hardcode container names.
- **mTLS:** Always verify `{{TLS_CA_FILE}}`. `InsecureSkipVerify: true` is forbidden in production.

> **Tip:** See `examples/sovereign-shield/patterns/` for reference implementations of these conventions.
