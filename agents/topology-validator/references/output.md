# Output

```markdown
# Topology Drift Report

## AMQP (3 checks)
- [x] Exchange names match
- [ ] Exchange types match: `strategist.provisioning.responses.dlx` is `topic` in code, `fanout` in ansible
- [x] Queue names match

## Docker Compose (5 checks)
- [x] Service names match
- [x] Networks correct
- [x] No port conflicts
- [x] Cert mounts read-only
- [ ] Env var `STRATEGIST_RABBITMQ_PASS` missing `:?error` pattern
```
