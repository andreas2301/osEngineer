# live-system/

Operational runbooks for the live production deployment.

## Purpose

This directory holds quick-reference guides for common operational tasks:
- Restarting services
- Recovering message brokers
- Rotating certificates
- Unsealing secrets vaults
- Checking container health

## Project-Specific Conventions

Runbooks are inherently project-specific. A Kubernetes deployment has different operational procedures than a Docker Compose stack or a systemd fleet.

- Place generic runbooks here.
- Place project-specific runbooks in `.osengineer/runbooks/` or in a dedicated `runbooks/` repo.
- Link to your monitoring dashboards, on-call rotations, and incident response playbooks from each runbook.

## Example Structure

```
live-system/
├── README.md
├── restart-service.md
├── cert-rotation.md
└── health-checks.md
```

## Integration with osEngineer

The **Live System Operator** agent reads runbooks from this directory before suggesting operational changes. During a hotfix phase, the operator follows the runbook's rollback path and logs deviations to `memory/retrospectives/`.
