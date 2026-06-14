# Sandbox Lifecycle Execution

When `/osEngineer:sandbox start` is invoked, follow these absolute steps:

## Phase 1: Pre-Flight Integrity Check
* Confirm `docker` and `docker-compose` are running and accessible.
* Validate the target mission test plan against `specs/SCHEMAS/mission-test.schema.json`.
* Source user secrets dynamically from `.osengineer/secrets.env` if present. If absent, fall back to safe environment defaults.

## Phase 2: Orchestrated Boot (`live-system/sandbox-setup.sh`)
* Spin up `live-system/sandbox-compose.yml` in detached mode.
* Wait for RabbitMQ management console (`http://localhost:15672`) to return HTTP 200.
* Wait for Vault API (`http://localhost:8200/v1/sys/health`) to confirm readiness.

## Phase 3: Vault Unsealing & Pre-Warming
* Initialize and unseal local Vault container using development-only mock keys.
* Write required mock credentials (such as AMQP secrets, persona keys, and developer certs) into `secret/data/clearance/`.
* Expose a secure development Vault token for active fleet containers.

## Phase 4: Swarm Launch & Mission Injection
* Launch target fleet containers (e.g. `ola-fleet-chameleon`) bound to the local workbench code changes.
* Inject the mission trigger payload into the RabbitMQ decision exchange (`decision.bus`).
* Stream logs in a separate background thread to detect panic errors or connection timeouts.

## Phase 5: Metrics Scrape & Log Auditing
* Poll Prometheus endpoint (`http://localhost:8080/metrics`) for decision latency, memory metrics, and throughput.
* Audit container logs for warning indicators or security clearance failures.

## Phase 6: Clean Tear-Down
* Stop and remove all sandbox containers.
* Destroy the local virtual network `net-secure-sandbox`.
* Output the final `MISSION_TEST_REPORT.md`.
