# Health Matrix

| Service | Metrics Port | Health Endpoint | AMQP Consumer | Custom Metric Example |
|---------|-------------|-----------------|---------------|----------------------|
| Strategist | 9091 | :8080/health | strategist.mission.status | `mission_plans_published_total` |
| Supervisor | 8080/metrics | :8080/health | supervisor.mission.requests | `supervisor_missions_handled_total` |
| Guardian | — | :8080/health | guardian.events | `guardian_schema_validation_errors_total` |
| Metronome | 9091 | :8080/health | metronome.budget.responses | `metronome_tasks_submitted_total` |
| Persist | 9091 | :8080/health | persist.approvals | `persist_records_total` |
| Accountant | 9091 | :8080/health | accountant.cost.events | `accountant_cost_events_total` |
| Witness | 9091 | :8080/health | — | `witness_http_requests_total` |
| Registry | 9091 | :8080/health | — | `registry_registrations_total` |
