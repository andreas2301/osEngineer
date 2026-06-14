# Topology Validation Rules

| Layer | Rule | Violation |
|-------|------|-----------|
| **Management** | Strategist knows missions, not Docker. | Strategist imports docker SDK → BLOCK |
| **Supervisor** | Supervisor knows containers, not mission heuristics. | Supervisor imports mission planner → BLOCK |
| **Operator** | Operator is the execution engine. | Operator bypassed for direct Docker spawn → BLOCK |
| **Fleet** | Fleet brokers are isolated from host broker. | AMQP URL points to host broker from fleet → BLOCK |
| **Vault** | All secrets via Vault, never env vars in production. | Hardcoded password in compose → BLOCK |
