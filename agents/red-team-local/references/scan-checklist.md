# Scan Checklist

## SAST (Static Analysis)
- [ ] No hardcoded secrets (API keys, tokens, passwords).
- [ ] No `InsecureSkipVerify: true` in TLS config (production code).
- [ ] No `eval()`, `exec()`, or shell injection vectors.
- [ ] No SQL injection (parameterized queries only).
- [ ] No unbounded loops or recursion without depth limits.

## Secret Leaks
- [ ] No `.env` files committed.
- [ ] No `ghp_` or `sk-` tokens in code or tests.
- [ ] No private keys in test fixtures (use `testutil.GenerateKey` instead).

## Allowlist Enforcement
- [ ] New Docker images use allowed registries only.
- [ ] New AMQP exchanges/queues follow naming convention (`ex.*`, `*.requests`).
- [ ] New Vault paths follow the project's configured prefix (e.g. `secret/{{PROJECT_NAME}}/*`).

## Project-Specific Conventions
- [ ] Fail-closed: Any error path must log WARN and disable, not panic or fallback to insecure.
- [ ] mTLS: Client certs verify `{{TLS_CA_FILE}}`. No `InsecureSkipVerify`.
- [ ] AMQP: Persistent delivery mode for mission-critical messages. No `autoDelete` on production queues.
- [ ] Prometheus: Respect the project's reserved metric prefix (configured in `.osengineer/workbench-config.yml`).
