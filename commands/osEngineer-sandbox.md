---
name: osEngineer:sandbox
description: >-
  Spins up the isolated local stack (RabbitMQ, Vault, data layers)
  from `live-system/sandbox-compose.yml`, seeds mock credentials,
  builds containers from workbench branch code, injects the mission
  payload, and emits MISSION_TEST_REPORT.md. Use during verify phase
  for cross-service tracer bullets (AMQP topology change, Vault
  policy change, schema migration) or when the verifier needs an
  isolated end-to-end run. Don't use against the live system (use
  /osEngineer:fix with live-system-operator); don't use for
  single-repo unit tests (the dockertest suite is cheaper); don't use
  without a validated mission-test JSON — the provisioner refuses.
phase_allowed: [execute, verify]
---

# /osEngineer:sandbox

**Syntax:** `/osEngineer:sandbox start <mission-plan-path> [--clean] [--duration <secs>]`  
**Scope:** Workbench (multi-repo orchestration)  
**Primary Agent:** Sandbox Provisioner  
**Co-agents:** Researcher, Live System Operator, Verifier, Red-Team-Local  
**Output:** Active testbed runtime + `MISSION_TEST_REPORT.md`

---

## 1. Description

Spins up an isolated, containerized local sandbox stack running RabbitMQ, HashiCorp Vault, and data layers to execute and test a swarm mission end-to-end against local branch code modifications.

---

## 2. Arguments

| Parameter | Required | Description |
| :--- | :--- | :--- |
| `start <path>` | Yes | Absolute or relative path to the mission test definition file (`.json`). |
| `--clean` | No | Forces rebuilding of local code containers and purges previous Docker volumes. |
| `--duration` | No | The maximum execution window (in seconds) for the active swarm simulation [default: 60]. |

---

## 3. Step Protocol

1. **Pre-flight verification:**
   - Confirm Docker daemon is running locally.
   - Researcher validates the target JSON file against `specs/SCHEMAS/mission-test.schema.json`.
2. **Environment Isolation Setup:**
   - Provisioner launches `live-system/sandbox-compose.yml`.
   - Checks that RabbitMQ and Vault containers reach healthy status.
3. **Local Credentials Seeding:**
   - Sourced from gitignored `.osengineer/secrets.env`.
   - Seeds mock certificates and client tokens into Vault.
4. **Target Container Assembly:**
   - Compiles local developer branch code changes into lightweight local test images.
   - Deploys and connects containers to `net-secure-sandbox`.
5. **Swarm Message Trigger:**
   - Injects the starter AMQP payload into the local RabbitMQ queue.
6. **Active Diagnostic Inspection:**
   - Scrapes metrics endpoints every 5 seconds.
   - Evaluates logs for security alerts or microservice panics.
7. **Graceful Clean-up:**
   - Shuts down the sandbox Compose stack.
   - Compiles latency and log evidence into `MISSION_TEST_REPORT.md`.

---

## 4. Example Output

```bash
/osEngineer:sandbox start specs/TEMPLATES/mission-test.json --clean
```

Output:
```
[osEngineer] Sandboxing mission MS-088...
[osEngineer] + Docker sandbox network initialized.
[osEngineer] + Vault mock API ready (auto-unsealed).
[osEngineer] + RabbitMQ mock broker ready.
[osEngineer] + Compiled local Go changes for ola-fleet-chameleon.
[osEngineer] Swarm active. Injecting trigger decision.created...
[osEngineer] Swarm executing mission MS-088 (max duration: 60s)...
[osEngineer] Scraped metrics: latency = 45ms, memory = 22MB, througput = 12msg/s.
[osEngineer] Test execution complete. Tearing down sandbox...
[osEngineer] Generated: planning/active/phase-033/MISSION_TEST_REPORT.md (All assertions passed)
```
