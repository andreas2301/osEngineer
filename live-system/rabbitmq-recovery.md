# Runbook: RabbitMQ Queue/Exchange Recovery

## Detection

```bash
# Check queue depth (should be near 0 in steady state)
rabbitmqctl list_queues name messages | grep -E "mission|provision"

# Check consumers (should match expected count)
rabbitmqctl list_consumers | grep -E "strategist|supervisor"
```

## Common Issues

### Missing Exchange
```bash
# Re-declare from ansible
ansible-playbook ansible/bootstrap_host.yml --tags rabbitmq
```

### Missing Queue
```bash
# Re-declare manually (idempotent)
rabbitmqctl declare queue name=supervisor.mission.requests durable=true
```

### PRECONDITION_FAILED
Usually means code and ansible disagree on exchange type. Fix the mismatch, then restart service.

## Verification
```bash
rabbitmqctl list_exchanges name type | grep ex\.
rabbitmqctl list_bindings source_name destination_name routing_key | grep mission
```
