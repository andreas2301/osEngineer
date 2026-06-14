# Output Format

```markdown
# Contract — retry-policy-v1.yaml

## Producer
- Repo: <management-service-repo>
- Exchange: ex.management.missions
- Routing key: mission.request.{team_id}

## Schema
```yaml
type: object
required: [schema_version, plan_id, customer_id]
properties:
  schema_version:
    type: string
    enum: ["mission-plan-v1"]
  plan_id:
    type: string
    format: uuid
```

## Validation
- JSON Schema: `internal/schema/files/mission-plan-v1.json`
- Registry entry: `universal-agent-v1.json` (runtime_type extended)
```
