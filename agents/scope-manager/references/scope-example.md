# Scope Example

**Goal:** "Fix management service to publish to orchestrator bus"

```yaml
# SCOPE.yaml
primary:
  - <producer-repo>      # Producer of Plan
  - <consumer-repo>      # Consumer of Plan
  - <registry-repo>      # Schema registry
supporting:
  - ansible/             # Topology declarations
  - <docs-repo>          # Documentation updates
excluded:
  - <dashboard-repo>     # No UI change
  - <fleet-repo>         # No fleet change
  - <config-repo>        # No config change
```
