# Project Contracts

| Surface | Location | Schema Tool |
|---------|----------|-------------|
| AMQP messages | `internal/schema/files/*.json` | JSON Schema 2020-12 |
| Registry allowlist | `internal/schema/files/universal-agent-v1.json` | JSON Schema 2020-12 |
| Service manifests | `.claude/contracts/service-manifest.yml` | JSON Schema 2020-12 |
| DB migrations | `migrations/sql/V*.sql` | Idempotent SQL |
| Ansible topology | `ansible/tasks/configure_rabbitmq.yml` | YAML (ansible-lint) |
