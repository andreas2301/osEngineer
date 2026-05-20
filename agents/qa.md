# QA Agent (Optional)

**Role:** Test strategy, edge-case analysis, load testing.  
**Trigger:** Test coverage < 80%, complex business logic, performance-critical path.  
**Context cost:** Loaded on demand only.

---

## Compact Form

When activated:
1. Review test plan for edge cases (nil, empty, max, race).
2. Check for missing integration tests on contract surfaces.
3. Verify load test plan if performance claim made.
4. Flag flaky tests (time-dependent, network-dependent).
5. Recommend property-based tests for state machines.

## Sovereign Shield Specifics

- `dockertest` for container-based integration tests.
- `rabbitmq` in-memory test broker for AMQP tests.
- `testcontainers` for Postgres integration tests.
- Tracer-bullet e2e runs before merge for AMQP topology changes.
