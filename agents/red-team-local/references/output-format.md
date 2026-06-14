# Output Format

```markdown
# Red Team Report — PR #NNN

## Critical (0)
(None found)

## High (1)
- **File:** `internal/service/service.go:142`
- **Issue:** Missing error handling on `docker.SpawnContainer`
- **Fix:** Wrap error with `%w` and emit WARN metric

## Medium (0)
(None found)

## Low (2)
- `internal/api/handlers.go:88` — log message missing correlation_id
- `docker-compose.yml:45` — healthcheck interval too aggressive (1s)
```
