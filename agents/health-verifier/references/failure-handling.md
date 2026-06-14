# Failure Handling

If any check fails:

1. Log `HEALTH_REPORT.md` with failure details.
2. If CRITICAL (service down): trigger `/osEngineer:fix` for incident response.
3. If WARNING (missing metrics): note in phase verification but don't block.
