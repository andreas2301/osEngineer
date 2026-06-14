# Project-Specific Conventions

- **Go:** `gofmt` clean, `%w` wrapping, JSON structured logs.
- **Prometheus:** `promauto` metrics have tests; `Help` strings are descriptive.
- **AMQP:** `QueueDeclare` before `Consume`; persistent delivery mode.
- **Docker:** No hardcoded names; `dockertest` for integration tests.
- **Ansible:** FQCN (`ansible.builtin.*`); idempotent tasks.
