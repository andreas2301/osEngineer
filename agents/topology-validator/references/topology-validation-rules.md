# Topology Validation Rules

| Rule | Violation Example |
|------|-------------------|
| Host broker = management bus | Fleet broker used for `ex.management.missions` → BLOCK |
| DLX = fanout | DLX declared as `topic` → BLOCK |
| Persistent queues | `autoDelete: true` on production queue → BLOCK |
| Idempotent declares | Code panics on `PRECONDITION_FAILED` instead of handling → HIGH |
