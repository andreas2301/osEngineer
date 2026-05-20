# Spec-Driven Development Protocol

Adapted from [Spec Kit](https://github.com/github/spec-kit).  
**Rule:** No code without a contract. Contract validates before commit.

---

## Contract Surfaces

| Surface | Format | Location | Validator |
|---------|--------|----------|-----------|
| HTTP API | OpenAPI 3.1 | `docs/openapi/*.yaml` | spectral |
| AMQP Message | JSON Schema 2020-12 | `internal/schema/files/*.json` | jsonschema |
| Service Manifest | YAML + JSON Schema | `.claude/contracts/service-manifest.yml` | jsonschema |
| DB Migration | SQL | `migrations/sql/V*.sql` | sqlfluff (optional) |
| Ansible Topology | YAML | `ansible/tasks/*.yml` | ansible-lint |

## Contract-First Steps

1. **Identify surface:** Is this task touching an API, message, schema, or DB?
2. **Write contract:** Create/update the contract file FIRST.
3. **Validate contract:** Run the validator. Must pass.
4. **Write tests:** Test against the contract.
5. **Write code:** Implement to satisfy the contract.
6. **Commit:** Contract commit BEFORE code commit.

## Schema Evolution Rules

- **Additive only:** New fields, new enums, new endpoints.
- **No renames:** Renaming breaks consumers. Deprecate + add new instead.
- **No removals:** Remove only after 2 major versions with deprecation warning.
- **Version in path/name:** `mission-plan-v1.json`, not `mission-plan.json`.

## Sovereign Shield Contracts

```yaml
# Example: AMQP message contract
# .claude/contracts/produced/mission-plan.yaml

producer:
  repo: ola-management-strategist
  exchange: ex.management.missions
  routing_key: mission.request.{team_id}
  schema: internal/schema/files/mission-plan-v1.json

consumer:
  repo: ola-management-supervisor
  queue: supervisor.mission.requests
  binding_key: mission.request.#

validation:
  json_schema: "https://json-schema.org/draft/2020-12/schema"
  registry_entry: universal-agent-v1.json
```
