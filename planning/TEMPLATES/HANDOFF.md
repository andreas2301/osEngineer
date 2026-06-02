# osEngineer Handoff — HO-{{HANDOFF_NUMBER}}

**Status:** Open | Resolved
**Source Team:** {{FROM_TEAM}}
**Target Team:** {{TO_TEAM}}
**Scenario Profile:** infra | web | api | hybrid
**Opened At:** {{TIMESTAMP}}

---

## 1. Context & Objective

Provide a concise summary of the cross-team or cross-repo requirement. Why is this handoff needed, and how does it block the parent phase?

## 2. Requirements & Acceptance Criteria

List the exact assertions that must be validated to close this handoff:
*   [ ] Assertion 1: Describe the expected state, signature, or behavior.
*   [ ] Assertion 2: ...

---

## 3. Scenario-Specific Operational Specifications

Fill in the section relevant to the **Scenario Profile**:

### A. Infrastructure / Configuration Profile (Ansible/Docker)
*   **Target Config Files:** List yaml/ini paths (e.g., `ansible/group_vars/all.yml`).
*   **Verbatim Execution Commands:**
    ```bash
    # Command to dry-run or syntax-check:
    ansible-playbook -i localhost, playbooks/deploy.yml --syntax-check
    # Command to run local test setup:
    docker-compose -f live-system/sandbox-compose.yml up -d
    ```
*   **Performance Invariant:** Log CPU/Memory metrics of the container or verify that the RabbitMQ management portal returns HTTP 200 within 5 seconds.

### B. Frontend / Web Application Profile (Playwright)
*   **Target Components:** List source paths (e.g., `src/components/MDashboard.js`).
*   **Playwright Test Suite:**
    ```bash
    npx playwright test tests/e2e/MDashboard.spec.js
    ```
*   **Visual Regression Invariants:** Screenshot comparison files and expected DOM selector anchors (e.g., `#dashboard-header` is visible and matches style guidelines).

### C. Backend / API Profile (Go/REST/AMQP)
*   **Target Schemas/Contracts:** Reference OpenAPI spec or `.json` message schemas.
*   **AMQP Routing / Queue Assertions:**
    *   Exchange: `{{EXCHANGE_NAME}}`
    *   Routing Key: `{{ROUTING_KEY}}`
    *   Expected Queues: `{{QUEUES}}`
*   **Execution Commands:**
    ```bash
    go test -v ./internal/metrics/ -run TestMetricsGather
    ```

---

## 4. Closing Evidence (Completed by Target Team)

*   **Resolved At:** {{TIMESTAMP}}
*   **Resolution Log:** Summarize the implementation (atomic commits, pull requests, test output).
*   **Execution Verification Output:** (Paste raw exit codes and verified terminal streams here).
*   **Verification Status:** PASS | FAIL
